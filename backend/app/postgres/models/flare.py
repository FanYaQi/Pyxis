# In backend/app/postgres/models/flare.py

import uuid
from typing import Optional
from datetime import datetime, date

from sqlalchemy import String, Float, Date
from sqlalchemy.sql import func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from geoalchemy2 import Geometry
from geoalchemy2.types import WKBElement

from .base import Base


class Flare(Base):
    """
    Model for flare data combining location and volume information.

    Contains flare identification, location, volume, and temporal data.
    Multiple records can exist for the same original_id with different time periods.
    """

    __tablename__ = "flare"

    flare_id: Mapped[str] = mapped_column(
        String,
        unique=True,
        index=True,
        default=lambda: str(uuid.uuid4()),
        comment="Pyxis-generated unique flare identifier",
        primary_key=True,
    )
    original_id: Mapped[str] = mapped_column(
        String, index=True, comment="Original flare ID from data source"
    )

    # Geospatial information
    latitude: Mapped[float] = mapped_column(Float, comment="Latitude of flare")
    longitude: Mapped[float] = mapped_column(Float, comment="Longitude of flare")
    geometry: Mapped[Optional[WKBElement]] = mapped_column(
        Geometry("POINT", srid=4326), comment="Point geometry of flare"
    )
    h3_index: Mapped[str] = mapped_column(
        String(15), index=True, comment="H3 index at resolution 10"
    )

    # Volume data
    volume: Mapped[float] = mapped_column(
        Float, comment="Flare volume in standard cubic meters"
    )

    # Temporal information
    valid_from: Mapped[Optional[date]] = mapped_column(
        Date,
        index=True,
        comment="Start date when this flare data is valid (NULL means no start limit)",
    )
    valid_to: Mapped[Optional[date]] = mapped_column(
        Date,
        index=True,
        comment="End date when this flare data stops being valid (NULL means no end limit)",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self):
        return f"<Flare(flare_id='{self.flare_id}', original_id='{self.original_id}', volume={self.volume}, valid_from={self.valid_from}, valid_to={self.valid_to})>"
