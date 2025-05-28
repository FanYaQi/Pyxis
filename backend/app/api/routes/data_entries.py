import json
import uuid
from typing import Optional, Dict, Any
from datetime import date

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    UploadFile,
    File,
    BackgroundTasks,
)
from pydantic import BaseModel, Field, ConfigDict


from app.postgres.models import DataSourceMeta
from app.postgres.models.data_entry import (
    FileExtension,
    DataGranularity,
    DataEntry,
)
from app.schemas.data_entry import DataEntryInfo
from app.services.data_entry_service import validate_data_entry
from app.services.data_entry_service import (
    trigger_data_processing,
    get_data_entry_status,
)
from app.services.data_source_service import check_data_source_access
from app.api.deps import CurrentUser, DBSessionDep


router = APIRouter(prefix="/data-entries", tags=["data-entries"])


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


class DataEntryUploadResponse(BaseModel):
    """Response for data entry upload"""

    data_entry: DataEntryInfo
    message: str = "Data entry uploaded successfully"


@router.post(
    "/", response_model=DataEntryUploadResponse, status_code=status.HTTP_201_CREATED
)
async def upload_data_entry(
    current_user: CurrentUser,
    db: DBSessionDep,
    form_data: DataEntryUploadForm = Depends(),
    data_file: UploadFile = File(...),
    config_file: UploadFile = File(...),
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

    # TODO: Check if the data entry already exists by md5 hash of the data file

    # Determine file extension from filename
    file_extension = None
    if data_file.filename:
        ext = data_file.filename.split(".")[-1].lower()
        try:
            # TODO: Shapefile logic is different
            file_extension = FileExtension(ext)
        except ValueError:
            file_extension = FileExtension.OTHER

    if not file_extension:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file extension",
        )

    # Validate the data entry
    try:
        data_entry = await validate_data_entry(
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

        return DataEntryUploadResponse(
            data_entry=DataEntryInfo.model_validate(data_entry)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing data entry: {str(e)}",
        ) from e


@router.post("/{data_entry_id}/process")
async def process_data_entry(
    data_entry_id: int,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser,
    db: DBSessionDep,
) -> Dict[str, Any]:
    """
    Trigger processing of a data entry.

    Args:
        data_entry_id: ID of the data entry to process
        background_tasks: FastAPI background tasks
        current_user: Current authenticated user
        db: Database session

    Returns:
        Dict with processing status
    """
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

    # Trigger processing
    result = await trigger_data_processing(data_entry, background_tasks, db)

    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["message"],
        )

    return result


@router.get("/{data_entry_id}/status")
async def get_processing_status(
    data_entry_id: int,
    current_user: CurrentUser,
    db: DBSessionDep,
) -> Dict[str, Any]:
    """
    Get the processing status of a data entry.

    Args:
        data_entry_id: ID of the data entry
        current_user: Current authenticated user
        db: Database session

    Returns:
        Dict with processing status
    """
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

    # Get status
    status_result = await get_data_entry_status(data_entry_id, db)

    if not status_result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=status_result["message"],
        )

    return status_result
