"""Pyxis field related apis."""

from typing import List

from fastapi import (
    APIRouter,
    Depends,
)
from sqlalchemy.orm import Session

from pyxis_app.dependencies import get_postgres_db
from pyxis_app.postgres.models.pyxis_field import (
    PyxisFieldMeta,
)
from pyxis_app.schemas.pyxis_field import (
    PyxisFieldMetaResponse,
)

router = APIRouter(
    prefix="/fields",
    tags=["Pyxis"],
    responses={404: {"description": "Not found"}},
)


@router.get("/", response_model=List[PyxisFieldMetaResponse])
def list_pyxis_fields(
    db: Session = Depends(get_postgres_db),
    skip: int = 0,
    limit: int = 100,
):
    """List all Pyxis fields."""
    pyxis_fields = db.query(PyxisFieldMeta).offset(skip).limit(limit).all()
    return pyxis_fields
