# backend/pyxis_app/routers/data_entries.py
import json
import uuid
from typing import Optional, Dict, Any, Annotated

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, ConfigDict, Json

from pyxis_app.dependencies import get_postgres_db
from pyxis_app.postgres.models import User, DataSourceMeta
from pyxis_app.postgres.models.data_entry import (
    FileExtension,
    DataGranularity,
)
from pyxis_app.schemas.data_entry import DataEntryResponse
from pyxis_app.services.data_entry_service import process_data_entry
from pyxis_app.auth.utils import get_current_user


router = APIRouter(
    prefix="/data-entries",
    tags=["Data Entry"],
    responses={404: {"description": "Not found"}},
)


class DataEntryUploadForm(BaseModel):
    """Form data for uploading a data entry"""

    source_id: int = Field(..., description="ID of the data source")
    granularity: DataGranularity = Field(..., description="Level of data granularity")
    alias: Optional[str] = Field(
        None, description="Human-readable name for the data entry"
    )
    additional_metadata: Optional[str] = Field(
        None, description="Additional metadata(json format)"
    )

    model_config = ConfigDict(extra="forbid")


@router.post("/", response_model=DataEntryResponse, status_code=status.HTTP_201_CREATED)
async def upload_data_entry(
    form_data: DataEntryUploadForm = Depends(),
    data_file: UploadFile = File(...),
    config_file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_postgres_db),
):
    """
    Upload a new data entry with data file and config file.

    This endpoint accepts multipart form data with:
    - source_id: ID of the data source
    - granularity: Level of data granularity (field, well, etc.)
    - alias: (Optional) Human-readable name for the data entry
    - additional_metadata: (Optional) JSON object with additional metadata
    - data_file: The data file (CSV, etc.)
    - config_file: JSON configuration file for mapping data
    """
    additional_metadata: Optional[Dict[str, Any]] = None
    if form_data.additional_metadata:
        try:
            additional_metadata = json.loads(form_data.additional_metadata)
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid JSON format for additional metadata: {str(e)}",
            ) from e

    # Check if source exists and user has access
    data_source = (
        db.query(DataSourceMeta)
        .filter(DataSourceMeta.id == form_data.source_id)
        .first()
    )
    if not data_source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Data source not found"
        )

    # Check if user has access to the data source
    if current_user not in data_source.users and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this data source",
        )

    # Generate record_id and version
    record_id = str(uuid.uuid4())
    version = "1.0.0"  # Initial version

    # Determine file extension from filename
    file_extension = None
    if data_file.filename:
        ext = data_file.filename.split(".")[-1].lower()
        try:
            file_extension = FileExtension(ext)
        except ValueError:
            file_extension = FileExtension.OTHER

    if not file_extension:
        file_extension = FileExtension.OTHER

    # Process the data entry
    try:
        data_entry = await process_data_entry(
            db=db,
            source_id=form_data.source_id,
            record_id=record_id,
            version=version,
            alias=form_data.alias
            or data_file.filename
            or "",  # Use filename as alias if not provided
            granularity=form_data.granularity,
            file_extension=file_extension,
            data_file=data_file,
            config_file=config_file,
            additional_metadata=additional_metadata,
        )

        return data_entry
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing data entry: {str(e)}",
        ) from e
