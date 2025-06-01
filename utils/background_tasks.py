import requests
import re
import html
import threading
import os
from .cache import get_cache, set_cache # Import cache functions

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

def fetch_myntra_products(query, num_results=2):
    """Fetches product details from Myntra based on a query and returns top results."""
    url_query = query.replace(' ', '-')
    raw_query = query.replace(' ', '%20')
    url = f"https://www.myntra.com/{url_query}?rawQuery={raw_query}"
    print(f"[DEBUG] Fetching Myntra results for: '{query}' from {url}")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
        "Referer": "https://www.google.com/"
    }
    
    # Optional proxy configuration (add to .env file)
    proxies = None
    proxy_url = os.getenv('PROXY_URL')  # e.g., "http://username:password@proxy-server:port"
    if proxy_url:
        proxies = {
            'http': proxy_url,
            'https': proxy_url
        }
        print(f"[DEBUG] Using proxy: {proxy_url}")
    
    top_products = []

    try:
        print(f"[DEBUG] Making request to: {url}")
        print(f"[DEBUG] Request headers: {headers}")
        
        # Add session with retry strategy
        session = requests.Session()
        
        response = session.get(url, headers=headers, proxies=proxies, timeout=15)
        
        print(f"[DEBUG] Response status code: {response.status_code}")
        print(f"[DEBUG] Response headers: {dict(response.headers)}")
        print(f"[DEBUG] Response URL (after redirects): {response.url}")
        
        response.raise_for_status()

        html_content = response.text
        print(f"[DEBUG] Response content length: {len(html_content)} characters")
        
        # Log first 500 characters of HTML content
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
        
        # Look for specific Myntra indicators
        if "myntra" not in html_lower or len(html_content) < 1000:
            print(f"[DEBUG] ⚠️ Response seems invalid - too short or missing Myntra content")
            return top_products
        
        # Debug regex patterns
        print(f"[DEBUG] Searching for product names with pattern: '\"productName\":\"(.*?)\"'")
        product_names = re.findall(r'"productName":"(.*?)"', html_content)
        print(f"[DEBUG] Found {len(product_names)} product names: {product_names[:5]}")
        
        print(f"[DEBUG] Searching for image URLs with pattern: '\"searchImage\":\"(.*?)\"'")
        image_urls = re.findall(r'"searchImage":"(.*?)"', html_content)
        print(f"[DEBUG] Found {len(image_urls)} image URLs: {image_urls[:5]}")

        # Alternative regex patterns to try
        if not product_names:
            print(f"[DEBUG] Trying alternative product name patterns...")
            alt_product_names = re.findall(r'"name":"(.*?)"', html_content)
            print(f"[DEBUG] Alternative pattern found {len(alt_product_names)} names: {alt_product_names[:5]}")
            
            title_pattern = re.findall(r'"title":"(.*?)"', html_content)
            print(f"[DEBUG] Title pattern found {len(title_pattern)} titles: {title_pattern[:5]}")

        if not image_urls:
            print(f"[DEBUG] Trying alternative image URL patterns...")
            alt_images = re.findall(r'"image":"(.*?)"', html_content)
            print(f"[DEBUG] Alternative image pattern found {len(alt_images)} images: {alt_images[:5]}")
            
            src_pattern = re.findall(r'"src":"(.*?)"', html_content)
            print(f"[DEBUG] Src pattern found {len(src_pattern)} sources: {src_pattern[:5]}")

        if not product_names or not image_urls:
            print(f"[DEBUG] ❌ No product names or images found for '{query}'.")
            # Save a snippet of HTML for debugging
            with open(f"/tmp/myntra_debug_{query.replace(' ', '_')}.html", "w", encoding="utf-8") as f:
                f.write(html_content[:10000])
            print(f"[DEBUG] Saved HTML snippet to /tmp/myntra_debug_{query.replace(' ', '_')}.html")
            return top_products

        count = 0
        for product_name, img_url in zip(product_names, image_urls):
            if count >= num_results:
                break
                
            print(f"[DEBUG] Processing product {count + 1}: '{product_name}' with image: '{img_url}'")
            
            decoded_name = html.unescape(product_name).encode('utf-8').decode('unicode_escape')
            decoded_url = html.unescape(img_url).encode('utf-8').decode('unicode_escape')

            print(f"[DEBUG] Decoded name: '{decoded_name}'")
            print(f"[DEBUG] Decoded URL: '{decoded_url}'")

            # Construct full image URL if necessary
            if decoded_url.startswith('http'):
                full_url = decoded_url
            else:
                full_url = f"https://assets.myntassets.com/{decoded_url.lstrip('/')}"
            
            print(f"[DEBUG] Final image URL: '{full_url}'")
                
            top_products.append({"name": decoded_name, "image_url": full_url})
            count += 1
        
        print(f"[DEBUG] ✅ Successfully found {len(top_products)} products for '{query}'")
            
    except requests.exceptions.RequestException as e:
        print(f"[DEBUG] ❌ RequestException for '{query}': {e}")
        print(f"[DEBUG] Exception type: {type(e).__name__}")
    except Exception as e:
        print(f"[DEBUG] ❌ Unexpected error for '{query}': {e}")
        print(f"[DEBUG] Exception type: {type(e).__name__}")
        import traceback
        print(f"[DEBUG] Traceback: {traceback.format_exc()}")
        
    return top_products

def process_recommendations_and_fetch(recommendations_data, gender="unisex"):
    """Processes recommendations and fetches top 2 Myntra products for each item."""
    global redis_client
    # print("[Background Task] Starting recommendation processing...")
    if not recommendations_data or 'recommendations' not in recommendations_data:
        print("[Background Task] No recommendations data found to process.")
        return

    parsed_recommendations = recommendations_data['recommendations']

    for category, items in parsed_recommendations.items():
        if not isinstance(items, list):
            print(f"[Background Task] Skipping category '{category}' as its value is not a list.")
            continue
            
        # print(f"[Background Task] Processing category: {category}")
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
                        # print(f"\n[Background Task] Searching for: {search_query} (color already in type)")
                    else:
                        search_query = f"{color} {clothing_type} for {gender}"
                        # print(f"\n[Background Task] Searching for: {search_query}")

                    # --- Check Cache First ---
                    cache_key = f"myntra:{search_query}"
                    
                    if redis_client:
                        cached_products = get_cache(redis_client, cache_key)
                        
                        if cached_products is not None:
                            # Use cached results directly
                            products = cached_products
                            # print(f"[Background Task] Using cached results for '{search_query}'.")
                        else:
                            # Fetch from Myntra if not in cache
                            products = fetch_myntra_products(search_query, num_results=2)
                            # Cache the results if found
                            if products:
                                set_cache(redis_client, cache_key, products)
                    else:
                        # print("[Background Task] Redis client not available, skipping cache")
                        products = fetch_myntra_products(search_query, num_results=2)
                    # --- End Cache Check ---
                        
                    if products:
                        pass
                        # print(f"[Background Task] Top {len(products)} results for '{search_query}':")
                        # for i, product in enumerate(products, 1):
                            # print(f"  {i}. Name: {product['name']}")
                            # print(f"     Image: {product['image_url']}")
                    else:
                        print(f"[Background Task] No results found for '{search_query}'.")
                        
            except Exception as e:
                print(f"[Background Task] Error processing item {item}: {e}")

    # print("[Background Task] Finished processing recommendations.")

def get_recommendations_data(recommendations_data , gender="unisex"):
    """
    Processes recommendations and fetches Myntra products for each item.
    Checks Redis cache first, scrapes if not available, and returns structured results.
    """
    global redis_client
    results = {}
    
    print(f"[DEBUG] Starting get_recommendations_data with gender: {gender}")
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
                            # Fetch from Myntra if not in cache
                            products = fetch_myntra_products(search_query, num_results=2)
                            # Cache the results if found
                            if products:
                                print(f"[DEBUG] 💾 Caching {len(products)} products for '{search_query}'")
                                set_cache(redis_client, cache_key, products)
                            else:
                                print(f"[DEBUG] ⚠️ No products to cache for '{search_query}'")
                    else:
                        print(f"[DEBUG] ⚠️ Redis client not available, fetching without cache")
                        # Fetch without cache
                        products = fetch_myntra_products(search_query, num_results=2)
                        
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
    # Run the processing in a separate thread like the main app would
    thread = threading.Thread(target=process_recommendations_and_fetch, args=(example_data,))
    thread.start()
    thread.join() # Wait for the thread to finish in this example
    print("Main thread finished.") 