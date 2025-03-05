"""Data source related apis."""
from typing import List

from fastapi import (
    APIRouter,
    Depends,
)
from sqlalchemy.orm import Session

from pyxis_app.postgres.models.data_source import (
    DataSourceMeta,
)
from pyxis_app.schemas.data_source import (
    DataSourceMetaResponse,
)
from ..dependencies import get_postgres_db

router = APIRouter(
    prefix="/data-sources",
    tags=["data-sources"],
    responses={404: {"description": "Not found"}},
)

@router.get("/", response_model=List[DataSourceMetaResponse])
def list_data_sources(
    db: Session = Depends(get_postgres_db),
    skip: int = 0,
    limit: int = 100,
):
    """List all data sources."""
    data_sources = db.query(DataSourceMeta).offset(skip).limit(limit).all()
    return data_sources

