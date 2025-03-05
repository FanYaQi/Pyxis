"""Pyxis related apis."""

from fastapi import (
    APIRouter,
)

from .fields import router as fields_router
from .fields_data import router as fields_data_router


router = APIRouter(
    prefix="/pyxis",
    tags=["Pyxis"],
    responses={404: {"description": "Not found"}},
)

router.include_router(fields_router)
router.include_router(fields_data_router)
