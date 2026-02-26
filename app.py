import os
import numpy as np
import faiss
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from PyPDF2 import PdfReader
import openai
from PIL import Image
import base64
import io
import markdown2
import google.generativeai as genai
from gethd import scrape_hospitals_doctors


from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import threading


# ========== CONFIG ==========
KNOWLEDGE_FOLDER = "data"
PDF_IMAGES_FOLDER = "pdf_images"
os.makedirs(PDF_IMAGES_FOLDER, exist_ok=True)

# PostgreSQL config from Docker Compose env
DB_URL = os.getenv("DATABASE_URL", "postgresql+psycopg2://xhealth_user:strongpassword@localhost:5432/xhealth_db")

# ========== FLASK ==========
app = Flask(__name__, template_folder="templates")
app.config['SQLALCHEMY_DATABASE_URI'] = DB_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ========== MODELS ==========
# ========== MODELS ==========
class User(db.Model):
    __tablename__ = "users"  # explicit table name for clarity
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    blood_type = db.Column(db.String(5), nullable=True)  # e.g. "A+", "O-"
    city = db.Column(db.String(120), nullable=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


# Create tables if they don't exist
with app.app_context():
    db.create_all()


# Create tables
with app.app_context():
    db.create_all()

# ========== EMBEDDINGS & OPENAI ==========
genai.configure(api_key="AIzaSyDEpJsw55KTROvnwz7VVIIdiEfKLuc11GY")
EMBED_MODEL = "models/embedding-001"

# OpenAI configuration for version 0.27.8
openai.api_base = "https://openrouter.ai/api/v1"
openai.api_key = "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"
GEN_MODEL = "meta-llama/llama-3.2-11b-vision-instruct:free"


def get_embedding(text):
    response = genai.embed_content(model=EMBED_MODEL, content=text)
    return np.array(response["embedding"], dtype="float32")


def extract_text_from_pdf(pdf_path):
    reader = PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"
    return text.strip()


def extract_images_base64(pdf_path, max_images=2):
    images = []
    reader = PdfReader(pdf_path)
    for page in reader.pages:
        resources = page.get("/Resources")
        if not resources:
            continue
        xObject = resources.get("/XObject")
        if not xObject:
            continue
        xObject = xObject.get_object()
        for obj_name in xObject:
            xobj = xObject[obj_name]
            if xobj.get("/Subtype") != "/Image":
                continue
            data = xobj.get_data()
            width = xobj.get("/Width")
            height = xobj.get("/Height")
            color_space = xobj.get("/ColorSpace")
            mode = "RGB" if color_space == "/DeviceRGB" else "P"
            try:
                if xobj.get("/Filter") == "/DCTDecode":
                    img = Image.open(io.BytesIO(data))
                elif xobj.get("/Filter") == "/JPXDecode":
                    img = Image.open(io.BytesIO(data))
                else:
                    img = Image.frombytes(mode, (width, height), data)
                img.thumbnail((1024, 1024))
                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=80)
                images.append(base64.b64encode(buffer.getvalue()).decode("utf-8"))
                if len(images) >= max_images:
                    return images
            except Exception as e:
                print(f"⚠️ Skipped image due to error: {e}")
                continue
    return images


def build_vector_store():
    texts, embeddings, pdf_files = [], [], []
    for file_name in os.listdir(KNOWLEDGE_FOLDER):
        if file_name.lower().endswith(".pdf"):
            path = os.path.join(KNOWLEDGE_FOLDER, file_name)
            text = extract_text_from_pdf(path)
            if text:
                emb = get_embedding(text)
                texts.append(text)
                embeddings.append(emb)
                pdf_files.append(path)
    if not embeddings:
        return None, [], []
    dim = len(embeddings[0])
    index = faiss.IndexFlatL2(dim)
    index.add(np.array(embeddings))
    return index, texts, pdf_files


index, texts, pdf_files = build_vector_store()

# ========== ROUTES ==========
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/ask")
def ask():
    question = request.args.get("question", "")
    if not question:
        return "No question provided", 400
    results = search_knowledge(question, index, texts, pdf_files)
    if not results:
        return "No relevant documents found.", 404
    context_text = "\n".join([r[0] for r in results])
    images_html = ""
    i = 0
    images_payload = []
    for pdf_file in [r[1] for r in results]:
        for img_b64 in extract_images_base64(pdf_file):
            i += 1
            if i == 2:
                break
            images_payload.append({"type": "image", "image_data": img_b64})
            images_html += f'<img src="data:image/jpeg;base64,{img_b64}" style="max-width:400px; margin:10px;"/>'
    prompt = f"""
### Question
{question}

### Available Knowledge
{context_text}

### Instruction
Answer only from the provided text excerpts and images.  
Format your answer in Markdown.
"""
    try:
        response = openai.ChatCompletion.create(
            model=GEN_MODEL,
            messages=[{"role": "user", "content": [{"type": "text", "text": prompt}] + images_payload}],
            max_tokens=2000,
            temperature=0.2
        )
        answer = response.choices[0].message.content
        html_answer = markdown2.markdown(answer, extras=["tables", "fenced-code-blocks"])
        return html_answer + "<br><h3>📌 Images extraites :</h3>" + images_html
    except openai.error.RateLimitError:
        return "⚠️ Rate limit exceeded."
    except openai.error.APIError as e:
        return f"🚨 API Error: {str(e)}"
    except Exception as e:
        return f"⚠️ Unexpected error: {str(e)}"


# ========== SIGNUP ==========
@app.route("/signup", methods=["POST"])
def signup():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")
    confirm = data.get("confirm")
    blood_type = data.get("bloodType")
    city = data.get("city")

    if not email or not password or not confirm or not blood_type or not city:
        return jsonify({"success": False, "error": "All fields are required."})
    if password != confirm:
        return jsonify({"success": False, "error": "Passwords do not match."})
    if User.query.filter_by(email=email).first():
        return jsonify({"success": False, "error": "Email already registered."})

    new_user = User(email=email, blood_type=blood_type, city=city)
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({"success": True})

# ========== LOGIN ==========
@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"success": False, "error": "Email and password are required."})

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"success": False, "error": "User not found."})
    
    if not user.check_password(password):
        return jsonify({"success": False, "error": "Incorrect password."})

    return jsonify({"success": True, "message": f"Welcome back, {email}!"})

from flask import Response, stream_with_context
import json

@app.route("/send_location", methods=["POST"])
def send_location():
    data = request.get_json()
    location = data.get("location")

    if not location:
        return json.dumps({
            "success": False,
            "error": "Please provide a location ?location=..."
        }), 400

    def generate():
        try:
            print(f"🔍 Starting scrape for location: {location}")
            
            # Use the generator directly
            generator = scrape_hospitals_doctors(location, scroll_times=5, wait_time=2)
            count = 0
            no_result_sent = False

            for item in generator:
                if item is None:
                    continue
                yield json.dumps(item) + "\n"
                count += 1

            # If nothing yielded, send a "no results" message
            if count == 0:
                yield json.dumps({
                    "success": False,
                    "error": "No hospitals/doctors found. This might be due to Chrome/Selenium setup issues in Docker."
                }) + "\n"

            # Signal completion
            yield json.dumps({"done": True, "count": count}) + "\n"

        except Exception as e:
            print(f"❌ Error in send_location: {str(e)}")
            import traceback
            traceback.print_exc()
            yield json.dumps({
                "success": False,
                "error": f"Scraping failed: {str(e)}. Check Docker logs for details."
            }) + "\n"

    return Response(stream_with_context(generate()), mimetype="application/json")




@app.route("/find_blood_matches", methods=["POST"])
def find_blood_matches():
    data = request.get_json()
    user_email = data.get("user")

    if not user_email:
        return Response(json.dumps({
            "success": False,
            "error": "Missing user email"
        }) + "\n", mimetype="application/json")

    def generate():
        try:
            # 1. Get logged-in user
            user = User.query.filter_by(email=user_email).first()
            if not user or not user.blood_type:
                yield json.dumps({
                    "success": False,
                    "error": "User not found or missing blood type"
                }) + "\n"
                return

            blood_type = user.blood_type
            print(f"🩸 Searching matches for blood type: {blood_type}")

            # 2. Stream people with same blood type
            matches = User.query.filter_by(blood_type=blood_type).all()
            count = 0

            for match in matches:
                # Skip the logged-in user themselves
                if match.email == user_email:
                    continue

                item = {
                    "id": match.id,
                    "name": match.email.split("@")[0],  # crude name placeholder
                    "email": match.email,
                    "blood_type": match.blood_type,
                    "city": match.city
                }
                yield json.dumps(item) + "\n"
                count += 1

            if count == 0:
                yield json.dumps({
                    "success": False,
                    "error": "No matches found"
                }) + "\n"

            yield json.dumps({"done": True, "count": count}) + "\n"

        except Exception as e:
            print(f"❌ Error in find_blood_matches: {str(e)}")
            yield json.dumps({
                "success": False,
                "error": f"Database error: {str(e)}"
            }) + "\n"

    return Response(stream_with_context(generate()), mimetype="application/json")


# ========== HELPER ==========
def search_knowledge(query, index, texts, pdf_files, top_k=2):
    query_emb = get_embedding(query)
    D, I = index.search(np.array([query_emb]), top_k)
    return [(texts[i], pdf_files[i]) for i in I[0] if i < len(texts)]

# ========== MAIN ==========
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
