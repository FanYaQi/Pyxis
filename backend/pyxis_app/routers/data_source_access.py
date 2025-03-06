"""
Data source permissions router
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from pyxis_app.postgres.models.user import User
from pyxis_app.postgres.models.data_source import DataSourceMeta
from pyxis_app.dependencies import get_postgres_db
from pyxis_app.routers.auth import get_current_user
from pyxis_app.services.data_source_service import check_data_source_access


router = APIRouter(
    prefix="/data-sources/access",
    tags=["Data Source Access"],
)


# Pydantic models for request/response
class UserPermissionCreate(BaseModel):
    """Pydantic model for creating a user permission"""

    user_id: int
    data_source_id: int


class UserPermissionResponse(BaseModel):
    """Pydantic model for a user permission response"""

    user_id: int
    user_email: str
    data_source_id: int
    data_source_name: str


# Grant access to a data source
@router.post("/{data_source_id}", response_model=UserPermissionResponse)
async def grant_data_source_access(
    data_source_id: int,
    user_permission: UserPermissionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_postgres_db),
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
    user = db.query(User).filter(User.id == user_permission.user_id).first()
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

    return UserPermissionResponse(
        user_id=user.id,
        user_email=user.email,
        data_source_id=data_source.id,
        data_source_name=data_source.name,
    )


# Revoke access to a data source
@router.delete("/{data_source_id}/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_data_source_access(
    data_source_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_postgres_db),
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


# List users with access to a data source
@router.get("/{data_source_id}", response_model=List[UserPermissionResponse])
async def list_data_source_users(
    data_source_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_postgres_db),
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
    return [
        UserPermissionResponse(
            user_id=user.id,
            user_email=user.email,
            data_source_id=data_source.id,
            data_source_name=data_source.name,
        )
        for user in data_source.users
    ]


# List data sources a user has access to
@router.get("/user/me", response_model=List[UserPermissionResponse])
async def list_my_data_sources(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_postgres_db),
):
    """List all data sources the current user has access to"""
    # Superusers see all data sources
    if current_user.is_superuser:
        data_sources = db.query(DataSourceMeta).all()
    else:
        data_sources = current_user.data_sources

    return [
        UserPermissionResponse(
            user_id=current_user.id,
            user_email=current_user.email,
            data_source_id=ds.id,
            data_source_name=ds.name,
        )
        for ds in data_sources
    ]
