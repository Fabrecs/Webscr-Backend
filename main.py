from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import signed_urls, webscraping_urls
from dotenv import load_dotenv
from utils.cache import get_redis_client
from utils.background_tasks import set_redis_client
from contextlib import asynccontextmanager
import redis
import requests
import os


load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize Redis client on startup (optional - don't fail if Redis unavailable)
    try:
        app.state.redis_client = get_redis_client()
        
        # Set the Redis client for background tasks
        if app.state.redis_client:
            set_redis_client(app.state.redis_client)
            print("✅ Redis client set for background tasks")
        else:
            print("⚠️ Redis client not available, continuing without it")
    except Exception as e:
        print(f"⚠️ Failed to connect to Redis: {e}. App will continue without Redis.")
        app.state.redis_client = None

    yield

    # Shutdown: close Redis connection
    if hasattr(app.state, 'redis_client') and app.state.redis_client:
        try:
            app.state.redis_client.close()
            print("🔌 Redis connection closed.")
        except redis.exceptions.RedisError as e:
            print(f"⚠️ Error closing Redis connection: {e}")
    # Add other cleanup if needed here

app = FastAPI(lifespan=lifespan)

# Enable CORS for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow frontend requests
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers

app.include_router(signed_urls.router, prefix="/generate-signed-urls", tags=["S3 Signed URLs"])
app.include_router(webscraping_urls.router, prefix="/products", tags=["Products"])

@app.get("/health")
async def health():
    """Simple health check that doesn't depend on external services"""
    return {"status": "healthy", "timestamp": "ok"}

@app.get("/health/ready")
async def readiness():
    """Readiness check that includes Redis connectivity"""
    try:
        # Check if Redis is available (optional)
        if hasattr(app.state, 'redis_client') and app.state.redis_client:
            app.state.redis_client.ping()
        return {"status": "ready", "redis": "connected"}
    except Exception as e:
        return {"status": "not_ready", "redis": "disconnected", "error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)




