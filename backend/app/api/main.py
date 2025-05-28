"""Main api router."""
from app.configs.settings import settings
from fastapi import (
    APIRouter,
)

from .routes import (
    users,
    login,
    data_sources,
    data_entries,
    database,
    fields_data,
    flare,
    private,
)


router = APIRouter()

router.include_router(database.router)
router.include_router(users.router)
router.include_router(login.router)
router.include_router(data_sources.router)
router.include_router(data_entries.router)
router.include_router(fields_data.router)
router.include_router(flare.router)


if settings.ENVIRONMENT == "local":
    router.include_router(private.router)
