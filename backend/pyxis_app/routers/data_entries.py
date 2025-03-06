"""
Data entries router
"""

from fastapi import (
    APIRouter,
)


router = APIRouter(
    prefix="/data-entries",
    tags=["Data Entry"],
    responses={404: {"description": "Not found"}},
)
