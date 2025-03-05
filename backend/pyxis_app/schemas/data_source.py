"""Schemas for data source metadata"""
from typing import Optional, List
from datetime import datetime

from pydantic import BaseModel, Field

from ..postgres.models.data_source import SourceType, DataAccessType


class DataSourceMetaBase(BaseModel):
    """Base schema with common attributes"""

    id: int = Field(..., description="Unique identifier for the data source")
    name: str = Field(..., description="Name of the data source (e.g., ANP, Zhan)")
    description: Optional[str] = Field(
        None, description="Detailed description of the data source"
    )
    urls: Optional[List[str]] = Field(
        None, description="URLs associated with the data source"
    )
    source_type: SourceType = Field(
        ..., description="Type of source (government, paper, commercial, ngo)"
    )
    data_access_type: DataAccessType = Field(
        ..., description="How data is accessed (api, file_upload)"
    )
    reliability_score: Optional[float] = Field(
        None, description="Score for data reliability", ge=0, le=5
    )
    recency_score: Optional[float] = Field(
        None, description="Score for data recency", ge=0, le=5
    )
    richness_score: Optional[float] = Field(
        None, description="Score for data coverage/richness", ge=0, le=5
    )
    pyxis_score: Optional[float] = Field(
        None, description="Overall Pyxis data quality score", ge=0, le=5
    )


class DataSourceMetaCreate(DataSourceMetaBase):
    """Schema for creating a new data source metadata record"""


class DataSourceMetaUpdate(BaseModel):
    """Schema for updating a data source metadata record"""

    id: Optional[int] = None
    name: Optional[str] = None
    description: Optional[str] = None
    urls: Optional[List[str]] = None
    source_type: Optional[SourceType] = None
    data_access_type: Optional[DataAccessType] = None
    reliability_score: Optional[float] = Field(None, ge=0, le=5)
    recency_score: Optional[float] = Field(None, ge=0, le=5)
    richness_score: Optional[float] = Field(None, ge=0, le=5)
    pyxis_score: Optional[float] = Field(None, ge=0, le=5)


class DataSourceMetaResponse(DataSourceMetaBase):
    """Schema for a complete data source metadata record with database fields"""

    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
