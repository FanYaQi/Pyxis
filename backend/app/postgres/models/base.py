"""Base class for all database models."""

from sqlalchemy.orm import DeclarativeBase


# To be inherited by database models or classes (the ORM models).
class Base(DeclarativeBase):
    """Base class for all database models."""
