import requests
import re
import html
import threading
from .cache import get_cache, set_cache # Import cache functions

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
    # print(f"[Background Task] Fetching Myntra results for: '{query}' from {url}")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    top_products = []

    try:
        response = requests.get(url, headers=headers, timeout=10) # Added timeout
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

        html_content = response.text

        product_names = re.findall(r'"productName":"(.*?)"', html_content)
        image_urls = re.findall(r'"searchImage":"(.*?)"', html_content)

        if not product_names or not image_urls:
            print(f"[Background Task] No product names or images found for '{query}'.")
            return top_products

        count = 0
        for product_name, img_url in zip(product_names, image_urls):
            if count >= num_results:
                break
                
            decoded_name = html.unescape(product_name).encode('utf-8').decode('unicode_escape')
            decoded_url = html.unescape(img_url).encode('utf-8').decode('unicode_escape')

            # Construct full image URL if necessary
            if decoded_url.startswith('http'):
                full_url = decoded_url
            else:
                full_url = f"https://assets.myntassets.com/{decoded_url.lstrip('/')}"
                
            top_products.append({"name": decoded_name, "image_url": full_url})
            count += 1
            
    except requests.exceptions.RequestException as e:
        print(f"[Background Task] Error fetching Myntra page for '{query}': {e}")
    except Exception as e:
        print(f"[Background Task] An unexpected error occurred during Myntra fetch for '{query}': {e}")
        
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
    
    if not recommendations_data or 'recommendations' not in recommendations_data:
        print("[get_recommendations_data] No recommendations data found to process.")
        return results

    parsed_recommendations = recommendations_data['recommendations']

    for category, items in parsed_recommendations.items():
        if not isinstance(items, list):
            print(f"[get_recommendations_data] Skipping category '{category}' as its value is not a list.")
            continue
            
        # Initialize category in results
        results[category] = []
        
        for item in items:
            try:
                clothing_type = item.get('Clothing Type')
                color_str = item.get('Color')

                if not clothing_type or not color_str:
                    print(f"[get_recommendations_data] Skipping item due to missing 'Clothing Type' or 'Color': {item}")
                    continue

                # Create item result with original recommendation
                item_result = {
                    'recommendation': item.copy(),
                    'products': []
                }
                
                # Split colors if 'or' is present, otherwise treat as a single color
                colors = [c.strip() for c in re.split(r'\s+or\s+', color_str, flags=re.IGNORECASE)]

                for color in colors:
                    if color.lower() in clothing_type.lower():
                        search_query = f"{clothing_type} for {gender}"
                    else:
                        search_query = f"{color} {clothing_type} for {gender}"

                    # Check Cache First
                    cache_key = f"myntra:{search_query}"
                    
                    if redis_client:
                        cached_products = get_cache(redis_client, cache_key)
                        
                        if cached_products is not None:
                            # Use cached results directly
                            products = cached_products
                        else:
                            # Fetch from Myntra if not in cache
                            products = fetch_myntra_products(search_query, num_results=2)
                            # Cache the results if found
                            if products:
                                set_cache(redis_client, cache_key, products)
                    else:
                        # Fetch without cache
                        products = fetch_myntra_products(search_query, num_results=2)
                        
                    # Add products to item result
                    if products:
                        for product in products:
                            item_result['products'].append({
                                'search_query': search_query,
                                'product': product
                            })
                    else:
                        print(f"[get_recommendations_data] No results found for '{search_query}'.")
                
                # Add item result to category results if products were found
                if item_result['products']:
                    results[category].append(item_result)
                        
            except Exception as e:
                print(f"[get_recommendations_data] Error processing item {item}: {e}")
    
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