"""
OPGEE input generation API routes.
"""

import logging
from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DBSessionDep
from app.schemas.opgee import OpgeeInputRequest, OpgeeInputResponse, OpgeeInputStatistics
from app.services.opgee_service import OpgeeService


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/opgee", tags=["opgee"])


@router.post("/generate-input", response_model=OpgeeInputResponse)
async def generate_opgee_input(
    request: OpgeeInputRequest,
    current_user: CurrentUser,
    db: DBSessionDep,
) -> OpgeeInputResponse:
    """
    Generate OPGEE-compatible input data by merging field data and flare assignments.
    
    This endpoint:
    1. Retrieves fields based on field_ids or country filter
    2. Assigns flares to fields using spatial and temporal criteria
    3. Merges field attributes using time-weighted processing for dynamic attributes
    4. Calculates Flaring-to-Oil Ratio (FOR) from flare volumes and oil production
    5. Optionally generates CSV file with OPGEE input data
    
    Args:
        request: OPGEE input generation request parameters
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        OpgeeInputResponse with processing statistics and optional CSV file path
        
    Raises:
        HTTPException: If validation fails or processing errors occur
    """
    try:
        # Validate request parameters
        if not request.field_ids and not request.country:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Must provide either field_ids or country parameter"
            )
        
        if request.start_date > request.end_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="start_date must be before or equal to end_date"
            )
        
        logger.info(
            f"User {current_user.email} requested OPGEE input generation for "
            f"{request.start_date} to {request.end_date}"
        )
        
        # Generate OPGEE input
        statistics_dict, csv_file_path = OpgeeService.generate_opgee_input(
            start_date=request.start_date,
            end_date=request.end_date,
            db=db,
            field_ids=request.field_ids,
            country=request.country,
            flare_config=request.flare_config,
            csv_output_path=request.csv_output_path,
            require_multi_source_coverage=request.require_multi_source_coverage,
            min_source_coverage_ratio=request.min_source_coverage_ratio,
            trusted_source_types=request.trusted_source_types
        )
        
        # Create response
        statistics = OpgeeInputStatistics(**statistics_dict)
        
        response = OpgeeInputResponse(
            statistics=statistics,
            csv_file_path=csv_file_path,
            message=f"Successfully processed {statistics.total_fields_processed} fields"
        )
        
        logger.info(
            f"OPGEE input generation completed for user {current_user.email}: "
            f"{statistics.fields_with_data} fields processed in "
            f"{statistics.processing_time_seconds:.2f} seconds"
        )
        
        return response
        
    except ValueError as e:
        logger.error(f"Validation error in OPGEE input generation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) from e
        
    except Exception as e:
        logger.error(f"Unexpected error in OPGEE input generation: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating OPGEE input: {str(e)}"
        ) from e


@router.get("/attributes", response_model=dict)
async def get_opgee_attributes(
    current_user: CurrentUser,
) -> dict:
    """
    Get list of all OPGEE-compatible attributes that can be processed.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Dict with list of available OPGEE attributes and their processing rules
    """
    try:
        from app.utils.merge_utils import load_merge_rules
        
        merge_rules = load_merge_rules()
        
        return {
            "attributes": list(merge_rules.keys()),
            "rules": merge_rules,
            "total_attributes": len(merge_rules)
        }
        
    except Exception as e:
        logger.error(f"Error loading OPGEE attributes: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error loading OPGEE attributes: {str(e)}"
        ) from e