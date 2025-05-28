"""Flare related schemas."""

from typing import Optional, List
from datetime import datetime, date
from pydantic import BaseModel, Field, ConfigDict
from geoalchemy2.types import WKBElement


class FlareBase(BaseModel):
    """Base schema for Flare"""
    
    original_id: str = Field(..., description="Original flare ID from data source")
    latitude: float = Field(..., description="Latitude of flare", ge=-90, le=90)
    longitude: float = Field(..., description="Longitude of flare", ge=-180, le=180)
    volume: float = Field(..., description="Flare volume in billion cubic meters (BCM)")
    valid_from: Optional[date] = Field(None, description="Start date when this flare data is valid")
    valid_to: Optional[date] = Field(None, description="End date when this flare data stops being valid")


class FlareCreate(FlareBase):
    """Schema for creating a new flare record"""
    pass


class FlareUpdate(BaseModel):
    """Schema for updating a flare record"""
    
    original_id: Optional[str] = None
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    volume: Optional[float] = None
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None


class FlareResponse(FlareBase):
    """Schema for returning flare data"""
    
    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)
    
    flare_id: str = Field(..., description="Pyxis-generated unique flare identifier")
    h3_index: str = Field(..., description="H3 index at resolution 9")
    created_at: datetime
    updated_at: datetime
    
    # Exclude geometry from serialization as it's binary
    geometry: Optional[WKBElement] = Field(None, exclude=True)


class FlareListResponse(BaseModel):
    """Schema for paginated flare list"""
    
    flares: List[FlareResponse]
    total: int
    page: int
    per_page: int
    pages: int


class FlareUploadResponse(BaseModel):
    """Schema for flare upload response"""
    
    message: str
    processed_records: int
    created_records: int
    updated_records: int
    skipped_records: int
    errors: List[str] = []


class FlareFilter(BaseModel):
    """Schema for flare filtering parameters"""
    
    original_id: Optional[str] = None
    min_volume: Optional[float] = Field(None, ge=0)
    max_volume: Optional[float] = None
    min_lat: Optional[float] = Field(None, ge=-90, le=90)
    max_lat: Optional[float] = Field(None, ge=-90, le=90)
    min_lon: Optional[float] = Field(None, ge=-180, le=180)
    max_lon: Optional[float] = Field(None, ge=-180, le=180)
    valid_date: Optional[date] = Field(None, description="Date to check if flare data is valid")
    h3_index: Optional[str] = None