"""Pyxis field related apis."""

from typing import List

from fastapi import (
    APIRouter,
    Depends,
)
from sqlalchemy.orm import Session

from pyxis_app.dependencies import get_postgres_db
from pyxis_app.postgres.models.pyxis_field import (
    PyxisFieldData,
)
from pyxis_app.schemas.pyxis_field import (
    PyxisFieldDataResponse,
)

router = APIRouter(
    prefix="/fields-data",
    tags=["Pyxis"],
    responses={404: {"description": "Not found"}},
)


@router.get("/", response_model=List[PyxisFieldDataResponse])
def list_pyxis_field_data(
    db: Session = Depends(get_postgres_db),
    skip: int = 0,
    limit: int = 10,
):
    """List all Pyxis fields data."""
    pyxis_field_data = db.query(PyxisFieldData).offset(skip).limit(limit).all()
    return pyxis_field_data
