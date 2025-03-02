import enum
from sqlalchemy import Column, String, Integer, Float, DateTime, ARRAY, Enum
from sqlalchemy.sql import func
from .base import Base


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

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    urls = Column(ARRAY(String), nullable=True)
    source_type = Column(Enum(SourceType), nullable=False)
    data_access_type = Column(Enum(DataAccessType), nullable=False)
    reliability_score = Column(Float, nullable=True)
    recency_score = Column(Float, nullable=True)
    richness_score = Column(Float, nullable=True)
    pyxis_score = Column(Float, nullable=True)  # Overall score
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<DataSourceMeta(id={self.id}, name='{self.name}', pyxis_score={self.pyxis_score})>"