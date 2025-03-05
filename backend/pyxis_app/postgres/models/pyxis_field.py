from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime, JSON, Enum as SQLEnum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from geoalchemy2 import Geometry
from .base import Base
import enum

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

    id = Column(Integer, primary_key=True)
    pyxis_field_id = Column(String, unique=True, index=True, nullable=False)
    field_name = Column(String, index=True)
    country = Column(String, index=True)
    geometry = Column(Geometry('GEOMETRY', srid=4326))
    centroid_h3_index = Column(String, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class PyxisFieldData(Base):
    __tablename__ = "pyxis_field_data"

    id = Column(Integer, primary_key=True)
    pyxis_field_id = Column(Integer, ForeignKey("pyxis_fields.id"), index=True, 
                            comment="Reference to the Pyxis field ID")
    data_entry_id = Column(Integer, index=True, comment="Reference to the data entry ID")
    data_entry_version = Column(String, index=True,
                              comment="Version of the data entry")
    source_id = Column(String, ForeignKey("data_source_meta.source_id"), index=True,
                      comment="Reference to the data source")
    effective_start_date = Column(DateTime(timezone=True), index=True,
                                comment="Start date when these attributes became effective")
    effective_end_date = Column(DateTime(timezone=True), index=True,
                              comment="End date when these attributes were superseded")
    
    # Functional attributes
    functional_unit = Column(SQLEnum(FunctionalUnit), 
                           comment="Whether the field produces primarily oil or gas")
    
    # Production methods
    downhole_pump = Column(Boolean, comment="Whether the field uses downhole pumps")
    water_reinjection = Column(Boolean, comment="Whether the field uses water reinjection")
    natural_gas_reinjection = Column(Boolean, comment="Whether the field uses natural gas reinjection")
    water_flooding = Column(Boolean, comment="Whether the field uses water flooding")
    gas_lifting = Column(Boolean, comment="Whether the field uses gas lifting")
    gas_flooding = Column(Boolean, comment="Whether the field uses gas flooding")
    steam_flooding = Column(Boolean, comment="Whether the field uses steam flooding")
    oil_sands_mine_type = Column(SQLEnum(OilSandsMineType), 
                               comment="Type of oil sands mining operation, if applicable")

    # Field properties
    age = Column(Float, comment="Age of the field in years")
    depth = Column(Float, comment="Depth of the field in feet")
    oil_prod = Column(Float, comment="Oil production volume in barrels per day")
    num_prod_wells = Column(Integer, comment="Number of producing wells")
    num_water_inj_wells = Column(Integer, comment="Number of water injecting wells")
    well_diam = Column(Float, comment="Production tubing diameter in inches")
    prod_index = Column(Float, comment="Productivity index in bbl_oil/(psia*day)")
    res_press = Column(Float, comment="Reservoir pressure in psia")
    res_temp = Column(Float, comment="Reservoir temperature in degrees Fahrenheit")
    offshore = Column(Boolean, comment="Whether the field is offshore")

    # Oil and gas properties
    api = Column(Float, comment="API gravity of oil at standard pressure and temperature")
    gas_comp_n2 = Column(Float, comment="Percentage of N2 in the gas composition")
    gas_comp_co2 = Column(Float, comment="Percentage of CO2 in the gas composition")
    gas_comp_c1 = Column(Float, comment="Percentage of C1 (methane) in the gas composition")
    gas_comp_c2 = Column(Float, comment="Percentage of C2 (ethane) in the gas composition")
    gas_comp_c3 = Column(Float, comment="Percentage of C3 (propane) in the gas composition")
    gas_comp_c4 = Column(Float, comment="Percentage of C4+ (butane+) in the gas composition")
    gas_comp_h2s = Column(Float, comment="Percentage of H2S in the gas composition")
    
    # Ratios
    gor = Column(Float, comment="Gas-to-oil ratio in scf/bbl_oil")
    wor = Column(Float, comment="Water-to-oil ratio in bbl_water/bbl_oil")
    wir = Column(Float, comment="Water injection ratio in bbl_water/bbl_oil")
    glir = Column(Float, comment="Gas lifting injection ratio in scf/bbl_liquid")
    gfir = Column(Float, comment="Gas flooding injection ratio in scf/bbl_oil")
    flood_gas_type = Column(SQLEnum(FloodGasType), comment="Type of gas used for flooding")
    frac_co2_breakthrough = Column(Float, comment="Fraction of CO2 breaking through to producers")
    co2_source = Column(SQLEnum(CO2SourceType), comment="Source of makeup CO2")
    perc_sequestration_credit = Column(Float, comment="Percentage of sequestration credit assigned to the oilfield")
    sor = Column(Float, comment="Steam-to-oil ratio in bbl_steam/bbl_oil")
    
    # Fractions and processing
    fraction_elec_onsite = Column(Float, comment="Fraction of required fossil electricity generated onsite")
    fraction_remaining_gas_inj = Column(Float, comment="Fraction of remaining natural gas reinjected")
    fraction_water_reinjected = Column(Float, comment="Fraction of produced water reinjected")
    fraction_steam_cogen = Column(Float, comment="Fraction of steam generation via cogeneration")
    fraction_steam_solar = Column(Float, comment="Fraction of steam generation via solar thermal")
    heater_treater = Column(Boolean, comment="Whether a heater/treater is used")
    stabilizer_column = Column(Boolean, comment="Whether a stabilizer column is used")
    upgrader_type = Column(SQLEnum(UpgraderType), comment="Type of upgrader used")
    gas_processing_path = Column(SQLEnum(GasProcessingPath), comment="Associated gas processing path")
    for_value = Column(Float, comment="Flaring-to-oil ratio in scf/bbl_oil")
    frac_venting = Column(Float, comment="Purposeful venting fraction (post-flare gas fraction vented)")
    fraction_diluent = Column(Float, comment="Volume fraction of diluent")
    
    # Land use impact
    ecosystem_richness = Column(SQLEnum(EcosystemRichness), comment="Ecosystem carbon richness category")
    field_development_intensity = Column(SQLEnum(FieldDevelopmentIntensity), comment="Field development intensity category")
    
    # Transportation
    frac_transport_tanker = Column(Float, comment="Fraction of product transported by ocean tanker")
    frac_transport_barge = Column(Float, comment="Fraction of product transported by barge")
    frac_transport_pipeline = Column(Float, comment="Fraction of product transported by pipeline")
    frac_transport_rail = Column(Float, comment="Fraction of product transported by rail")
    frac_transport_truck = Column(Float, comment="Fraction of product transported by truck")
    transport_dist_tanker = Column(Float, comment="Transportation distance by ocean tanker in miles")
    transport_dist_barge = Column(Float, comment="Transportation distance by barge in miles")
    transport_dist_pipeline = Column(Float, comment="Transportation distance by pipeline in miles")
    transport_dist_rail = Column(Float, comment="Transportation distance by rail in miles")
    transport_dist_truck = Column(Float, comment="Transportation distance by truck in miles")
    ocean_tanker_size = Column(Float, comment="Ocean tanker size in tonnes")
    
    # Additional data, did not find it in opgee_attributes.xml
    small_sources_emissions = Column(Float, comment="Small sources emissions")
    
    # Any additional attributes
    additional_attributes = Column(JSON, comment="Additional attributes not explicitly defined in the schema")
    
    # Partitioning strategy - for time-based queries
    __table_args__ = (
        # Partition by year to optimize time-based queries
        {"postgresql_partition_by": "RANGE (effective_start_date)"},
    )
