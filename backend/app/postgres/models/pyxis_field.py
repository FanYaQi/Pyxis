"""
Models for Pyxis field metadata and field data.
"""

# pylint: disable=E1102,C0301
import enum
from typing import List, Optional
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Integer,
    Float,
    String,
    Date,
    DateTime,
    ForeignKey,
    JSON,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from geoalchemy2 import Geometry
from geoalchemy2.types import WKBElement

from app.schemas.data_entry_config import Attribute, AttributeType
from .base import Base


# Enum definitions for option fields
class FunctionalUnit(str, enum.Enum):
    """Functional unit options for field data"""

    OIL = "oil"
    GAS = "gas"


class OilSandsMineType(str, enum.Enum):
    """Oil sands mine type options"""

    NONE = "None"
    INTEGRATED_UPGRADER = "Integrated with upgrader"
    INTEGRATED_DILUENT = "Integrated with diluent"
    INTEGRATED_BOTH = "Integrated with both"


class FloodGasType(str, enum.Enum):
    """Flood gas type options"""

    NG = "NG"  # Natural gas
    N2 = "N2"  # Nitrogen
    CO2 = "CO2"  # Carbon dioxide


class CO2SourceType(str, enum.Enum):
    """CO2 source options"""

    NATURAL = "Natural subsurface reservoir"
    ANTHROPOGENIC = "Anthropogenic"


class UpgraderType(str, enum.Enum):
    """Upgrader type options"""

    NONE = "None"
    DELAYED_COKING = "Delayed coking"
    HYDROCONVERSION = "Hydroconversion"
    COMBINED = "Combined"


class GasProcessingPath(str, enum.Enum):
    """Gas processing path options"""

    NONE = "None"
    MINIMAL = "Minimal"
    ACID_GAS = "Acid Gas"
    WET_GAS = "Wet Gas"
    ACID_WET_GAS = "Acid Wet Gas"
    SOUR_GAS_REINJECTION = "Sour Gas Reinjection"
    CO2_EOR_MEMBRANE = "CO2-EOR Membrane"
    CO2_EOR_RYAN_HOLMES = "CO2-EOR Ryan Holmes"


class EcosystemRichness(str, enum.Enum):
    """Ecosystem carbon richness options"""

    LOW = "Low carbon"
    MEDIUM = "Med carbon"
    HIGH = "High carbon"


class FieldDevelopmentIntensity(str, enum.Enum):
    """Field development intensity options"""

    LOW = "Low"
    MEDIUM = "Med"
    HIGH = "High"


class PyxisFieldMeta(Base):
    """
    Metadata for a Pyxis field. Used to determine whether two fields are the same.
    All the attributes used in the matching process are stored here.
    """

    __tablename__ = "pyxis_field_meta"

    id: Mapped[int] = mapped_column(primary_key=True)
    pyxis_field_code: Mapped[str] = mapped_column(unique=True, index=True)

    # Basic field information
    name: Mapped[Optional[str]] = mapped_column(index=True)
    country: Mapped[Optional[str]] = mapped_column(index=True)
    centroid_h3_index: Mapped[Optional[str]] = mapped_column(
        index=True, comment="H3 index of the field centroid"
    )
    geometry: Mapped[Optional[WKBElement]] = mapped_column(
        Geometry("POLYGON", srid=4326), comment="Geometry of the field"
    )
    # Relationship with pyxis_field_data
    pyxis_field_datas: Mapped[List["PyxisFieldData"]] = relationship(
        back_populates="pyxis_field_meta"
    )
 
    @classmethod
    def get_pyxis_field_meta_attributes(cls) -> List[str]:
        """
        Get all attributes of the model except for id, created_at, updated_at

        Returns:
            List of attribute names
        """
        # Get all attribute names from the model
        attrs = list(cls.__table__.columns.keys())

        # Filter out excluded attributes
        excluded = {"id", "created_at", "updated_at"}
        return [attr for attr in attrs if attr not in excluded]


class PyxisFieldData(Base):
    """
    Data for a Pyxis field.
    Could be used to transform into OPGEE compatible attributes.
    """

    __tablename__ = "pyxis_field_data"

    # TODO: Partitioning strategy - for time-based queries
    # __table_args__ = (
    #     # Partition by year to optimize time-based queries
    #     {"postgresql_partition_by": "RANGE (valid_from)"},
    # )

    id: Mapped[int] = mapped_column(primary_key=True)
    pyxis_field_meta_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("pyxis_field_meta.id"), comment="Reference to the Pyxis field ID"
    )
    data_entry_id: Mapped[int] = mapped_column(
        ForeignKey("data_entry.id"), comment="Reference to the data entry ID"
    )
    valid_from: Mapped[Optional[datetime]] = mapped_column(
        index=True, comment="Start date when these attributes became valid"
    )
    valid_to: Mapped[Optional[datetime]] = mapped_column(
        index=True, comment="End date when these attributes were superseded"
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    name: Mapped[Optional[str]] = mapped_column(index=True)
    country: Mapped[Optional[str]] = mapped_column(index=True)
    latitude: Mapped[Optional[float]] = mapped_column(comment="Latitude of the field")
    longitude: Mapped[Optional[float]] = mapped_column(comment="Longitude of the field")
    centroid_h3_index: Mapped[Optional[str]] = mapped_column(
        comment="H3 index of the field centroid"
    )
    geometry: Mapped[Optional[WKBElement]] = mapped_column(
        Geometry("POLYGON", srid=4326), comment="Geometry of the field"
    )
    # Functional attributes
    functional_unit: Mapped[Optional[FunctionalUnit]] = mapped_column(
        comment="Whether the field produces primarily oil or gas"
    )

    # Production methods
    downhole_pump: Mapped[Optional[bool]] = mapped_column(
        comment="Whether the field uses downhole pumps"
    )
    water_reinjection: Mapped[Optional[bool]] = mapped_column(
        comment="Whether the field uses water reinjection"
    )
    natural_gas_reinjection: Mapped[Optional[bool]] = mapped_column(
        comment="Whether the field uses natural gas reinjection"
    )
    water_flooding: Mapped[Optional[bool]] = mapped_column(
        comment="Whether the field uses water flooding"
    )
    gas_lifting: Mapped[Optional[bool]] = mapped_column(
        comment="Whether the field uses gas lifting"
    )
    gas_flooding: Mapped[Optional[bool]] = mapped_column(
        comment="Whether the field uses gas flooding"
    )
    steam_flooding: Mapped[Optional[bool]] = mapped_column(
        comment="Whether the field uses steam flooding"
    )
    oil_sands_mine_type: Mapped[Optional[OilSandsMineType]] = mapped_column(
        comment="Type of oil sands mining operation, if applicable"
    )

    # Field properties
    age: Mapped[Optional[float]] = mapped_column(
        comment="Age of the field in years", info={"units": "years"}
    )
    depth: Mapped[Optional[float]] = mapped_column(
        comment="Depth of the field in feet", info={"units": "ft"}
    )
    oil_prod: Mapped[Optional[float]] = mapped_column(
        comment="Oil production volume in barrels per day", info={"units": "bbl/day"}
    )
    num_prod_wells: Mapped[Optional[int]] = mapped_column(
        comment="Number of producing wells"
    )
    num_water_inj_wells: Mapped[Optional[int]] = mapped_column(
        comment="Number of water injecting wells"
    )
    well_diam: Mapped[Optional[float]] = mapped_column(
        comment="Production tubing diameter in inches", info={"units": "inch"}
    )
    prod_index: Mapped[Optional[float]] = mapped_column(
        comment="Productivity index in bbl_oil/(psi*day)",
        info={"units": "bbl_oil/(psi*day)"},
    )
    res_press: Mapped[Optional[float]] = mapped_column(
        comment="Reservoir pressure in psi", info={"units": "psi"}
    )
    res_temp: Mapped[Optional[float]] = mapped_column(
        comment="Reservoir temperature in degrees Fahrenheit", info={"units": "degF"}
    )
    offshore: Mapped[Optional[bool]] = mapped_column(
        comment="Whether the field is offshore"
    )

    # Oil and gas properties
    # TODO: Confirm units, there is no units for API gravity.
    api: Mapped[Optional[float]] = mapped_column(
        comment="API gravity of oil at standard pressure and temperature"
    )
    gas_comp_n2: Mapped[Optional[float]] = mapped_column(
        comment="Percentage of N2 in the gas composition"
    )
    gas_comp_co2: Mapped[Optional[float]] = mapped_column(
        comment="Percentage of CO2 in the gas composition"
    )
    gas_comp_c1: Mapped[Optional[float]] = mapped_column(
        comment="Percentage of C1 (methane) in the gas composition"
    )
    gas_comp_c2: Mapped[Optional[float]] = mapped_column(
        comment="Percentage of C2 (ethane) in the gas composition"
    )
    gas_comp_c3: Mapped[Optional[float]] = mapped_column(
        comment="Percentage of C3 (propane) in the gas composition"
    )
    gas_comp_c4: Mapped[Optional[float]] = mapped_column(
        comment="Percentage of C4+ (butane+) in the gas composition"
    )
    gas_comp_h2s: Mapped[Optional[float]] = mapped_column(
        comment="Percentage of H2S in the gas composition"
    )

    # Ratios
    gor: Mapped[Optional[float]] = mapped_column(
        comment="Gas-to-oil ratio in scf/bbl_oil", info={"units": "scf/bbl_oil"}
    )
    wor: Mapped[Optional[float]] = mapped_column(
        comment="Water-to-oil ratio in bbl_water/bbl_oil",
        info={"units": "bbl_water/bbl_oil"},
    )
    wir: Mapped[Optional[float]] = mapped_column(
        comment="Water injection ratio in bbl_water/bbl_oil",
        info={"units": "bbl_water/bbl_oil"},
    )
    glir: Mapped[Optional[float]] = mapped_column(
        comment="Gas lifting injection ratio in scf/bbl_liquid",
        info={"units": "scf/bbl_liquid"},
    )
    gfir: Mapped[Optional[float]] = mapped_column(
        comment="Gas flooding injection ratio in scf/bbl_oil",
        info={"units": "scf/bbl_oil"},
    )
    flood_gas_type: Mapped[Optional[FloodGasType]] = mapped_column(
        comment="Type of gas used for flooding"
    )
    frac_co2_breakthrough: Mapped[Optional[float]] = mapped_column(
        comment="Fraction of CO2 breaking through to producers"
    )
    co2_source: Mapped[Optional[CO2SourceType]] = mapped_column(
        comment="Source of makeup CO2"
    )
    perc_sequestration_credit: Mapped[Optional[float]] = mapped_column(
        comment="Percentage of sequestration credit assigned to the oilfield"
    )
    sor: Mapped[Optional[float]] = mapped_column(
        comment="Steam-to-oil ratio in bbl_steam/bbl_oil",
        info={"units": "bbl_steam/bbl_oil"},
    )

    # Fractions and processing
    fraction_elec_onsite: Mapped[Optional[float]] = mapped_column(
        comment="Fraction of required fossil electricity generated onsite"
    )
    fraction_remaining_gas_inj: Mapped[Optional[float]] = mapped_column(
        comment="Fraction of remaining natural gas reinjected"
    )
    fraction_water_reinjected: Mapped[Optional[float]] = mapped_column(
        comment="Fraction of produced water reinjected"
    )
    fraction_steam_cogen: Mapped[Optional[float]] = mapped_column(
        comment="Fraction of steam generation via cogeneration"
    )
    fraction_steam_solar: Mapped[Optional[float]] = mapped_column(
        comment="Fraction of steam generation via solar thermal"
    )
    heater_treater: Mapped[Optional[bool]] = mapped_column(
        comment="Whether a heater/treater is used"
    )
    stabilizer_column: Mapped[Optional[bool]] = mapped_column(
        comment="Whether a stabilizer column is used"
    )
    upgrader_type: Mapped[Optional[UpgraderType]] = mapped_column(
        comment="Type of upgrader used"
    )
    gas_processing_path: Mapped[Optional[GasProcessingPath]] = mapped_column(
        comment="Associated gas processing path"
    )
    for_value: Mapped[Optional[float]] = mapped_column(
        comment="Flaring-to-oil ratio in scf/bbl_oil", info={"units": "scf/bbl_oil"}
    )
    frac_venting: Mapped[Optional[float]] = mapped_column(
        comment="Purposeful venting fraction (post-flare gas fraction vented)"
    )
    fraction_diluent: Mapped[Optional[float]] = mapped_column(
        comment="Volume fraction of diluent"
    )

    # Land use impact
    ecosystem_richness: Mapped[Optional[EcosystemRichness]] = mapped_column(
        comment="Ecosystem carbon richness category"
    )
    field_development_intensity: Mapped[
        Optional[FieldDevelopmentIntensity]
    ] = mapped_column(comment="Field development intensity category")

    # Transportation
    frac_transport_tanker: Mapped[Optional[float]] = mapped_column(
        comment="Fraction of product transported by ocean tanker"
    )
    frac_transport_barge: Mapped[Optional[float]] = mapped_column(
        comment="Fraction of product transported by barge"
    )
    frac_transport_pipeline: Mapped[Optional[float]] = mapped_column(
        comment="Fraction of product transported by pipeline"
    )
    frac_transport_rail: Mapped[Optional[float]] = mapped_column(
        comment="Fraction of product transported by rail"
    )
    frac_transport_truck: Mapped[Optional[float]] = mapped_column(
        comment="Fraction of product transported by truck"
    )
    transport_dist_tanker: Mapped[Optional[float]] = mapped_column(
        comment="Transportation distance by ocean tanker in miles",
        info={"units": "miles"},
    )
    transport_dist_barge: Mapped[Optional[float]] = mapped_column(
        comment="Transportation distance by barge in miles", info={"units": "miles"}
    )
    transport_dist_pipeline: Mapped[Optional[float]] = mapped_column(
        comment="Transportation distance by pipeline in miles", info={"units": "miles"}
    )
    transport_dist_rail: Mapped[Optional[float]] = mapped_column(
        comment="Transportation distance by rail in miles", info={"units": "miles"}
    )
    transport_dist_truck: Mapped[Optional[float]] = mapped_column(
        comment="Transportation distance by truck in miles", info={"units": "miles"}
    )
    ocean_tanker_size: Mapped[Optional[float]] = mapped_column(
        comment="Ocean tanker size in tonnes", info={"units": "tonne"}
    )
    # Additional data, did not find it in opgee_attributes.xml
    small_sources_emissions: Mapped[Optional[float]] = mapped_column(
        comment="Small sources emissions", info={"units": "g/MJ"}
    )

    # Any additional attributes
    additional_attributes: Mapped[Optional[dict]] = mapped_column(
        JSON, comment="Additional attributes not explicitly defined in the schema"
    )

    # Relationship with pyxis_field_meta
    pyxis_field_meta: Mapped["PyxisFieldMeta"] = relationship(
        back_populates="pyxis_field_datas"
    )
    data_entry: Mapped["DataEntry"] = relationship(  # type: ignore
        back_populates="pyxis_field_datas"
    )

    @classmethod
    def get_field_attributes(cls) -> List[str]:
        """
        Get all attributes of the model except for id, created_at, updated_at

        Returns:
            List of attribute names
        """
        # Get all attribute names from the model
        attrs = list(cls.__table__.columns.keys())

        # Filter out excluded attributes
        excluded = {
            "id",
            "created_at",
            "updated_at",
            "pyxis_field_meta_id",
            "data_entry_id",
        }
        return [attr for attr in attrs if attr not in excluded]

    @classmethod
    def get_attribute_info_by_name(cls, name: str) -> Attribute:
        """
        Get the attribute info by name

        Args:
            name: The name of the attribute to get info for

        Returns:
            Attribute object with the attribute's metadata

        Raises:
            ValueError: If the attribute doesn't exist in the model
        """
        if name not in cls.__table__.columns:
            raise ValueError(f"Attribute {name} not found in {cls.__tablename__}")

        column = cls.__table__.columns[name]

        # Get the units from the info dictionary if it exists
        units = (
            column.info.get("units")
            if hasattr(column, "info") and column.info
            else None
        )

        # Get the description from the comment attribute
        description = getattr(column, "comment", None)

        # Map SQLAlchemy types to AttributeType
        type_map = {
            Boolean: AttributeType.boolean,
            Integer: AttributeType.integer,
            Float: AttributeType.number,
            String: AttributeType.string,
            Date: AttributeType.date,
            DateTime: AttributeType.datetime,
            Geometry: AttributeType.geometry,
        }

        # Default to string
        attr_type = AttributeType.string

        # Find the matching type in the map
        for sql_type, attribute_type in type_map.items():
            if isinstance(column.type, sql_type):
                attr_type = attribute_type
                break

        # Handle enum types
        if hasattr(column.type, "enum_class") and column.type.enum_class is not None:  # type: ignore
            attr_type = AttributeType.string

        return Attribute(
            name=name, units=units, description=description, type=attr_type
        )
