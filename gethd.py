from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import pandas as pd
import time
import re
import os
def scrape_hospitals_doctors(location, scroll_times=15, wait_time=3):
    """
    Stream hospitals/doctors around a location from Google Maps using Remote Selenium.
    Yields one result at a time as a dictionary.
    """
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-plugins")
    options.add_argument("--disable-images")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    selenium_host = os.getenv('SELENIUM_HOST', 'localhost')
    selenium_port = os.getenv('SELENIUM_PORT', '4444')
    selenium_url = f"http://{selenium_host}:{selenium_port}/wd/hub"

    try:
        print(f"🔗 Connecting to Selenium at: {selenium_url}")
        driver = webdriver.Remote(
            command_executor=selenium_url,
            options=options
        )
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        print("✅ Successfully connected to remote Selenium")
    except Exception as e:
        print(f"❌ Failed to connect to remote Selenium: {e}")
        return  # generator ends early

    try:
        search_queries = [
            f"{location} hospitals",
            f"{location} doctors",
            f"{location} clinics",
            f"{location} medical centers"
        ]

        for search_query in search_queries:
            print(f"🔍 Searching for: {search_query}")
            url = f"https://www.google.com/maps/search/{search_query.replace(' ', '+')}"
            driver.get(url)
            time.sleep(5)

            try:
                wait = WebDriverWait(driver, 15)
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '[role="feed"]')))
                results_container = driver.find_element(By.CSS_SELECTOR, '[role="feed"]')

                last_height = driver.execute_script("return arguments[0].scrollHeight", results_container)
                for scroll_attempt in range(scroll_times):
                    print(f"📜 Scrolling... ({scroll_attempt + 1}/{scroll_times})")
                    driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", results_container)
                    time.sleep(wait_time)
                    new_height = driver.execute_script("return arguments[0].scrollHeight", results_container)
                    if new_height == last_height:
                        print("🛑 Reached end of results")
                        break
                    last_height = new_height

                cards = driver.find_elements(By.CSS_SELECTOR, '[role="feed"] > div > div')
                print(f"📋 Found {len(cards)} potential results")

                for idx, card in enumerate(cards):
                    try:
                        if card.find_elements(By.CSS_SELECTOR, '[aria-label="Sponsored"]'):
                            continue

                        # --- Extract fields ---
                        name = None
                        name_elements = card.find_elements(By.CSS_SELECTOR, '.qBF1Pd, .fontHeadlineSmall')
                        if name_elements:
                            name = name_elements[0].text.strip()
                        if not name:
                            continue

                        rating = None
                        review_count = None
                        rating_elements = card.find_elements(By.CSS_SELECTOR, '.MW4etd')
                        if rating_elements:
                            try:
                                rating_text = rating_elements[0].text.strip().replace(',', '.')
                                if re.match(r'^\d+(\.\d+)?$', rating_text):
                                    rating = float(rating_text)
                            except Exception:
                                pass
                        review_elements = card.find_elements(By.CSS_SELECTOR, '.UY7F9')
                        if review_elements:
                            try:
                                review_text = review_elements[0].text.strip()
                                review_match = re.search(r'\((\d+(?:,\d+)*)\)', review_text)
                                if review_match:
                                    review_count = int(review_match.group(1).replace(',', ''))
                            except Exception:
                                pass

                        if rating is None:
                            star_elements = card.find_elements(By.CSS_SELECTOR, '[role="img"][aria-label*="star"]')
                            if star_elements:
                                aria_label = star_elements[0].get_attribute('aria-label')
                                if aria_label:
                                    rating_match = re.search(r'(\d+\.?\d*)\s*stars?', aria_label)
                                    review_match = re.search(r'(\d+(?:,\d+)*)\s*[Rr]eviews?', aria_label)
                                    if rating_match:
                                        rating = float(rating_match.group(1))
                                    if review_match and review_count is None:
                                        review_count = int(review_match.group(1).replace(',', ''))

                        category = None
                        category_elements = card.find_elements(By.CSS_SELECTOR, '.W4Efsd span')
                        for elem in category_elements:
                            text = elem.text.strip()
                            if text and text not in ['·', ''] and not re.match(r'^\d', text):
                                category = text
                                break

                        address = None
                        address_elements = card.find_elements(By.CSS_SELECTOR, '.W4Efsd')
                        for addr_elem in address_elements:
                            addr_text = addr_elem.text.strip()
                            if addr_text and '·' in addr_text:
                                parts = addr_text.split('·')
                                for part in parts:
                                    part = part.strip()
                                    if (len(part) > 10 and any(char.isdigit() for char in part) 
                                        and not part.startswith('0') and 'stars' not in part.lower()):
                                        address = part
                                        break
                                if address:
                                    break

                        phone = None
                        phone_elements = card.find_elements(By.CSS_SELECTOR, '.UsdlK')
                        if phone_elements:
                            phone = phone_elements[0].text.strip()

                        hours_status = None
                        hours_elements = card.find_elements(By.CSS_SELECTOR, 
                                                           '[style*="color: rgba(25,134,57"], [style*="color: rgba(220,54,46"]')
                        if hours_elements:
                            hours_status = hours_elements[0].text.strip()

                        website = None
                        website_elements = card.find_elements(By.CSS_SELECTOR, 'a[data-value="Website"]')
                        if website_elements:
                            website = website_elements[0].get_attribute('href')

                        review_snippet = None
                        snippet_elements = card.find_elements(By.CSS_SELECTOR, '.ah5Ghc span')
                        if snippet_elements:
                            review_snippet = snippet_elements[0].text.strip().replace('"', '')

                        # --- Yield entry immediately ---
                        if name and (category or address or phone):
                            data_entry = {
                                "name": name,
                                "category": category,
                                "rating": rating,
                                "review_count": review_count,
                                "address": address,
                                "phone": phone,
                                "hours_status": hours_status,
                                "website": website,
                                "review_snippet": review_snippet,
                                "search_query": search_query
                            }
                            print(f"✅ Yielding: {name}")
                            yield data_entry  # stream this result now

                    except Exception as e:
                        print(f"⚠️ Error processing card {idx}: {e}")
                        continue

            except TimeoutException:
                print(f"⏰ Timeout for query: {search_query}")
                continue
            except Exception as e:
                print(f"❌ Error during search for '{search_query}': {e}")
                continue

    except Exception as e:
        print(f"❌ Critical error in scrape_hospitals_doctors: {e}")
    finally:
        try:
            driver.quit()
            print("🔌 Selenium driver closed")
        except:
            pass
