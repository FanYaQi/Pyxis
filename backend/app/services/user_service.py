from sqlalchemy import select
from sqlalchemy.orm import Session

from app.postgres.models import User
from app.api.auth.security import get_password_hash, verify_password
from app.schemas.users import UserCreate, UserUpdate


def authenticate(*, session: Session, email: str, password: str) -> User | None:
    db_user = get_user_by_email(session=session, email=email)
    if not db_user:
        return None
    if not db_user.hashed_password:
        # This should be 3rd party login.
        # Hide information about the user login method.
        return None
    if not verify_password(password, db_user.hashed_password):
        return None
    return db_user


def create_user(*, session: Session, user_create: UserCreate) -> User:
    user_data = user_create.model_dump(exclude_unset=True)
    user_data["hashed_password"] = get_password_hash(user_data.pop("password"))
    new_user = User(**user_data)
    session.add(new_user)
    session.commit()
    session.refresh(new_user)
    return new_user


def update_user(*, session: Session, db_user: User, user_in: UserUpdate) -> User:
    user_data = user_in.model_dump(exclude_unset=True)
    extra_data = {}
    if "password" in user_data:
        password = user_data.pop("password")
        hashed_password = get_password_hash(password)
        extra_data["hashed_password"] = hashed_password

    # Update user attributes directly
    for key, value in user_data.items():
        setattr(db_user, key, value)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


def get_user_by_email(*, session: Session, email: str) -> User | None:
    statement = select(User).where(User.email == email)
    session_user = session.execute(statement).scalar_one_or_none()
    return session_user
