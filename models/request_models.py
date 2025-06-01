from pydantic import BaseModel
from typing import List

class FashionRequest(BaseModel):
    description: str
    style: str = "casual"
    gender: str = "unisex"

# Model for Signed URL generation request
class SignedUrlRequest(BaseModel):
    count: int = 1
    content_type: List[str]  

class ImageURLRequest(BaseModel):
    image_url: str


