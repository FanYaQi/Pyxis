"""Database related apis."""

from fastapi import APIRouter

from pyxis_app.postgres.database import engine, Base

router = APIRouter(
    prefix="/data",
    tags=["data"],
    responses={404: {"description": "Not found"}},
)


@router.post("/init_db", status_code=200)
def initialize_database():
    """Initialize database tables based on SQLAlchemy models"""
    # Create all tables
    Base.metadata.create_all(bind=engine)
    return {"message": "Database tables created successfully"}
