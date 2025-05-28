from typing import Optional, Any, Dict, List
from datetime import datetime, date
from pydantic import BaseModel, Field, ConfigDict

from app.postgres.models.data_entry import (
    FileExtension,
    DataGranularity,
    ProcessingStatus,
)


class DataEntryInfo(BaseModel):
    """Schema for data entry information"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: int = Field(
        ..., description="ID of the data source this entry belongs to"
    )
    record_id: str = Field(..., description="Record ID for this data entry")
    version: str = Field(..., description="Version of the dataset")
    alias: str = Field(..., description="Human-readable identifier for this data entry")
    granularity: DataGranularity = Field(
        ..., description="Granularity level of the data"
    )
    file_name: Optional[str] = Field(
        None, description="Original filename or archive name"
    )
    file_extension: FileExtension = Field(..., description="File extension type")
    file_size: Optional[int] = Field(None, description="Size of the file in bytes")
    contained_files: Optional[List[str]] = Field(
        None, description="List of filenames within the archive"
    )
    raw_data_md5: Optional[str] = None
    config_file_md5: Optional[str] = None
    status: ProcessingStatus
    additional_metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional metadata for the entry"
    )
    created_at: datetime
    updated_at: datetime
