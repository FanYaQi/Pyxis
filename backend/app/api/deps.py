"""
Common dependencies for the API
"""
from typing import Annotated, Generator, Optional

from jose import JWTError, ExpiredSignatureError
from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.postgres.database import SessionLocal
from app.postgres.models import User
from app.configs.settings import settings
from app.api.auth.security import decode_token


def get_postgres_db() -> Generator[Session, None, None]:
    """Dependency to get a PostgreSQL database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class ConditionalOAuth2PasswordBearer(OAuth2PasswordBearer):
    """OAuth2 password bearer that can conditionally skip authentication"""

    async def __call__(self, request: Request) -> Optional[str]:
        """Return None instead of raising an exception if AUTH_ENABLED is False"""
        if not settings.AUTH_ENABLED:
            return None

        # Use the parent class's __call__ method if authentication is enabled
        return await super().__call__(request)


oauth2_scheme = ConditionalOAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token"
)


async def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_postgres_db)
) -> User:
    """Get the current authenticated user from JWT token"""

    if not token and not settings.AUTH_ENABLED:
        # Get anonymous user from database
        anonymous_user = (
            db.query(User).filter(User.email == settings.ANONYMOUS_USER_EMAIL).first()
        )
        if anonymous_user:
            return anonymous_user

        # This should not happen if database is initialized correctly
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Anonymous user not found in database",
        )
    try:
        token_data = decode_token(token)
    except (JWTError, ExpiredSignatureError) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

    user = db.query(User).filter(User.id == token_data.sub).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


# Dependencies that are commonly used in the API
DBSessionDep = Annotated[Session, Depends(get_postgres_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]
TokenDep = Annotated[str, Depends(oauth2_scheme)]
