from pydantic import BaseModel, Field
from typing import Literal

class WardrobeItem(BaseModel):
    id: str = Field(default_factory=str, alias="_id")
    user_id: str
    image_url: str 
    caption: str
    category: Literal["tops", "bottoms", "dresses", "accessories", "outerwear", "others"]

    class Config:
        populate_by_name = True
