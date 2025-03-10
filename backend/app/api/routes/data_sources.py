"""
Data sources router
"""

from typing import List

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.api.deps import CurrentUser, DBSessionDep
from app.postgres.models import User, DataSourceMeta
from app.schemas.data_source import DataSourceMetaCreate, DataSourceMetaResponse
from app.services.data_source_service import check_data_source_access
from app.schemas.users import UserResponse


router = APIRouter(
    prefix="/data-sources",
    tags=["Data Sources"],
)


class DataSourceResponse(BaseModel):
    """Pydantic model for a user permission response"""

    data_source_id: int
    data_source_name: str


@router.post(
    "/", response_model=DataSourceMetaResponse, status_code=status.HTTP_201_CREATED
)
async def create_data_source_endpoint(
    data_source: DataSourceMetaCreate,
    current_user: CurrentUser,
    db: DBSessionDep,
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


# List data sources a user has access to
# TODO: Also return all data sources created by anonymous user
@router.get("/", response_model=List[DataSourceResponse])
async def list_my_data_sources(
    current_user: CurrentUser,
    db: DBSessionDep,
):
    """List all data sources the current user has access to"""
    # Superusers see all data sources
    if current_user.is_superuser:
        data_sources = db.query(DataSourceMeta).all()
    else:
        data_sources = current_user.data_sources

    return [
        DataSourceResponse(
            data_source_id=ds.id,
            data_source_name=ds.name,
        )
        for ds in data_sources
    ]


# List users with access to a data source
@router.get("/{data_source_id}/users", response_model=List[UserResponse])
async def list_data_source_users(
    data_source_id: int,
    current_user: CurrentUser,
    db: DBSessionDep,
):
    """List all users who have access to a data source"""
    # Verify data source exists
    data_source = (
        db.query(DataSourceMeta).filter(DataSourceMeta.id == data_source_id).first()
    )
    if not data_source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Data source not found"
        )

    # Check if current user has access
    has_access = await check_data_source_access(data_source_id, current_user, db)
    if not has_access:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this data source",
        )

    # Return list of users with access
    return [UserResponse.model_validate(user) for user in data_source.users]


# Grant access to a data source
@router.post("/access/{data_source_id}")
async def grant_data_source_access(
    data_source_id: int,
    user_id: int,
    current_user: CurrentUser,
    db: DBSessionDep,
):
    """Grant a user access to a data source"""
    # Verify current user is superuser
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superusers can manage permissions",
        )

    # Verify data source exists
    data_source = (
        db.query(DataSourceMeta).filter(DataSourceMeta.id == data_source_id).first()
    )
    if not data_source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Data source not found"
        )

    # Verify user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Check if permission already exists
    existing_permission = (
        db.query(DataSourceMeta)
        .filter(
            DataSourceMeta.id == data_source_id, DataSourceMeta.users.any(id=user.id)
        )
        .first()
    )

    if existing_permission:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has access to this data source",
        )

    # Add user to data source
    data_source.users.append(user)
    db.commit()

    return {
        "message": f"User {user.email} granted access to data source with id {data_source.id}",
    }


# Revoke access to a data source
@router.delete("/access/{data_source_id}/", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_data_source_access(
    data_source_id: int,
    user_id: int,
    current_user: CurrentUser,
    db: DBSessionDep,
):
    """Revoke a user's access to a data source"""
    # Verify current user is superuser
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only superusers can manage permissions",
        )

    # Verify data source exists
    data_source = (
        db.query(DataSourceMeta).filter(DataSourceMeta.id == data_source_id).first()
    )
    if not data_source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Data source not found"
        )

    # Verify user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Check if permission exists
    if user not in data_source.users:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User does not have access to this data source",
        )

    # Remove user from data source
    data_source.users.remove(user)
    db.commit()

    return None
