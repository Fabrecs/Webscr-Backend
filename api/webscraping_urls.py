import threading
from utils.background_tasks import get_recommendations_data
from fastapi import APIRouter, Request
from utils.background_tasks import process_recommendations_and_fetch

router = APIRouter()

@router.post("/references-scrape")
async def webscraping_references(request: Request):
    body = await request.json()
    recommendations = body.get("recommendations")
    gender = body.get("gender")
    thread = threading.Thread(target=process_recommendations_and_fetch, args=(recommendations, gender))
    thread.start()
    return {"message": "Recommendations are being processed in the background"}

@router.post("/references")
async def webscraping_references(request: Request):
    body = await request.json()
    recommendations = body.get("recommendations")
    gender = body.get("gender")
    recommendations_data = {
        "recommendations": recommendations,
    }
    return get_recommendations_data(recommendations_data, gender)















