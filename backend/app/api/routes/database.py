"""Database related apis."""

from fastapi import APIRouter

from app.postgres.models.base import Base
from app.postgres.models import User
from app.postgres.database import engine, SessionLocal
from app.configs.settings import settings


router = APIRouter(
    prefix="/database",
    tags=["database"],
)


@router.post("/init_db", status_code=200)
def initialize_database():
    """Initialize database tables based on SQLAlchemy models"""
    # Create all tables
    Base.metadata.create_all(bind=engine)

    # Create anonymous user if it doesn't exist
    with SessionLocal() as db:
        anonymous_user = (
            db.query(User).filter(User.email == settings.ANONYMOUS_USER_EMAIL).first()
        )
        if not anonymous_user:
            anonymous_user = User(
                email=settings.ANONYMOUS_USER_EMAIL,
                is_active=True,
                is_superuser=False,
            )
            db.add(anonymous_user)
            db.commit()
    return {"message": "Database tables created successfully"}
