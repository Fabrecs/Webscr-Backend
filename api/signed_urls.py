from fastapi import APIRouter, HTTPException
from typing import List
from models.request_models import SignedUrlRequest
from services.s3_service import S3Service

router = APIRouter()


s3_service = S3Service()


@router.post("/", response_model=List[str], tags=["S3 Signed URLs"])
async def generate_s3_signed_urls(request: SignedUrlRequest):
    """
    Generates one or more presigned PUT URLs for uploading files to S3.

    - **count**: Number of signed URLs to generate (default: 1).
    """
    print(request)
    try:
        presigned_urls = s3_service.generate_presigned_urls(count=request.count, content_type=request.content_type)
        return presigned_urls
    except ValueError as e:
        # Handle specific errors from the service (e.g., invalid count, S3 not configured)
        raise HTTPException(status_code=400, detail=str(e))
    except ConnectionError as e:
        # Handle errors during S3 communication
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        # Catch any other unexpected errors
        print(f"Unexpected error in generate_s3_signed_urls endpoint: {e}")
        raise HTTPException(status_code=500, detail="An internal server error occurred.") 