# backend/pyxis_app/routers/auth.py
from typing import Optional
from datetime import timedelta

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from pyxis_app.postgres.models.user import User
from pyxis_app.dependencies import get_postgres_db
from pyxis_app.auth.utils import (
    create_access_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)
from pyxis_app.auth.oauth import oauth, get_or_create_user
from pyxis_app.auth.utils import get_current_user

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


# Pydantic models for request/response data
class Token(BaseModel):
    access_token: str
    token_type: str


class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    is_active: bool
    is_superuser: bool
    oauth_provider: Optional[str] = None


# Local authentication routes
@router.post("/register", response_model=UserResponse)
async def register(user_data: UserCreate, db: Session = Depends(get_postgres_db)):
    """Register a new user with email and password"""
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    # Create new user - hash password with bcrypt
    password_bytes = user_data.password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password_bytes, salt).decode("utf-8")

    new_user = User(
        email=user_data.email, hashed_password=hashed_password, is_active=True
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_postgres_db),
):
    """Login with username (email) and password for JWT token"""
    # Find user by email
    user = db.query(User).filter(User.email == form_data.username).first()

    # Verify password with bcrypt
    password_valid = False
    if user and user.hashed_password:
        password_bytes = form_data.password.encode("utf-8")
        hashed_bytes = user.hashed_password.encode("utf-8")
        password_valid = bcrypt.checkpw(password_bytes, hashed_bytes)

    if not user or not password_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}


# OAuth routes for Google
@router.get("/login/google")
async def login_google(request: Request):
    """Initiate Google OAuth login flow"""
    redirect_uri = request.url_for("auth_google_callback")
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/login/google/callback")
async def auth_google_callback(
    request: Request, db: Session = Depends(get_postgres_db)
):
    """Handle Google OAuth callback and create/get user"""
    token = await oauth.google.authorize_access_token(request)
    user_info = token.get("userinfo")

    if not user_info or not user_info.get("email"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not get user info from Google",
        )

    # Get or create user
    user = await get_or_create_user(user_info, db)

    # Create JWT token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )

    # Set cookie with token for client-side
    response = Response(
        content='{"status": "success", "message": "Successfully authenticated with Google"}',
        media_type="application/json",
    )
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        expires=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
        secure=False,  # Set to True in production with HTTPS
    )

    return response


@router.get("/me", response_model=UserResponse)
async def get_user_info(current_user: User = Depends(get_current_user)):
    """Get the current user's information"""
    return current_user
