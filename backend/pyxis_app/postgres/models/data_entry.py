"""
This module defines the DataEntry model for the Pyxis system.

The DataEntry model represents a specific dataset from a data source.
It includes information about the data entry, such as its alias, file extension,
granularity, and processing status.
"""

# pylint: disable=E1102,C0301
import enum
from typing import Dict, List, Optional
from datetime import datetime

from sqlalchemy import (
    String,
    ForeignKey,
    LargeBinary,
    JSON,
    UniqueConstraint,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import Mapped, mapped_column, relationship

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
    __table_args__ = (
        UniqueConstraint(
            "record_id", "version", name="uq_data_entry_record_id_version"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("data_source_meta.id"))
    record_id: Mapped[str] = mapped_column(index=True)
    version: Mapped[str] = mapped_column(index=True)

    # Information about the data entry.
    alias: Mapped[str]
    file_extension: Mapped[FileExtension]
    granularity: Mapped[DataGranularity]

    # File data and identification
    raw_data: Mapped[bytes] = mapped_column(
        LargeBinary
    )  # Binary storage for raw file data
    raw_data_md5: Mapped[str] = mapped_column(
        String(32)
    )  # MD5 hash of raw_data for validation
    file_name: Mapped[Optional[str]]  # Original filename or archive name
    file_size: Mapped[Optional[int]]  # Size in bytes

    # Configuration and metadata
    config_file: Mapped[Optional[Dict]] = mapped_column(
        JSON
    )  # JSON storage for configuration/mapping
    config_file_md5: Mapped[Optional[str]] = mapped_column(
        String(32)
    )  # MD5 hash of config_file
    contained_files: Mapped[Optional[List[str]]] = mapped_column(
        JSON
    )  # List of files inside the archive (if applicable)

    # Processing details
    status: Mapped[ProcessingStatus] = mapped_column(default=ProcessingStatus.PENDING)
    error_message: Mapped[Optional[str]]
    # Additional metadata about the entry
    additional_metadata: Mapped[Optional[Dict]] = mapped_column(JSON)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    # Relationship with data source
    data_source: Mapped["DataSourceMeta"] = relationship(back_populates="data_entries")  # type: ignore

    def __repr__(self):
        return (
            f"<DataEntry(id={self.id}, alias='{self.alias}', file_extension="
            f"'{self.file_extension}', status='{self.status}')>"
        )
