# Pydantic models.
from typing import Any

from pydantic import BaseModel


# Generic message
class Message(BaseModel):
    message: str


# Generic response
class Response(BaseModel):
    message: str
    data: Any
