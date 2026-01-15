"""Flare data schemas"""
from typing import Optional, List
from datetime import date, datetime
import enum
from pydantic import BaseModel, Field, field_validator, ConfigDict,model_validator


class FlareBase(BaseModel):
    """Base schema for flare data"""
    
    original_id: str = Field(..., description="Original flare ID from data source")
    latitude: float = Field(..., description="Latitude of flare", ge=-90, le=90)
    longitude: float = Field(..., description="Longitude of flare", ge=-180, le=180)
    volume: float = Field(..., description="Flare volume in standard cubic meters", ge=0)
    valid_from: Optional[date] = Field(None, description="Start date when flare data is valid")
    valid_to: Optional[date] = Field(None, description="End date when flare data is valid")

class FlareAllocationStrategy(str, enum.Enum):
    """Strategy for allocating flares among competing fields"""
    PRODUCTION_WEIGHTED = "production_weighted"
    EQUAL_SPLIT = "equal_split"

class FlareCreate(FlareBase):
    """Schema for creating a new flare record"""
    pass


class FlareResponse(FlareBase):
    """Schema for flare response"""
    
    model_config = ConfigDict(from_attributes=True)
    
    flare_id: str = Field(..., description="Pyxis-generated unique flare identifier")
    h3_index: str = Field(..., description="H3 index at resolution 9")
    created_at: datetime
    updated_at: datetime


class FlareFilter(BaseModel):
    """Schema for filtering flares"""
    
    original_id: Optional[str] = None
    min_volume: Optional[float] = Field(None, ge=0)
    max_volume: Optional[float] = Field(None, ge=0)
    min_lat: Optional[float] = Field(None, ge=-90, le=90)
    max_lat: Optional[float] = Field(None, ge=-90, le=90)
    min_lon: Optional[float] = Field(None, ge=-180, le=180)
    max_lon: Optional[float] = Field(None, ge=-180, le=180)
    valid_date: Optional[date] = None
    h3_index: Optional[str] = None


class FlareListResponse(BaseModel):
    """Schema for paginated flare list response"""
    
    flares: List[FlareResponse]
    total: int = Field(..., description="Total number of flares matching filter")
    page: int = Field(..., description="Current page number")
    per_page: int = Field(..., description="Number of items per page")
    pages: int = Field(..., description="Total number of pages")


class FlareUploadResponse(BaseModel):
    """Schema for flare upload response"""
    
    message: str
    processed_records: int
    created_records: int
    updated_records: int
    skipped_records: int
    errors: List[str] = Field(default_factory=list)

class FlareAssignmentConfig(BaseModel):
    """Configuration for flare assignment process"""
    
    proximity_distance_km: float = Field(
        100.0, 
        description="Distance in km for H3 k-ring proximity filtering",
        gt=0,
        le=1000
    )
    buffer_distance_km: float = Field(
        5.0,
        description="Buffer distance in km for buffer zone matching", 
        gt=0,
        le=100
    )
    allocation_strategy: FlareAllocationStrategy = Field(
        FlareAllocationStrategy.PRODUCTION_WEIGHTED,
        description="Strategy for allocating flares among competing fields"
    )


class FlareAssignmentRequest(BaseModel):
    """Request schema for flare assignment to fields"""
    
    start_date: date = Field(..., description="Start date for time range filter (YYYY-MM-DD)")
    end_date: date = Field(..., description="End date for time range filter (YYYY-MM-DD)")
    field_ids: Optional[List[int]] = Field(None, description="Optional list of specific field IDs to process")
    country: Optional[str] = Field(None, description="Optional country filter for fields")
    config: FlareAssignmentConfig = Field(default_factory=FlareAssignmentConfig, description="Assignment configuration parameters")
    csv_output_path: Optional[str] = Field(None, description="Local file path to save CSV results (e.g., '/home/user/results.csv')")
    
    @field_validator('end_date')
    @classmethod
    def validate_date_range(cls, end_date, info):
        """Validate that end_date is after start_date"""
        if 'start_date' in info.data and end_date < info.data['start_date']:
            raise ValueError('end_date must be after or equal to start_date')
        return end_date
    
    # Temporarily disabled - this validator is interfering with OpgeeInputRequest
    # @model_validator(mode='after')
    # def validate_field_selection(self):
    #     """Validate that either field_ids or country is provided, but not both"""
    #     if self.field_ids is not None and self.country is not None:
    #         raise ValueError('Provide either field_ids or country, not both')
    #
    #     if self.field_ids is None and self.country is None:
    #         raise ValueError('Must provide either field_ids or country')
    #
    #     return self


class FlareAssignmentStatistics(BaseModel):
    """Statistics from flare assignment process"""
    
    total_fields_processed: int = Field(..., description="Total number of fields processed")
    fields_with_exact_matches: int = Field(..., description="Fields with exact geometry matches") 
    fields_with_buffer_matches: int = Field(..., description="Fields with buffer zone matches")
    fields_with_no_matches: int = Field(..., description="Fields with no flare matches")
    total_flares_assigned: int = Field(..., description="Total flares assigned to fields")
    total_flare_volume_assigned: float = Field(..., description="Total volume assigned to fields")
    processing_time_seconds: float = Field(..., description="Processing time in seconds")

class FlareAssignmentResponse(BaseModel):
    """Response schema for flare assignment"""
    
    statistics: FlareAssignmentStatistics
    csv_file_path: Optional[str] = Field(None, description="Path where CSV file was saved (if csv_output_path provided)")

class FieldFlareMatch(BaseModel):
    """Schema for individual field-flare match result (for detailed responses)"""
    
    field_id: int
    field_name: Optional[str]
    field_country: Optional[str]
    exact_matches: List[str] = Field(..., description="List of flare IDs with exact matches")
    buffer_matches: List[str] = Field(..., description="List of flare IDs with buffer matches")
    total_volume_exact: float = Field(..., description="Total volume from exact matches")
    total_volume_buffer: float = Field(..., description="Total volume from buffer matches")
    total_volume_assigned: float = Field(..., description="Total volume assigned to field")
    match_type: str = Field(..., description="Type of match: 'exact', 'buffer', or 'none'")