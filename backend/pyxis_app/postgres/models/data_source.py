"""
Model for data source metadata in the Pyxis system.
"""

# pylint: disable=E1102,C0301
import enum
from typing import List, Optional
from datetime import datetime

from sqlalchemy import String, ARRAY
from sqlalchemy.sql import func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .user import user_data_source


class SourceType(str, enum.Enum):
    """Enumeration of possible source types"""

    GOVERNMENT = "government"
    PAPER = "paper"
    COMMERCIAL = "commercial"
    NGO = "ngo"


class DataAccessType(str, enum.Enum):
    """Enumeration of possible data access types"""

    API = "api"
    FILE_UPLOAD = "file_upload"


class DataSourceMeta(Base):
    """
    Model for metadata about data sources in the Pyxis system.
    Stores information about source reliability, recency, and coverage.
    """

    __tablename__ = "data_source_meta"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str]
    description: Mapped[Optional[str]]
    urls: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String))
    source_type: Mapped[SourceType]
    data_access_type: Mapped[DataAccessType]
    reliability_score: Mapped[Optional[float]]
    recency_score: Mapped[Optional[float]]
    richness_score: Mapped[Optional[float]]
    pyxis_score: Mapped[Optional[float]]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    # Relationship with data entries
    data_entries: Mapped[List["DataEntry"]] = relationship(back_populates="data_source")  # type: ignore

    # Relationship with users
    users: Mapped[List["User"]] = relationship(secondary=user_data_source, back_populates="data_sources")  # type: ignore

    def __repr__(self):
        return f"<DataSourceMeta(id={self.id}, name='{self.name}', pyxis_score={self.pyxis_score})>"
