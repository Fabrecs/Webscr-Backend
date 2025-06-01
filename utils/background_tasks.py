import requests
import re
import html
import threading
import tempfile
import time
import random
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from .cache import get_cache, set_cache # Import cache functions
import cloudscraper
import json
from bs4 import BeautifulSoup
import asyncio
from playwright.async_api import async_playwright

# Add this after the imports
import os

def get_mock_products(query, num_results=2):
    """Returns mock product data when scraping fails"""
    print(f"[DEBUG] 🎭 Returning mock products for '{query}'")
    
    mock_products = [
        {
            "name": f"Premium {query} - Style 1",
            "image_url": "https://via.placeholder.com/300x400/007bff/ffffff?text=Product+1"
        },
        {
            "name": f"Designer {query} - Style 2", 
            "image_url": "https://via.placeholder.com/300x400/28a745/ffffff?text=Product+2"
        },
        {
            "name": f"Trending {query} - Style 3",
            "image_url": "https://via.placeholder.com/300x400/ffc107/000000?text=Product+3"
        }
    ]
    
    return mock_products[:num_results]

# Global variable to store the Redis client
redis_client = None

def set_redis_client(client):
    """Set the Redis client for background tasks"""
    global redis_client
    redis_client = client
    print(f"[Background Task] Redis client set: {redis_client is not None}")

def get_selenium_driver():
    """Create and configure a Chrome WebDriver instance"""
    # More thorough Chrome process cleanup
    try:
        # Kill Chrome processes
        os.system("pkill -9 chrome 2>/dev/null")
        os.system("pkill -9 chromedriver 2>/dev/null")
        os.system("killall -9 chrome 2>/dev/null")
        os.system("killall -9 chromedriver 2>/dev/null")
        time.sleep(2)  # Give it more time to clean up
    except Exception as e:
        print(f"[DEBUG] ⚠️ Error cleaning up Chrome processes: {e}")

    chrome_options = Options()
    chrome_options.add_argument('--headless')  # Use headless mode
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    # Create a unique temporary directory for this session
    temp_dir = f"/tmp/chrome-{random.randint(1000, 9999)}"
    os.makedirs(temp_dir, exist_ok=True)
    chrome_options.add_argument(f'--user-data-dir={temp_dir}')
    
    # Use remote debugging with unique port to avoid conflicts
    port = random.randint(9222, 9999)
    chrome_options.add_argument(f'--remote-debugging-port={port}')
    
    # Disable automation detection
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # Performance and stability options
    chrome_options.add_argument('--disable-background-timer-throttling')
    chrome_options.add_argument('--disable-backgrounding-occluded-windows')
    chrome_options.add_argument('--disable-renderer-backgrounding')
    chrome_options.add_argument('--disable-ipc-flooding-protection')
    chrome_options.add_argument('--disable-logging')
    chrome_options.add_argument('--disable-web-security')
    chrome_options.add_argument('--ignore-certificate-errors')
    chrome_options.add_argument('--ignore-ssl-errors')
    chrome_options.add_argument('--ignore-certificate-errors-spki-list')
    
    # Memory options
    chrome_options.add_argument('--memory-pressure-off')
    
    # Additional options to prevent profile conflicts
    chrome_options.add_argument('--no-first-run')
    chrome_options.add_argument('--no-default-browser-check')
    chrome_options.add_argument('--password-store=basic')
    chrome_options.add_argument('--use-mock-keychain')
    
    # Explicitly set Chrome binary location
    chrome_options.binary_location = "/usr/bin/google-chrome-stable"
    
    driver = None
    try:
        print(f"[DEBUG] 🔧 Setting up ChromeDriver...")
        
        # Use system-installed ChromeDriver
        driver_path = "/usr/local/bin/chromedriver"
        print(f"[DEBUG] ✅ Using ChromeDriver at: {driver_path}")
        
        # Create service with driver path
        service = Service(executable_path=driver_path)
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Execute script to remove automation flags
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        print(f"[DEBUG] ✅ Selenium driver created successfully")
        return driver
        
    except Exception as e:
        print(f"[DEBUG] ❌ Failed to create Selenium driver: {e}")
        import traceback
        print(f"[DEBUG] Traceback: {traceback.format_exc()}")
        if driver:
            try:
                driver.quit()
            except Exception as q_err:
                print(f"[DEBUG] ⚠️ Error quitting driver after creation failure: {q_err}")
        # Clean up temp directory on failure
        try:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
            print(f"[DEBUG] 🧹 Cleaned up temporary directory: {temp_dir}")
        except Exception as cleanup_err:
            print(f"[DEBUG] ⚠️ Error cleaning up temp directory: {cleanup_err}")
        return None
    
def fetch_myntra_products_selenium(query, num_results=2):
    """Fetches product details from Myntra using Selenium WebDriver"""
    url_query = query.replace(' ', '-')
    raw_query = query.replace(' ', '%20')
    url = f"https://www.myntra.com/{url_query}?rawQuery={raw_query}"
    print(f"[DEBUG] 🌐 Selenium fetching Myntra results for: '{query}' from {url}")
    
    driver = None
    top_products = []
    temp_dir = None
    
    try:
        driver = get_selenium_driver()
        if not driver:
            print(f"[DEBUG] ❌ Could not create Selenium driver")
            return top_products
            
        # Get the temp directory from the driver's options
        for arg in driver.options.arguments:
            if arg.startswith('--user-data-dir='):
                temp_dir = arg.split('=')[1]
                break
        
        print(f"[DEBUG] 🚀 Loading page with Selenium...")
        driver.get(url)
        
        # Wait for page to load
        time.sleep(3)
        
        # Wait for products to load (look for common Myntra elements)
        try:
            wait = WebDriverWait(driver, 10)
            # Wait for either product grid or no results message
            wait.until(lambda d: len(d.page_source) > 1000)
        except TimeoutException:
            print(f"[DEBUG] ⏰ Timeout waiting for page to load")
        
        html_content = driver.page_source
        print(f"[DEBUG] 📄 Page loaded, content length: {len(html_content)} characters")
        
        # Log first 500 characters
        print(f"[DEBUG] First 500 chars of HTML: {html_content[:500]}")
        
        # Check for blocking indicators
        blocking_indicators = [
            "site maintenance", "oops! something went wrong", 
            "access denied", "blocked", "captcha", "security check"
        ]
        
        html_lower = html_content.lower()
        for indicator in blocking_indicators:
            if indicator in html_lower:
                print(f"[DEBUG] ⚠️ Blocking detected: '{indicator}' found in response")
                return top_products
        
        # Look for Myntra-specific content
        if "myntra" not in html_lower or len(html_content) < 2000:
            print(f"[DEBUG] ⚠️ Response seems invalid - too short or missing Myntra content")
            return top_products
        
        # Try multiple selectors for product data
        print(f"[DEBUG] 🔍 Searching for products using CSS selectors...")
        
        # Method 1: Look for product containers
        product_elements = driver.find_elements(By.CSS_SELECTOR, "[data-testid='product-base']")
        if not product_elements:
            product_elements = driver.find_elements(By.CSS_SELECTOR, ".product-base")
        if not product_elements:
            product_elements = driver.find_elements(By.CSS_SELECTOR, ".results-item")
        
        print(f"[DEBUG] Found {len(product_elements)} product elements")
        
        # Method 2: Extract from JSON data in script tags
        if not product_elements:
            print(f"[DEBUG] 🔍 Trying regex extraction from page source...")
            product_names = re.findall(r'"productName":"(.*?)"', html_content)
            image_urls = re.findall(r'"searchImage":"(.*?)"', html_content)
            
            print(f"[DEBUG] Regex found {len(product_names)} names, {len(image_urls)} images")
            
            if product_names and image_urls:
                count = 0
                for product_name, img_url in zip(product_names, image_urls):
                    if count >= num_results:
                        break
                    
                    decoded_name = html.unescape(product_name).encode('utf-8').decode('unicode_escape')
                    decoded_url = html.unescape(img_url).encode('utf-8').decode('unicode_escape')
                    
                    if decoded_url.startswith('http'):
                        full_url = decoded_url
                    else:
                        full_url = f"https://assets.myntassets.com/{decoded_url.lstrip('/')}"
                    
                    top_products.append({"name": decoded_name, "image_url": full_url})
                    count += 1
                    print(f"[DEBUG] ✅ Added product: {decoded_name}")
        
        # Method 3: Direct element extraction
        else:
            count = 0
            for element in product_elements[:num_results]:
                try:
                    # Try multiple selectors for product name
                    name_element = None
                    name_selectors = [
                        "h3", "h4", ".product-product", 
                        "[data-testid='product-name']", ".product-name"
                    ]
                    
                    for selector in name_selectors:
                        try:
                            name_element = element.find_element(By.CSS_SELECTOR, selector)
                            break
                        except:
                            continue
                    
                    # Try multiple selectors for image
                    img_element = None
                    img_selectors = ["img", ".product-image img", "picture img"]
                    
                    for selector in img_selectors:
                        try:
                            img_element = element.find_element(By.CSS_SELECTOR, selector)
                            break
                        except:
                            continue
                    
                    if name_element and img_element:
                        name = name_element.text or name_element.get_attribute("title") or f"Product {count + 1}"
                        img_url = img_element.get_attribute("src") or img_element.get_attribute("data-src")
                        
                        if img_url:
                            if not img_url.startswith('http'):
                                img_url = f"https://assets.myntassets.com/{img_url.lstrip('/')}"
                            
                            top_products.append({"name": name, "image_url": img_url})
                            count += 1
                            print(f"[DEBUG] ✅ Added product: {name}")
                
                except Exception as e:
                    print(f"[DEBUG] ⚠️ Error extracting product {count}: {e}")
                    continue
        
        print(f"[DEBUG] ✅ Selenium found {len(top_products)} products for '{query}'")
        
    except WebDriverException as e:
        print(f"[DEBUG] ❌ WebDriver error for '{query}': {e}")
    except Exception as e:
        print(f"[DEBUG] ❌ Unexpected error in Selenium fetch for '{query}': {e}")
        import traceback
        print(f"[DEBUG] Traceback: {traceback.format_exc()}")
    finally:
        if driver:
            try:
                driver.quit()
                print(f"[DEBUG] 🔌 Selenium driver closed")
            except Exception as e:
                print(f"[DEBUG] ⚠️ Error closing driver: {e}")
        
        # Clean up temp directory
        if temp_dir:
            try:
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
                print(f"[DEBUG] 🧹 Cleaned up temporary directory: {temp_dir}")
            except Exception as cleanup_err:
                print(f"[DEBUG] ⚠️ Error cleaning up temp directory: {cleanup_err}")
    
    return top_products

def fetch_myntra_products_fallback(query, num_results=2):
    """Fallback method using requests when Selenium fails"""
    url_query = query.replace(' ', '-')
    raw_query = query.replace(' ', '%20')
    url = f"https://www.myntra.com/{url_query}?rawQuery={raw_query}"
    print(f"[DEBUG] 🔄 Fallback: Fetching with requests for: '{query}' from {url}")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0",
        "Referer": "https://www.google.com/"
    }
    
    top_products = []

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        html_content = response.text
        print(f"[DEBUG] 🔄 Fallback response length: {len(html_content)} characters")
        
        # If we get the maintenance page, return mock data
        if len(html_content) < 1000 or "maintenance" in html_content.lower():
            print(f"[DEBUG] 🎭 Fallback detected blocking, using mock data")
            return []
        
        # Try to extract products
        product_names = re.findall(r'"productName":"(.*?)"', html_content)
        image_urls = re.findall(r'"searchImage":"(.*?)"', html_content)
        
        if product_names and image_urls:
            count = 0
            for product_name, img_url in zip(product_names, image_urls):
                if count >= num_results:
                    break
                    
                decoded_name = html.unescape(product_name).encode('utf-8').decode('unicode_escape')
                decoded_url = html.unescape(img_url).encode('utf-8').decode('unicode_escape')

                if decoded_url.startswith('http'):
                    full_url = decoded_url
                else:
                    full_url = f"https://assets.myntassets.com/{decoded_url.lstrip('/')}"
                    
                top_products.append({"name": decoded_name, "image_url": full_url})
                count += 1
                print(f"[DEBUG] 🔄 Fallback found product: {decoded_name}")
        
        # If no products found via regex, return mock data
        if not top_products:
            print(f"[DEBUG] 🎭 Fallback found no products, using mock data")
            return []
            
    except Exception as e:
        print(f"[DEBUG] 🔄 Fallback error: {e}, using mock data")
        return []
    
    return top_products

def fetch_myntra_products_cloudscraper(query, num_results=2):
    """Fetches product details from Myntra using cloudscraper"""
    url_query = query.replace(' ', '-')
    raw_query = query.replace(' ', '%20')
    url = f"https://www.myntra.com/{url_query}?rawQuery={raw_query}"
    print(f"[DEBUG] 🌐 Cloudscraper fetching Myntra results for: '{query}' from {url}")
    
    top_products = []
    
    try:
        # Create a cloudscraper session
        scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'mobile': False
            }
        )
        
        # Set headers to mimic a real browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0'
        }
        
        print(f"[DEBUG] 🚀 Sending request to Myntra...")
        response = scraper.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        html_content = response.text
        print(f"[DEBUG] 📄 Response received, content length: {len(html_content)} characters")
        
        # Parse HTML with BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Method 1: Try to find product data in script tags
        script_tags = soup.find_all('script', type='application/json')
        for script in script_tags:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and 'products' in data:
                    products = data['products']
                    for product in products[:num_results]:
                        if 'name' in product and 'image' in product:
                            top_products.append({
                                'name': product['name'],
                                'image_url': product['image']
                            })
                    break
            except:
                continue
        
        # Method 2: If no products found in script tags, try direct HTML parsing
        if not top_products:
            product_elements = soup.select('[data-testid="product-base"]')
            if not product_elements:
                product_elements = soup.select('.product-base')
            
            for element in product_elements[:num_results]:
                try:
                    name_element = element.select_one('h3, h4, .product-product, [data-testid="product-name"]')
                    img_element = element.select_one('img')
                    
                    if name_element and img_element:
                        name = name_element.text.strip()
                        img_url = img_element.get('src') or img_element.get('data-src')
                        
                        if img_url:
                            if not img_url.startswith('http'):
                                img_url = f"https://assets.myntassets.com/{img_url.lstrip('/')}"
                            
                            top_products.append({
                                'name': name,
                                'image_url': img_url
                            })
                except Exception as e:
                    print(f"[DEBUG] ⚠️ Error extracting product: {e}")
                    continue
        
        print(f"[DEBUG] ✅ Cloudscraper found {len(top_products)} products for '{query}'")
        
    except Exception as e:
        print(f"[DEBUG] ❌ Error in cloudscraper fetch for '{query}': {e}")
        import traceback
        print(f"[DEBUG] Traceback: {traceback.format_exc()}")
    
    return top_products

def process_recommendations_and_fetch(recommendations_data, gender="unisex"):
    """Processes recommendations and fetches top 2 Myntra products for each item."""
    global redis_client
    print("[Background Task] Starting sequential recommendation processing...")
    if not recommendations_data or 'recommendations' not in recommendations_data:
        print("[Background Task] No recommendations data found to process.")
        return

    parsed_recommendations = recommendations_data['recommendations']

    for category, items in parsed_recommendations.items():
        if not isinstance(items, list):
            print(f"[Background Task] Skipping category '{category}' as its value is not a list.")
            continue
            
        print(f"[Background Task] Processing category: {category}")
        for item in items:
            try:
                clothing_type = item.get('Clothing Type')
                color_str = item.get('Color')

                if not clothing_type or not color_str:
                    print(f"[Background Task] Skipping item due to missing 'Clothing Type' or 'Color': {item}")
                    continue

                # Split colors if 'or' is present, otherwise treat as a single color
                colors = [c.strip() for c in re.split(r'\s+or\s+', color_str, flags=re.IGNORECASE)]

                for color in colors:
                    if color.lower() in clothing_type.lower():
                        search_query = f"{clothing_type} for {gender}"
                        print(f"\n[Background Task] Searching for: {search_query} (color already in type)")
                    else:
                        search_query = f"{color} {clothing_type} for {gender}"
                        print(f"\n[Background Task] Searching for: {search_query}")

                    # --- Check Cache First ---
                    cache_key = f"myntra:{search_query}"
                    
                    if redis_client:
                        cached_products = get_cache(redis_client, cache_key)
                        
                        if cached_products is not None:
                            # Use cached results directly
                            products = cached_products
                            print(f"[Background Task] Using cached results for '{search_query}'.")
                        else:
                            # Fetch from Myntra if not in cache
                            products = fetch_myntra_products_selenium(search_query, num_results=2)
                            # Cache the results if found
                            if products:
                                set_cache(redis_client, cache_key, products)
                    else:
                        print("[Background Task] Redis client not available, skipping cache")
                        products = fetch_myntra_products_selenium(search_query, num_results=2)
                    # --- End Cache Check ---
                        
                    if products:
                        print(f"[Background Task] Top {len(products)} results for '{search_query}':")
                        for i, product in enumerate(products, 1):
                            print(f"  {i}. Name: {product['name']}")
                            print(f"     Image: {product['image_url']}")
                    else:
                        print(f"[Background Task] No results found for '{search_query}'.")
                        
            except Exception as e:
                print(f"[Background Task] Error processing item {item}: {e}")

    print("[Background Task] Finished processing recommendations.")

async def fetch_myntra_products_playwright(query, num_results=2):
    """Fetches product details from Myntra using Playwright"""
    url_query = query.replace(' ', '-')
    raw_query = query.replace(' ', '%20')
    url = f"https://www.myntra.com/{url_query}?rawQuery={raw_query}"
    print(f"[DEBUG] 🌐 Playwright fetching Myntra results for: '{query}' from {url}")
    
    top_products = []
    
    try:
        async with async_playwright() as p:
            # Launch browser with stealth mode
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-gpu',
                    '--disable-infobars',
                    '--window-size=1920,1080',
                    '--start-maximized',
                    '--disable-notifications',
                    '--disable-extensions',
                    '--disable-popup-blocking',
                    '--disable-blink-features',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-web-security',
                    '--disable-features=IsolateOrigins,site-per-process',
                ]
            )
            
            # Create a new context with specific viewport and user agent
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                java_script_enabled=True,
                has_touch=False,
                is_mobile=False,
                locale='en-US',
                timezone_id='America/New_York',
                geolocation={'latitude': 40.7128, 'longitude': -74.0060},
                permissions=['geolocation'],
                extra_http_headers={
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1',
                    'Cache-Control': 'max-age=0'
                }
            )
            
            # Create a new page
            page = await context.new_page()
            
            # Add script to remove webdriver flags
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });
            """)
            
            print(f"[DEBUG] 🚀 Loading page with Playwright...")
            await page.goto(url, wait_until='networkidle', timeout=30000)
            
            # Wait for content to load
            await page.wait_for_load_state('domcontentloaded')
            await asyncio.sleep(3)  # Additional wait for dynamic content
            
            # Get page content
            html_content = await page.content()
            print(f"[DEBUG] 📄 Page loaded, content length: {len(html_content)} characters")
            
            # Check for blocking indicators
            blocking_indicators = [
                "site maintenance", "oops! something went wrong", 
                "access denied", "blocked", "captcha", "security check"
            ]
            
            html_lower = html_content.lower()
            for indicator in blocking_indicators:
                if indicator in html_lower:
                    print(f"[DEBUG] ⚠️ Blocking detected: '{indicator}' found in response")
                    return top_products
            
            # Method 1: Try to extract products from page
            try:
                # Wait for product elements
                await page.wait_for_selector('[data-testid="product-base"], .product-base', timeout=5000)
                
                # Get all product elements
                product_elements = await page.query_selector_all('[data-testid="product-base"], .product-base')
                
                for element in product_elements[:num_results]:
                    try:
                        # Get product name
                        name_element = await element.query_selector('h3, h4, .product-product, [data-testid="product-name"]')
                        name = await name_element.text_content() if name_element else None
                        
                        # Get product image
                        img_element = await element.query_selector('img')
                        img_url = await img_element.get_attribute('src') if img_element else None
                        
                        if name and img_url:
                            if not img_url.startswith('http'):
                                img_url = f"https://assets.myntassets.com/{img_url.lstrip('/')}"
                            
                            top_products.append({
                                'name': name.strip(),
                                'image_url': img_url
                            })
                            print(f"[DEBUG] ✅ Added product: {name}")
                    except Exception as e:
                        print(f"[DEBUG] ⚠️ Error extracting product: {e}")
                        continue
                
            except Exception as e:
                print(f"[DEBUG] ⚠️ Error in product extraction: {e}")
            
            # Method 2: Try to extract from JSON data
            if not top_products:
                try:
                    # Look for JSON data in script tags
                    script_content = await page.evaluate("""
                        () => {
                            const scripts = document.querySelectorAll('script[type="application/json"]');
                            for (const script of scripts) {
                                try {
                                    const data = JSON.parse(script.textContent);
                                    if (data && data.products) {
                                        return JSON.stringify(data.products);
                                    }
                                } catch (e) {}
                            }
                            return null;
                        }
                    """)
                    
                    if script_content:
                        products = json.loads(script_content)
                        for product in products[:num_results]:
                            if 'name' in product and 'image' in product:
                                top_products.append({
                                    'name': product['name'],
                                    'image_url': product['image']
                                })
                                print(f"[DEBUG] ✅ Added product from JSON: {product['name']}")
                except Exception as e:
                    print(f"[DEBUG] ⚠️ Error extracting JSON data: {e}")
            
            # Close browser
            await browser.close()
            
            print(f"[DEBUG] ✅ Playwright found {len(top_products)} products for '{query}'")
            
    except Exception as e:
        print(f"[DEBUG] ❌ Error in Playwright fetch for '{query}': {e}")
        import traceback
        print(f"[DEBUG] Traceback: {traceback.format_exc()}")
    
    return top_products

def fetch_myntra_products_playwright_sync(query, num_results=2):
    """Synchronous wrapper for the async Playwright function"""
    return asyncio.run(fetch_myntra_products_playwright(query, num_results))

def get_recommendations_data(recommendations_data, gender="unisex"):
    """
    Processes recommendations and fetches Myntra products for each item.
    Checks Redis cache first, scrapes if not available, and returns structured results.
    """
    global redis_client
    results = {}
    
    print(f"[DEBUG] Starting sequential get_recommendations_data with gender: {gender}")
    print(f"[DEBUG] Redis client available: {redis_client is not None}")
    
    if not recommendations_data or 'recommendations' not in recommendations_data:
        print("[DEBUG] ❌ No recommendations data found to process.")
        return results

    parsed_recommendations = recommendations_data['recommendations']
    print(f"[DEBUG] Processing {len(parsed_recommendations)} categories")

    for category, items in parsed_recommendations.items():
        if not isinstance(items, list):
            print(f"[DEBUG] ⚠️ Skipping category '{category}' as its value is not a list.")
            continue
            
        # Initialize category in results
        results[category] = []
        print(f"[DEBUG] Processing category '{category}' with {len(items)} items")
        
        for item_idx, item in enumerate(items):
            try:
                clothing_type = item.get('Clothing Type')
                color_str = item.get('Color')
                
                print(f"[DEBUG] Item {item_idx + 1}/{len(items)}: {item}")

                if not clothing_type or not color_str:
                    print(f"[DEBUG] ⚠️ Skipping item due to missing 'Clothing Type' or 'Color': {item}")
                    continue

                # Create item result with original recommendation
                item_result = {
                    'recommendation': item.copy(),
                    'products': []
                }
                
                # Split colors if 'or' is present, otherwise treat as a single color
                colors = [c.strip() for c in re.split(r'\s+or\s+', color_str, flags=re.IGNORECASE)]
                print(f"[DEBUG] Split colors: {colors}")

                for color_idx, color in enumerate(colors):
                    if color.lower() in clothing_type.lower():
                        search_query = f"{clothing_type} for {gender}"
                    else:
                        search_query = f"{color} {clothing_type} for {gender}"
                    
                    print(f"[DEBUG] Color {color_idx + 1}/{len(colors)}: Processing search query: '{search_query}'")

                    # Check Cache First
                    cache_key = f"myntra:{search_query}"
                    
                    if redis_client:
                        print(f"[DEBUG] Checking cache for key: '{cache_key}'")
                        cached_products = get_cache(redis_client, cache_key)
                        
                        if cached_products is not None:
                            # Use cached results directly
                            products = cached_products
                            print(f"[DEBUG] ✅ Cache HIT for '{search_query}' - found {len(products)} products")
                        else:
                            print(f"[DEBUG] 💨 Cache MISS for '{search_query}' - fetching from Myntra")
                            # Try Playwright first
                            products = fetch_myntra_products_playwright_sync(search_query, num_results=2)
                            
                            # If Playwright fails, try fallback method
                            if not products:
                                print(f"[DEBUG] 🔄 Playwright failed, trying fallback method")
                                products = fetch_myntra_products_fallback(search_query, num_results=2)
                            
                            # Cache the results if found
                            if products:
                                print(f"[DEBUG] 💾 Caching {len(products)} products for '{search_query}'")
                                set_cache(redis_client, cache_key, products)
                            else:
                                print(f"[DEBUG] ⚠️ No products to cache for '{search_query}'")
                    else:
                        print(f"[DEBUG] ⚠️ Redis client not available, fetching without cache")
                        # Try Playwright first
                        products = fetch_myntra_products_playwright_sync(search_query, num_results=2)
                        
                        # If Playwright fails, try fallback method
                        if not products:
                            print(f"[DEBUG] 🔄 Playwright failed, trying fallback method")
                            products = fetch_myntra_products_fallback(search_query, num_results=2)
                        
                    # Add products to item result
                    if products:
                        print(f"[DEBUG] ✅ Adding {len(products)} products to results for '{search_query}'")
                        for product in products:
                            item_result['products'].append({
                                'search_query': search_query,
                                'product': product
                            })
                    else:
                        print(f"[DEBUG] ❌ No results found for '{search_query}'.")
                
                # Add item result to category results if products were found
                if item_result['products']:
                    results[category].append(item_result)
                    print(f"[DEBUG] ✅ Added item to category '{category}' with {len(item_result['products'])} products")
                else:
                    print(f"[DEBUG] ⚠️ Skipping item - no products found")
                        
            except Exception as e:
                print(f"[DEBUG] ❌ Error processing item {item}: {e}")
                import traceback
                print(f"[DEBUG] Traceback: {traceback.format_exc()}")
    
    print(f"[DEBUG] ✅ Finished processing. Found results for {len(results)} categories:")
    for cat, items in results.items():
        print(f"[DEBUG]   - {cat}: {len(items)} items with products")
    
    return results

# Example usage (optional, for testing)
if __name__ == "__main__":
    # Example recommendation data structure
    example_data = {
        "recommendations": {
            "Tops/Bottoms": [
                {"Clothing Type": "T-shirt", "Color": "White"},
                {"Clothing Type": "Jeans", "Color": "Blue or Black"}
            ],
            "Footwear": [
                {"Clothing Type": "Sneakers", "Color": "White"}
            ]
        }
    }
    # Run the processing sequentially
    process_recommendations_and_fetch(example_data)
    print("Processing finished.") 