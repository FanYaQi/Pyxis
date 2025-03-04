# backend/pyxis_app/postgres/models/data_entry.py
import enum
from sqlalchemy import Column, Integer, String, ForeignKey, Enum, DateTime, LargeBinary, JSON, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .base import Base


class FileExtension(str, enum.Enum):
    """Enumeration of supported file extensions"""
    CSV = "csv"
    JSON = "json"
    GEOJSON = "geojson"
    SHP = "shp"  # Shapefile
    XLS = "xls"
    XLSX = "xlsx"
    TXT = "txt"
    ZIP = "zip"  # For compressed archives
    GDB = "gdb"  # File geodatabase
    GPKG = "gpkg"  # GeoPackage
    KML = "kml"
    OTHER = "other"


class DataGranularity(str, enum.Enum):
    """Enumeration of possible data granularities"""
    WELL = "well"
    FIELD = "field"
    BASIN = "basin"
    COUNTRY = "country"
    GLOBAL = "global"
    OTHER = "other"


class ProcessingStatus(str, enum.Enum):
    """Enumeration of possible processing statuses"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DataEntry(Base):
    """
    Model for individual data entries in the Pyxis system.
    Each entry represents a specific dataset from a data source.
    
    For multi-file formats like Shapefiles, all related files are stored
    together in a single archive in raw_data.
    """
    __tablename__ = "data_entry"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(String, ForeignKey("data_source_meta.source_id"), nullable=False)
    alias = Column(String, nullable=False, index=True)
    file_extension = Column(Enum(FileExtension), nullable=False)
    granularity = Column(Enum(DataGranularity), nullable=False)
    
    # File data and identification
    raw_data = Column(LargeBinary, nullable=True)  # Binary storage for raw file data
    raw_data_md5 = Column(String(32), nullable=True)  # MD5 hash of raw_data for validation
    file_name = Column(String, nullable=True)  # Original filename or archive name
    file_size = Column(Integer, nullable=True)  # Size in bytes
    
    # Configuration and metadata
    config_file = Column(JSON, nullable=True)  # JSON storage for configuration/mapping
    config_file_md5 = Column(String(32), nullable=True)  # MD5 hash of config_file
    version = Column(String, nullable=True)
    
    # List of files inside the archive (if applicable)
    contained_files = Column(JSON, nullable=True)  # List of filenames within the archive
    
    # Processing details
    upload_date = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(Enum(ProcessingStatus), nullable=False, default=ProcessingStatus.PENDING)
    error_message = Column(Text, nullable=True)
    metadata = Column(JSON, nullable=True)  # Additional metadata about the entry
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationship with data source
    source = relationship("DataSourceMeta", backref="entries")
    
    def __repr__(self):
        return f"<DataEntry(id={self.id}, alias='{self.alias}', file_extension='{self.file_extension}', status='{self.status}')>"