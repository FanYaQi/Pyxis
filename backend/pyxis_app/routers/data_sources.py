"""
Data sources router
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from pyxis_app.postgres.models import User, DataSourceMeta
from pyxis_app.schemas.data_source import DataSourceMetaCreate, DataSourceMetaResponse
from pyxis_app.dependencies import get_postgres_db
from pyxis_app.routers.auth import get_current_user


router = APIRouter(
    prefix="/data-sources",
    tags=["Data Sources"],
)


@router.post(
    "/", response_model=DataSourceMetaResponse, status_code=status.HTTP_201_CREATED
)
async def create_data_source_endpoint(
    data_source: DataSourceMetaCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_postgres_db),
):
    """
    Create a new data source

    The current user will automatically be given access to this data source.
    """
    try:
        # Create data source
        new_data_source = DataSourceMeta(**data_source.model_dump(exclude={"id"}))

        # Add the current user to the data source's users
        new_data_source.users.append(current_user)

        # Save to database
        db.add(new_data_source)
        db.commit()
        db.refresh(new_data_source)

        return new_data_source
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating data source: {str(e)}",
        ) from e
