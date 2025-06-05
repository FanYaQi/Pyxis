"""Schemas for OPGEE input generation."""

from typing import Optional, List
from datetime import date
from pydantic import BaseModel, Field

from app.schemas.flare import FlareAssignmentConfig


class OpgeeInputRequest(BaseModel):
    """Schema for OPGEE input generation request"""
    
    start_date: date = Field(..., description="Start date for time range filter")
    end_date: date = Field(..., description="End date for time range filter")
    field_ids: Optional[List[int]] = Field(
        None, description="Optional list of specific field IDs to process"
    )
    country: Optional[str] = Field(
        None, description="Optional country filter for fields"
    )
    flare_config: FlareAssignmentConfig = Field(
        default_factory=FlareAssignmentConfig,
        description="Configuration for flare assignment"
    )
    csv_output_path: Optional[str] = Field(
        None, description="Optional local file path to save CSV output"
    )


class OpgeeInputStatistics(BaseModel):
    """Schema for OPGEE input generation statistics"""
    
    total_fields_processed: int = Field(
        ..., description="Total number of fields processed"
    )
    fields_with_data: int = Field(
        ..., description="Number of fields with valid data"
    )
    fields_with_flare_assignment: int = Field(
        ..., description="Number of fields with flare assignments"
    )
    total_flare_volume_assigned: float = Field(
        ..., description="Total flare volume assigned in BCM"
    )
    processing_time_seconds: float = Field(
        ..., description="Total processing time in seconds"
    )
    # Additional statistics
    fields_with_exact_flare_matches: int = Field(
        0, description="Number of fields with exact flare matches"
    )
    fields_with_buffer_flare_matches: int = Field(
        0, description="Number of fields with buffer flare matches"
    )
    fields_with_no_flare_matches: int = Field(
        0, description="Number of fields with no flare matches"
    )


class OpgeeInputResponse(BaseModel):
    """Schema for OPGEE input generation response"""
    
    statistics: OpgeeInputStatistics = Field(
        ..., description="Processing statistics"
    )
    csv_file_path: Optional[str] = Field(
        None, description="Path to generated CSV file if requested"
    )
    message: str = Field(
        "OPGEE input generation completed successfully",
        description="Status message"
    )