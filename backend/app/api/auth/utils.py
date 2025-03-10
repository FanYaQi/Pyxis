"""
Authentication utilities
TODO: move to somewhere else.
"""
from dotenv import load_dotenv
from fastapi import HTTPException

from app.postgres.models import User
from app.api.deps import CurrentUser


load_dotenv()


async def get_current_active_user(
    current_user: CurrentUser,
):
    """Get the current active user"""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


def get_current_active_superuser(current_user: CurrentUser) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="The user doesn't have enough privileges"
        )
    return current_user
