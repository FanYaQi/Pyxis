"""
User model for authentication
"""

# pylint: disable=E1102,C0301
from datetime import datetime
from typing import List, Optional

from sqlalchemy import ForeignKey, Table, Column, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import Base

# Association table for many-to-many relationship between users and data sources
user_data_source = Table(
    "user_data_source",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id"), primary_key=True),
    Column(
        "data_source_id", Integer, ForeignKey("data_source_meta.id"), primary_key=True
    ),
)


class User(Base):
    """User model for authentication"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(unique=True, index=True)
    hashed_password: Mapped[Optional[str]] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    is_superuser: Mapped[bool] = mapped_column(default=False)

    # OAuth related fields
    oauth_provider: Mapped[Optional[str]] = mapped_column(nullable=True)
    oauth_id: Mapped[Optional[str]] = mapped_column(nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    data_sources: Mapped[List["DataSourceMeta"]] = relationship(  # type: ignore
        secondary=user_data_source, back_populates="users"
    )
