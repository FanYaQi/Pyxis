"""Schemas for OPGEE input generation."""

from typing import Optional, List
from datetime import date
from pydantic import BaseModel, Field

from app.schemas.flare import FlareAssignmentConfig
from app.postgres.models.data_source import SourceType


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
    production_type: Optional[str] = Field(
        None, description="Optional filter for fields by production type ('oil' or 'gas')"
    )
    flare_config: FlareAssignmentConfig = Field(
        default_factory=FlareAssignmentConfig,
        description="Configuration for flare assignment"
    )
    csv_output_path: Optional[str] = Field(
        None, description="Optional local file path to save CSV output"
    )
    require_multi_source_coverage: bool = Field(
        True, description="Filter fields by source coverage (default: True for opt-out)"
    )
    min_source_coverage_ratio: float = Field(
        0.5, description="Minimum ratio of sources required (0.0-1.0)", ge=0.0, le=1.0
    )
    trusted_source_types: List[SourceType] = Field(
        default=[SourceType.GOVERNMENT], 
        description="Source types that bypass coverage requirements"
    )


class OpgeeInputStatistics(BaseModel):
    """Schema for OPGEE input generation statistics"""
    
    total_fields_processed: int = Field(
        ..., description="Total number of fields processed after filtering"
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
    total_flaring_sum_scf: float = Field(
        ..., description="Total flaring sum in standard cubic feet (production * FOR)"
    )
    total_flaring_sum_bcm: float = Field(
        ..., description="Total flaring sum in billion cubic meters (production * FOR)"
    )
    production_type: str = Field(
        ..., description="Production type processed ('oil', 'gas', or 'all')"
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
    # Source coverage filtering statistics
    total_fields_before_source_filtering: Optional[int] = Field(
        None, description="Total fields before source coverage filtering"
    )
    fields_filtered_by_source_coverage: Optional[int] = Field(
        None, description="Number of fields filtered out by source coverage"
    )
    fields_with_trusted_source_exception: Optional[int] = Field(
        None, description="Number of fields included via trusted source exception"
    )
    contributing_sources_count: Optional[int] = Field(
        None, description="Total number of sources that contributed field data"
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