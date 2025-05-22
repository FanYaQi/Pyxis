import json
from datetime import timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, Response
from fastapi.requests import Request
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from app.services import user_service


from app.api.common import Message
from app.api.deps import DBSessionDep
from app.api.auth.utils import get_current_active_superuser
from app.api.auth.oauth import oauth, get_or_create_oauth_user
from app.configs.settings import settings
from app.api.auth.security import (
    get_password_hash,
    create_access_token,
    generate_password_reset_token,
    verify_password_reset_token,
)
from app.utils.email_utils import generate_reset_password_email, send_email


router = APIRouter(prefix="/login", tags=["login"])


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class NewPassword(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=40)


@router.post("/access-token")
def login_access_token(
    db: DBSessionDep, form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
):
    """
    OAuth2 compatible token login, get an access token for future requests
    """
    user = user_service.authenticate(
        session=db, email=form_data.username, password=form_data.password
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    elif not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive user",
        )

    # Create token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = Token(
        access_token=create_access_token(user.id, expires_delta=access_token_expires),
        token_type="bearer",
    )
    response = Response(
        content=json.dumps(token.model_dump()),
        media_type="application/json",
    )
    response.set_cookie(
        key="access_token",
        value=f"Bearer {token.access_token}",
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        expires=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="none",  # TODO: Set to lax in production
        secure=True,
    )
    return response


# OAuth routes for Google
@router.get("/google")
async def login_google(request: Request):
    """Initiate Google OAuth login flow"""
    redirect_uri = request.url_for("auth_google_callback")
    return await oauth.google.authorize_redirect(request, redirect_uri)  # type: ignore


@router.get("/google/callback")
async def auth_google_callback(
    request: Request,
    db: DBSessionDep,
):
    """Handle Google OAuth callback and create/get user"""
    token = await oauth.google.authorize_access_token(request)  # type: ignore
    user_info = token.get("userinfo")

    if not user_info or not user_info.get("email"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not get user info from Google",
        )

    # Get or create user
    user = await get_or_create_oauth_user(user_info, db)

    # Create JWT token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(user.id, expires_delta=access_token_expires)

    # Set cookie with token for client-side
    response = Response(
        content='{"status": "success", "message": "Successfully authenticated with Google"}',
        media_type="application/json",
    )
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        expires=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
        secure=True,
    )

    return response


@router.post("/password-recovery/{email}")
def recover_password(email: str, session: DBSessionDep) -> Message:
    """
    Password Recovery
    """
    user = user_service.get_user_by_email(session=session, email=email)

    if not user:
        raise HTTPException(
            status_code=404,
            detail="The user with this email does not exist in the system.",
        )
    password_reset_token = generate_password_reset_token(email=email)
    email_data = generate_reset_password_email(
        email_to=user.email, email=email, token=password_reset_token
    )
    send_email(
        email_to=user.email,
        subject=email_data.subject,
        html_content=email_data.html_content,
    )
    return Message(message="Password recovery email sent")


@router.post("/reset-password/")
def reset_password(session: DBSessionDep, body: NewPassword) -> Message:
    """
    Reset password
    """
    email = verify_password_reset_token(token=body.token)
    if not email:
        raise HTTPException(status_code=400, detail="Invalid token")
    user = user_service.get_user_by_email(session=session, email=email)
    if not user:
        raise HTTPException(
            status_code=404,
            detail="The user with this email does not exist in the system.",
        )
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    hashed_password = get_password_hash(password=body.new_password)
    user.hashed_password = hashed_password
    session.add(user)
    session.commit()
    return Message(message="Password updated successfully")


@router.post(
    "/password-recovery-html-content/{email}",
    dependencies=[Depends(get_current_active_superuser)],
    response_class=HTMLResponse,
)
def recover_password_html_content(email: str, session: DBSessionDep) -> Any:
    """
    HTML Content for Password Recovery
    """
    user = user_service.get_user_by_email(session=session, email=email)

    if not user:
        raise HTTPException(
            status_code=404,
            detail="The user with this username does not exist in the system.",
        )
    password_reset_token = generate_password_reset_token(email=email)
    email_data = generate_reset_password_email(
        email_to=user.email, email=email, token=password_reset_token
    )

    return HTMLResponse(
        content=email_data.html_content, headers={"subject:": email_data.subject}
    )
