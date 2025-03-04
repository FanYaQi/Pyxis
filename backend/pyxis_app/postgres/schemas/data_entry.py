# backend/pyxis_app/postgres/schemas/data_entry.py
from typing import Optional, Any, Dict, List
from datetime import datetime
from pydantic import BaseModel, Field

# Import enums from models
from ..models.data_entry import FileExtension, DataGranularity, ProcessingStatus


class DataEntryBase(BaseModel):
    """Base schema with common attributes"""
    source_id: str = Field(..., description="ID of the data source this entry belongs to")
    alias: str = Field(..., description="Human-readable identifier for this data entry")
    file_extension: FileExtension = Field(..., description="File extension type")
    granularity: DataGranularity = Field(..., description="Granularity level of the data")
    file_name: Optional[str] = Field(None, description="Original filename or archive name")
    config_file: Optional[Dict[str, Any]] = Field(None, description="Configuration/mapping information")
    version: Optional[str] = Field(None, description="Version of the dataset")
    contained_files: Optional[List[str]] = Field(None, description="List of filenames within the archive")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class DataEntryCreate(DataEntryBase):
    """Schema for creating a new data entry"""
    # Used for file upload, the actual file will be handled separately
    pass


class DataEntryUpdate(BaseModel):
    """Schema for updating a data entry"""
    alias: Optional[str] = None
    file_extension: Optional[FileExtension] = None
    granularity: Optional[DataGranularity] = None
    config_file: Optional[Dict[str, Any]] = None
    version: Optional[str] = None
    status: Optional[ProcessingStatus] = None
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    contained_files: Optional[List[str]] = None


class DataEntryResponse(DataEntryBase):
    """Schema for a complete data entry record with database fields"""
    id: int
    file_size: Optional[int] = None
    raw_data_md5: Optional[str] = None
    config_file_md5: Optional[str] = None
    upload_date: datetime
    status: ProcessingStatus
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True


class DataEntryFile(BaseModel):
    """Schema for handling file uploads"""
    file_contents: bytes
    file_name: str