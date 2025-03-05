import os
import json
import uuid
import hashlib
from typing import List, Optional
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    UploadFile,
    File,
    Form,
    BackgroundTasks,
    status,
)
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from .auth import get_current_user
from ..services.data_source_service import check_data_source_access
from ..postgres.models import DataSourceMeta, User, DataEntry
from ..postgres.models.data_entry import (
    FileExtension,
    DataGranularity,
    ProcessingStatus,
)
from ..schemas.data_entry import DataEntryResponse
from ..dependencies import get_postgres_db
from ..utils.config_validator import validate_config


router = APIRouter(
    prefix="/data-entries",
    tags=["Data Entry"],
    responses={404: {"description": "Not found"}},
)


# Modify the list_data_entries function
@router.get("/", response_model=List[DataEntryResponse])
async def list_data_entries(
    skip: int = 0,
    limit: int = 100,
    processing_status: Optional[ProcessingStatus] = None,
    source_id: Optional[str] = None,
    db: Session = Depends(get_postgres_db),
    current_user: User = Depends(get_current_user),
):
    """List all data entries with optional filtering"""
    query = db.query(DataEntry)

    if processing_status:
        query = query.filter(DataEntry.status == processing_status)

    if source_id:
        # Check if user has access to this data source
        has_access = await check_data_source_access(source_id, current_user, db)
        if not has_access:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this data source",
            )
        query = query.filter(DataEntry.source_id == source_id)
    elif not current_user.is_superuser:
        # Non-superusers only see entries from their accessible data sources
        query = query.join(DataSourceMeta).filter(
            DataSourceMeta.users.any(id=current_user.id)
        )

    data_entries = query.offset(skip).limit(limit).all()
    return data_entries


@router.get("/{entry_id}", response_model=DataEntryResponse)
async def get_data_entry(entry_id: int, db: Session = Depends(get_postgres_db)):
    """Get details for a specific data entry"""
    data_entry = db.query(DataEntry).filter(DataEntry.id == entry_id).first()
    if data_entry is None:
        raise HTTPException(status_code=404, detail="Data entry not found")
    return data_entry


@router.get("/{entry_id}/status")
async def get_processing_status(entry_id: int, db: Session = Depends(get_postgres_db)):
    """Get the processing status of a data entry"""
    data_entry = db.query(DataEntry).filter(DataEntry.id == entry_id).first()
    if data_entry is None:
        raise HTTPException(status_code=404, detail="Data entry not found")

    return {
        "id": data_entry.id,
        "status": data_entry.status,
        "error_message": data_entry.error_message,
        "updated_at": data_entry.updated_at,
    }


# @router.post("/", response_model=DataEntryResponse, status_code=status.HTTP_201_CREATED)
# async def create_data_entry(
#     background_tasks: BackgroundTasks,
#     file: UploadFile = File(...),
#     config: str = Form(...),
#     source_id: str = Form(...),
#     alias: str = Form(...),
#     data_entry_id: Optional[str] = Form(None),
#     version: str = Form("1.0"),
#     granularity: DataGranularity = Form(DataGranularity.FIELD),
#     db: Session = Depends(get_postgres_db),
# ):
#     """Upload a new data file with config and create a data entry"""
#     try:
#         # Generate a unique data_entry_id if not provided
#         if not data_entry_id:
#             data_entry_id = str(uuid.uuid4())

#         # Parse config
#         try:
#             config_json = json.loads(config)
#         except json.JSONDecodeError as e:
#             raise HTTPException(status_code=400, detail="Invalid JSON in config") from e

#         # Validate config
#         validation_result = validate_config(config_json)
#         if not validation_result["valid"]:
#             raise HTTPException(
#                 status_code=400,
#                 detail=f"Config validation failed: {validation_result['errors']}",
#             )

#         # Read file data and calculate MD5
#         file_data = await file.read()
#         file_md5 = hashlib.md5(file_data).hexdigest()

#         # Get file extension
#         _, file_ext = os.path.splitext(file.filename)
#         file_ext = file_ext.lstrip(".").lower()

#         # Convert to supported FileExtension enum
#         try:
#             file_extension = FileExtension(file_ext)
#         except ValueError:
#             # Default to OTHER if not in enum
#             file_extension = FileExtension.OTHER

#         # TODO: Create data entry
#         data_entry = DataEntry(
#             source_id=source_id,
#             data_entry_id=data_entry_id,
#             version=version,
#             alias=alias,
#             file_extension=file_extension,
#             granularity=granularity,
#             file_name=file.filename,
#             file_size=len(file_data),
#             raw_data=file_data,
#             raw_data_md5=file_md5,
#             config_file=config_json,
#             config_file_md5=hashlib.md5(config.encode()).hexdigest(),
#             status=ProcessingStatus.PENDING,
#         )

#         # Save to database
#         db.add(data_entry)
#         db.commit()
#         db.refresh(data_entry)

#         # TODO: Add background processing task here
#         # background_tasks.add_task(process_data_entry, data_entry.id)

#         return data_entry

#     except SQLAlchemyError as e:
#         db.rollback()
#         raise HTTPException(status_code=500, detail=f"Database error: {str(e)}") from e
#     except Exception as e:
#         raise HTTPException(
#             status_code=500, detail=f"Error creating data entry: {str(e)}"
#         ) from e


# @router.post("/{entry_id}/process")
# async def trigger_processing(
#     entry_id: int,
#     background_tasks: BackgroundTasks,
#     db: Session = Depends(get_postgres_db),
# ):
#     """Manually trigger processing for a data entry"""
#     data_entry = db.query(DataEntry).filter(DataEntry.id == entry_id).first()
#     if data_entry is None:
#         raise HTTPException(status_code=404, detail="Data entry not found")

#     if data_entry.status == ProcessingStatus.PROCESSING:
#         raise HTTPException(
#             status_code=400, detail="Data entry is already being processed"
#         )

#     # Update status to PROCESSING
#     data_entry.status = ProcessingStatus.PROCESSING
#     db.commit()

#     # TODO: Add background processing task here
#     # background_tasks.add_task(process_data_entry, data_entry.id)

#     return {"message": "Processing started", "id": data_entry.id}
