"""Pyxis field related apis."""

from typing import List

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.orm import Session

from pyxis_app.dependencies import get_postgres_db
from pyxis_app.postgres.models.user import User
from pyxis_app.postgres.models.data_entry import DataEntry
from pyxis_app.postgres.models.pyxis_field import (
    PyxisFieldData,
)
from pyxis_app.schemas.pyxis_field import (
    PyxisFieldDataResponse,
)
from pyxis_app.routers.auth import get_current_user
from pyxis_app.services.data_source_service import check_data_source_access

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


@router.get(
    "/by-data-entry/{data_entry_id}", response_model=List[PyxisFieldDataResponse]
)
async def list_pyxis_field_data_by_data_entry(
    data_entry_id: int,
    db: Session = Depends(get_postgres_db),
    current_user: User = Depends(get_current_user),
    skip: int = 0,
    limit: int = 100,
):
    """List all Pyxis field data for a specific data entry."""
    # Check if data entry exists
    data_entry = db.query(DataEntry).filter(DataEntry.id == data_entry_id).first()
    if not data_entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data entry with ID {data_entry_id} not found",
        )

    # Check if user has access to the data source
    has_access = await check_data_source_access(data_entry.source_id, current_user, db)
    if not has_access and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this data entry's source",
        )

    # Query the field data
    pyxis_field_data = (
        db.query(PyxisFieldData)
        .filter(PyxisFieldData.data_entry_id == data_entry_id)
        .offset(skip)
        .limit(limit)
        .all()
    )

    return pyxis_field_data
