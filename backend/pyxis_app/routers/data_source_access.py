"""
Data source permissions router
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from pyxis_app.postgres.models.user import User
from pyxis_app.postgres.models.data_source import DataSourceMeta
from pyxis_app.dependencies import get_postgres_db
from pyxis_app.routers.auth import get_current_user


router = APIRouter(
    prefix="/data-sources/access",
    tags=["Data Source Access"],
)


# Pydantic models for request/response
class UserPermissionCreate(BaseModel):
    """Pydantic model for creating a user permission"""

    user_id: int
    data_source_id: int


# Grant access to a data source
@router.post("/{data_source_id}")
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

    return {
        "message": f"User {user.email} granted access to data source with id {data_source.id}",
    }


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
