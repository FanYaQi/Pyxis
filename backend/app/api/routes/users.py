import uuid
from typing import Any, List
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from app.api.deps import (
    CurrentUser,
    DBSessionDep,
)
from app.api.auth.utils import get_current_active_superuser
from app.configs.settings import settings
from app.api.auth.security import get_password_hash, verify_password
from app.postgres.models import (
    User,
)
from app.services import user_service
from app.utils.email_utils import (
    generate_new_account_email,
    send_email,
)
from app.api.common import Message
from app.schemas.users import (
    UserResponse,
    UserCreate,
    UserUpdateMe,
    UserUpdate,
    UserSignup,
    UpdatePassword,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=List[UserResponse],
)
def read_users(db: DBSessionDep, skip: int = 0, limit: int = 100) -> Any:
    """
    Retrieve users.
    """

    count_statement = select(func.count()).select_from(User)  # pylint: disable=E1102
    count = db.scalar(count_statement)

    statement = select(User).offset(skip).limit(limit)
    users = db.execute(statement).all()

    return {
        "users": [UserResponse.model_validate(user) for user in users],
        "total": count,
    }


@router.post(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UserResponse,
)
def create_user(*, session: DBSessionDep, user_in: UserCreate) -> Any:
    """
    Create new user.
    """
    user = user_service.get_user_by_email(session=session, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system.",
        )

    user = user_service.create_user(session=session, user_create=user_in)
    if settings.emails_enabled and user_in.email:
        email_data = generate_new_account_email(
            email_to=user_in.email, username=user_in.email, password=user_in.password
        )
        send_email(
            email_to=user_in.email,
            subject=email_data.subject,
            html_content=email_data.html_content,
        )
    return user


@router.patch("/me", response_model=UserResponse)
def update_user_me(
    *, session: DBSessionDep, user_in: UserUpdateMe, current_user: CurrentUser
) -> Any:
    """
    Update own user.
    """

    if user_in.email:
        existing_user = user_service.get_user_by_email(
            session=session, email=user_in.email
        )
        if existing_user and existing_user.id != current_user.id:
            raise HTTPException(
                status_code=409, detail="User with this email already exists"
            )
    update_data = user_in.model_dump(exclude_unset=True)
    # Update user attributes directly
    for key, value in update_data.items():
        setattr(current_user, key, value)

    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return current_user


@router.patch("/me/password", response_model=Message)
def update_password_me(
    *, session: DBSessionDep, body: UpdatePassword, current_user: CurrentUser
) -> Any:
    """
    Update own password.
    """
    if current_user.oauth_provider:
        raise HTTPException(
            status_code=400, detail="Cannot update password for OAuth user"
        )
    if not current_user.hashed_password:
        logger.error("User %s has no password", current_user.email)
        raise HTTPException(
            status_code=400, detail="Cannot update password for user with no password"
        )
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect password")
    if body.current_password == body.new_password:
        raise HTTPException(
            status_code=400, detail="New password cannot be the same as the current one"
        )
    hashed_password = get_password_hash(body.new_password)
    current_user.hashed_password = hashed_password
    session.add(current_user)
    session.commit()
    return Message(message="Password updated successfully")


@router.get("/me", response_model=UserResponse)
def read_user_me(current_user: CurrentUser) -> Any:
    """
    Get current user.
    """
    return current_user


@router.delete("/me")
def delete_user_me(session: DBSessionDep, current_user: CurrentUser) -> Any:
    """
    Delete own user.
    """
    if current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="Super users are not allowed to delete themselves"
        )
    session.delete(current_user)
    session.commit()
    return Message(message="User deleted successfully")


@router.post("/signup", response_model=UserResponse)
def register_user(session: DBSessionDep, user_in: UserSignup) -> Any:
    """
    Create new user without the need to be logged in.
    """
    user = user_service.get_user_by_email(session=session, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system",
        )
    user_create = UserCreate.model_validate(user_in.model_dump())
    user = user_service.create_user(session=session, user_create=user_create)
    return user


@router.get("/{user_id}", response_model=UserResponse)
def read_user_by_id(
    user_id: uuid.UUID, session: DBSessionDep, current_user: CurrentUser
) -> Any:
    """
    Get a specific user by id.
    """
    user = session.get(User, user_id)
    if user == current_user:
        return user
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403,
            detail="The user doesn't have enough privileges",
        )
    return user


@router.patch(
    "/{user_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UserResponse,
)
def update_user(
    *,
    session: DBSessionDep,
    user_id: uuid.UUID,
    user_in: UserUpdate,
) -> Any:
    """
    Update a user.
    """

    db_user = session.get(User, user_id)
    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="The user with this id does not exist in the system",
        )
    if user_in.email:
        existing_user = user_service.get_user_by_email(
            session=session, email=user_in.email
        )
        if existing_user and existing_user.id != user_id:
            raise HTTPException(
                status_code=409, detail="User with this email already exists"
            )

    db_user = user_service.update_user(
        session=session, db_user=db_user, user_in=user_in
    )
    return db_user


@router.delete("/{user_id}", dependencies=[Depends(get_current_active_superuser)])
def delete_user(
    session: DBSessionDep, current_user: CurrentUser, user_id: uuid.UUID
) -> Message:
    """
    Delete a user.
    """
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user == current_user:
        raise HTTPException(
            status_code=403, detail="Super users are not allowed to delete themselves"
        )
    # TODO: dealwith the case where the user is the owner of some data.
    session.delete(user)
    session.commit()
    return Message(message="User deleted successfully")
