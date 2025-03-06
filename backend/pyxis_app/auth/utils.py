"""
Authentication utilities
"""

import os
from datetime import datetime, timedelta
from typing import Annotated, Optional, Dict, Any

from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from pydantic import BaseModel

from pyxis_app.postgres.models import User
from pyxis_app.dependencies import get_postgres_db


load_dotenv()

# Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Anonymous user settings
AUTH_ENABLED = os.getenv("AUTH_ENABLED", "true").lower() == "true"
ANONYMOUS_USER_EMAIL = os.getenv("ANONYMOUS_USER_EMAIL", "anonymous@pyxis.system")


class ConditionalOAuth2PasswordBearer(OAuth2PasswordBearer):
    """OAuth2 password bearer that can conditionally skip authentication"""

    async def __call__(self, request: Request) -> Optional[str]:
        """Return None instead of raising an exception if AUTH_ENABLED is False"""
        if not AUTH_ENABLED:
            return None

        # Use the parent class's __call__ method if authentication is enabled
        return await super().__call__(request)


oauth2_scheme = ConditionalOAuth2PasswordBearer(tokenUrl="auth/token")


class TokenData(BaseModel):
    email: Optional[str] = None


def create_access_token(
    data: Dict[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    """Create a JWT token with expiration"""
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_postgres_db)
) -> User:
    """Get the current authenticated user from JWT token"""

    if not token:
        # Get anonymous user from database
        anonymous_user = (
            db.query(User).filter(User.email == ANONYMOUS_USER_EMAIL).first()
        )
        if anonymous_user:
            return anonymous_user

        # This should not happen if database is initialized correctly
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Anonymous user not found in database",
        )

    # Regular authentication flow
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub", None)
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except JWTError as e:
        raise credentials_exception from e

    user = db.query(User).filter(User.email == token_data.email).first()
    if user is None:
        raise credentials_exception

    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Get the current active user"""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user
