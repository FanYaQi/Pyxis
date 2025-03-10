from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr

from app.api.deps import DBSessionDep
from app.api.auth.security import get_password_hash
from app.postgres.models import (
    User,
)
from app.schemas.users import UserResponse
from app.utils.email_utils import generate_test_email, send_email
from app.api.common import Message
from app.api.auth.utils import get_current_active_superuser


router = APIRouter(tags=["private"], prefix="/private")


class PrivateUserCreate(BaseModel):
    email: str
    password: str
    full_name: str
    is_verified: bool = False


@router.post("/users/", response_model=UserResponse)
def create_user(user_in: PrivateUserCreate, session: DBSessionDep) -> Any:
    """
    Create a new user.
    """

    user = User(
        email=user_in.email,
        full_name=user_in.full_name,
        hashed_password=get_password_hash(user_in.password),
    )

    session.add(user)
    session.commit()

    return user


@router.post(
    "/test-email/",
    dependencies=[Depends(get_current_active_superuser)],
    status_code=201,
)
def test_email(email_to: EmailStr) -> Message:
    """
    Test emails.
    """
    email_data = generate_test_email(email_to=email_to)
    send_email(
        email_to=email_to,
        subject=email_data.subject,
        html_content=email_data.html_content,
    )
    return Message(message="Test email sent")


@router.get("/health-check/")
async def health_check() -> bool:
    return True
