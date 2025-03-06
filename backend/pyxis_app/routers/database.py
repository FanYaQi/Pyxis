"""Database related apis."""

from fastapi import APIRouter

from pyxis_app.postgres.models.base import Base
from pyxis_app.postgres.models import User
from pyxis_app.postgres.database import engine, SessionLocal
from pyxis_app.auth.utils import ANONYMOUS_USER_EMAIL


router = APIRouter(
    prefix="/database",
    tags=["Database"],
    responses={404: {"description": "Not found"}},
)


@router.post("/init_db", status_code=200)
def initialize_database():
    """Initialize database tables based on SQLAlchemy models"""
    # Create all tables
    Base.metadata.create_all(bind=engine)

    # Create anonymous user if it doesn't exist
    with SessionLocal() as db:
        anonymous_user = (
            db.query(User).filter(User.email == ANONYMOUS_USER_EMAIL).first()
        )
        if not anonymous_user:
            anonymous_user = User(
                email=ANONYMOUS_USER_EMAIL, is_active=True, is_superuser=False
            )
            db.add(anonymous_user)
            db.commit()
    return {"message": "Database tables created successfully"}
