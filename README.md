# Medical Document Retrieval System

## Overview
The Medical Document Retrieval System is a web-based application that allows users to search and retrieve relevant medical documents using natural language queries. The system uses TF-IDF vectorization and cosine similarity to rank documents by relevance to the search query.

## System Architecture
The system follows a client-server architecture with the following components:

```
┌─────────────────────────────────────────────────────────────┐
│                    Client (Web Browser)                     │
└─────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                    Web Server (Flask)                       │
│                                                             │
│  ┌─────────────┐  ┌─────────────────────────────────────┐  │
│  │   Routes    │  │           Search Engine             │  │
│  │             │  │                                     │  │
│  │  GET: /     │  │  ┌─────────────────────────────────┐  │  │
│  │  POST: /    │  │  │   Document Retriever (TF-IDF)   │  │  │
│  │  POST: /api │  │  └─────────────────────────────────┘  │  │
│  └─────────────┘  └─────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│                    Data Storage                             │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │           Medical Documents (Text Files)           │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Components

### 1. Web Application (app.py)
- Built with Flask web framework
- Handles HTTP requests and responses
- Renders HTML templates
- Interfaces with the document retrieval system

#### Routes:
- `GET /` - Renders the main search page
- `POST /search` - Handles search queries and returns results
- `POST /api/search` - API endpoint for programmatic access

### 2. Document Retrieval System (retriever.py)
- Uses TF-IDF (Term Frequency-Inverse Document Frequency) vectorization
- Implements cosine similarity for document ranking
- Loads and processes medical documents from text files
- Returns ranked results based on query relevance

### 3. User Interface
- **Templates**: HTML templates using Jinja2 templating engine
- **Styling**: CSS for responsive and professional design

### 4. Data Storage
- Text files containing medical documents
- Simple file-based storage for easy deployment

## Technology Stack
- **Backend**: Python 3.9, Flask
- **Search Engine**: scikit-learn (TF-IDF vectorization)
- **Frontend**: HTML5, CSS3, Jinja2 templates
- **Deployment**: Docker, Docker Compose
- **Web Server**: Gunicorn (in production)

## Deployment Architecture
The application is containerized using Docker for easy deployment and scalability.

### Docker Configuration
- **Dockerfile**: Defines the application image
- **docker-compose.yml**: Defines the service configuration

## Data Flow
1. User accesses the web interface through a browser
2. User enters a search query and submits the form
3. Flask application receives the request
4. Application calls the document retriever with the query
5. Retriever processes the query using TF-IDF vectorization
6. Retriever calculates similarity scores for all documents
7. Retriever returns ranked results to the application
8. Application renders results in the HTML template
9. User views the search results in the browser

## How to Run

### Prerequisites
- Python 3.9+
- Docker and Docker Compose (for containerized deployment)

### Local Development

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Run the application:
   ```
   python app.py
   ```

3. Access the application at `http://localhost:5000`

### Docker Deployment

1. Build and run with Docker Compose:
   ```
   docker-compose up --build
   ```

2. Access the application at `http://localhost:5000`

### API Usage

The application also provides a REST API for programmatic access:

```
POST /api/search
Content-Type: application/json

{
  "query": "symptoms of diabetes"
}
```

Response:
```json
{
  "results": [
    {
      "title": "Diabetes Treatment Options",
      "content": "Diabetes is a disease that occurs when your blood glucose...",
      "score": 0.85
    }
  ]
}
```

## Project Structure
```
medical-document-retrieval/
├── app.py                 # Flask application
├── retriever.py           # Document retrieval system
├── requirements.txt       # Python dependencies
├── Dockerfile             # Docker configuration
├── docker-compose.yml     # Docker Compose configuration
├── templates/
│   └── index.html         # HTML template
├── static/
│   └── style.css          # CSS styling
└── data/
    └── medical_docs.txt   # Sample medical documents
```

## Future Enhancements
- Implement more advanced natural language processing
- Add document categorization and filtering
- Integrate with external medical databases
- Add user authentication and personalized search history
- Implement full-text search with Elasticsearch