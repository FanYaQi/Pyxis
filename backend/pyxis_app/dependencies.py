"""
Dependencies for the Pyxis API
"""

from pyxis_app.postgres.database import SessionLocal


def get_postgres_db():
    """Dependency to get a PostgreSQL database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
