"""Flare data API routes."""

import math
from typing import List, Optional
from datetime import date

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    UploadFile,
    File,
    Query,
)

from app.api.deps import CurrentUser, DBSessionDep
from app.schemas.flare import (
    FlareResponse,
    FlareListResponse,
    FlareUploadResponse,
    FlareFilter,
)
from app.services.flare_service import FlareService


router = APIRouter(prefix="/flares", tags=["flares"])


@router.post("/upload", response_model=FlareUploadResponse)
async def upload_flare_data(
    current_user: CurrentUser,
    db: DBSessionDep,
    file: UploadFile = File(..., description="CSV file with flare data"),
    update_existing: bool = Query(True, description="Whether to update existing records"),
):
    """
    Upload flare data from CSV file.
    
    Expected CSV columns:
    - lat: Latitude (float)
    - lon: Longitude (float) 
    - month: Excel serial date or date string
    - id: Original flare ID (string/int)
    - BCM: Volume in billion cubic meters (float)
    """
    # Check file extension
    if not file.filename or not file.filename.lower().endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be a CSV file"
        )
    
    try:
        result = await FlareService.process_csv_file(file, db, update_existing)
        
        return FlareUploadResponse(
            message="Flare data processed successfully",
            **result
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing flare data: {str(e)}"
        ) from e


@router.get("/", response_model=FlareListResponse)
def list_flares(
    current_user: CurrentUser,
    db: DBSessionDep,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=1000, description="Items per page"),
    original_id: Optional[str] = Query(None, description="Filter by original flare ID"),
    min_volume: Optional[float] = Query(None, ge=0, description="Minimum volume (BCM)"),
    max_volume: Optional[float] = Query(None, ge=0, description="Maximum volume (BCM)"),
    min_lat: Optional[float] = Query(None, ge=-90, le=90, description="Minimum latitude"),
    max_lat: Optional[float] = Query(None, ge=-90, le=90, description="Maximum latitude"),
    min_lon: Optional[float] = Query(None, ge=-180, le=180, description="Minimum longitude"),
    max_lon: Optional[float] = Query(None, ge=-180, le=180, description="Maximum longitude"),
    valid_date: Optional[date] = Query(None, description="Date to check validity (YYYY-MM-DD)"),
    h3_index: Optional[str] = Query(None, description="Filter by H3 index"),
):
    """
    List flares with optional filtering and pagination.
    """
    # Create filter object
    filters = FlareFilter(
        original_id=original_id,
        min_volume=min_volume,
        max_volume=max_volume,
        min_lat=min_lat,
        max_lat=max_lat,
        min_lon=min_lon,
        max_lon=max_lon,
        valid_date=valid_date,
        h3_index=h3_index,
    )
    
    # Calculate skip value
    skip = (page - 1) * per_page
    
    # Get flares
    flares, total = FlareService.get_flares(db, filters, skip, per_page)
    
    # Calculate pagination info
    pages = math.ceil(total / per_page) if total > 0 else 1
    
    return FlareListResponse(
        flares=[FlareResponse.model_validate(flare) for flare in flares],
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )


@router.get("/{flare_id}", response_model=FlareResponse)
def get_flare(
    flare_id: str,
    current_user: CurrentUser,
    db: DBSessionDep,
):
    """
    Get a specific flare by ID.
    """
    flare = FlareService.get_flare_by_id(db, flare_id)
    
    if not flare:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Flare with ID {flare_id} not found"
        )
    
    return FlareResponse.model_validate(flare)


@router.delete("/bulk")
def delete_flares_bulk(
    current_user: CurrentUser,
    db: DBSessionDep,
    original_ids: Optional[List[str]] = Query(None, description="Original flare IDs to delete"),
    start_date: Optional[date] = Query(None, description="Start date for validity range"),
    end_date: Optional[date] = Query(None, description="End date for validity range"),
):
    """
    Delete flares by criteria. Useful for re-importing data.
    
    **Warning**: This operation cannot be undone.
    """
    # Require superuser permissions for bulk deletion
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superusers can perform bulk deletions"
        )
    
    # Validate date range
    date_range = None
    if start_date or end_date:
        if not (start_date and end_date):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Both start_date and end_date must be provided for date range filtering"
            )
        if start_date > end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="start_date must be before or equal to end_date"
            )
        date_range = (start_date, end_date)
    
    # At least one filter must be provided
    if not original_ids and not date_range:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one filter (original_ids or date range) must be provided"
        )
    
    try:
        deleted_count = FlareService.delete_flares_by_criteria(
            db, original_ids, date_range
        )
        
        return {
            "message": f"Successfully deleted {deleted_count} flare records",
            "deleted_count": deleted_count
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting flare records: {str(e)}"
        ) from e


@router.get("/statistics/summary")
def get_flare_statistics(
    current_user: CurrentUser,
    db: DBSessionDep,
):
    """
    Get summary statistics for flare data.
    """
    from sqlalchemy import func
    from app.postgres.models.flare import Flare
    
    # Get basic statistics
    stats = db.query(
        func.count(Flare.flare_id).label('total_records'),
        func.count(func.distinct(Flare.original_id)).label('unique_flares'),
        func.min(Flare.volume).label('min_volume'),
        func.max(Flare.volume).label('max_volume'),
        func.avg(Flare.volume).label('avg_volume'),
        func.min(Flare.valid_from).label('earliest_date'),
        func.max(Flare.valid_to).label('latest_date'),
    ).first()
    
    # Get volume distribution
    volume_stats = db.query(
        func.count().label('count')
    ).filter(Flare.volume > 0).first()
    
    zero_volume_count = db.query(func.count()).filter(Flare.volume == 0).first()[0]
    
    return {
        "total_records": stats.total_records,
        "unique_flares": stats.unique_flares,
        "volume_statistics": {
            "min_volume": float(stats.min_volume) if stats.min_volume else 0,
            "max_volume": float(stats.max_volume) if stats.max_volume else 0,
            "avg_volume": float(stats.avg_volume) if stats.avg_volume else 0,
            "records_with_volume": volume_stats.count,
            "records_zero_volume": zero_volume_count,
        },
        "temporal_coverage": {
            "earliest_date": stats.earliest_date,
            "latest_date": stats.latest_date,
        }
    }