import redis
import os
from dotenv import load_dotenv
import json

# Load environment variables from .env file
load_dotenv()

# --- Redis Configuration ---
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None) # Add REDIS_PASSWORD to .env if needed

# --- Redis Cache TTL ---
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", 3600)) # Default to 1 hour

def get_redis_client() -> redis.StrictRedis | None:
    """Initializes and returns a Redis client connection."""
    try:
        client = redis.StrictRedis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            password=REDIS_PASSWORD,
            decode_responses=True # Decode responses to strings automatically
        )
        client.ping() # Check connection
        print(f"✅ Attempting Redis connection to {REDIS_HOST}:{REDIS_PORT} (will confirm success in lifespan)")
        return client
    except redis.exceptions.ConnectionError as e:
        print(f"❌ Failed to connect to Redis at {REDIS_HOST}:{REDIS_PORT} - {e}")
        return None
    except Exception as e:
        print(f"❌ An unexpected error occurred during Redis connection: {e}")
        return None

# Initialize the client globally so it's created once on module import
# redis_client = get_redis_client()

def set_cache(redis_client: redis.StrictRedis, key: str, value: list | dict, expiration_seconds: int = CACHE_TTL_SECONDS):
    """Sets a value in the Redis cache with an expiration time."""
    if not redis_client:
        print("⚠️ Redis client not available (from app state). Skipping cache set.")
        return False
    try:
        # Serialize the value to JSON string before storing
        json_value = json.dumps(value)
        redis_client.setex(key, expiration_seconds, json_value)
        print(f"💾 Cached data in Redis with key: {key} (TTL: {expiration_seconds}s)")
        return True
    except redis.exceptions.RedisError as e:
        print(f"⚠️ Redis Error: Failed to set cache for key '{key}' - {e}")
        return False
    except TypeError as e:
         print(f"⚠️ TypeError: Could not serialize value for key '{key}' to JSON - {e}")
         return False

def get_cache(redis_client: redis.StrictRedis, key: str) -> list | dict | None:
    """Gets a value from the Redis cache."""
    if not redis_client:
        print("⚠️ Redis client not available (from app state). Skipping cache get.")
        return None
    try:
        cached_value = redis_client.get(key)
        if cached_value:
            print(f"📦 Cache hit for key: {key}")
            # Deserialize the JSON string back to Python object
            return json.loads(cached_value)
        else:
            print(f"💨 Cache miss for key: {key}")
            return None
    except redis.exceptions.RedisError as e:
        print(f"⚠️ Redis Error: Failed to get cache for key '{key}' - {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"⚠️ JSON Error: Could not deserialize cached value for key '{key}' - {e}")
        # Optionally delete the invalid key
        # try:
        #     redis_client.delete(key)
        #     print(f"🗑️ Deleted invalid cache key: {key}")
        # except redis.exceptions.RedisError:
        #     pass # Ignore deletion error
        return None 