"""Pyxis field related schemas."""

from typing import Optional, Dict, Any
from datetime import datetime

from pydantic import BaseModel, Field, field_validator, ConfigDict, field_serializer
from geoalchemy2.types import WKBElement
from geoalchemy2.shape import to_shape


# Import the same enums from models to ensure consistency
from app.postgres.models.pyxis_field import (
    FunctionalUnit,
    OilSandsMineType,
    FloodGasType,
    CO2SourceType,
    UpgraderType,
    GasProcessingPath,
    EcosystemRichness,
    FieldDevelopmentIntensity,
)


# PyxisFieldMeta schemas
class PyxisFieldMetaBase(BaseModel):
    """Base schema for PyxisFieldMeta"""
    
    model_config = ConfigDict(arbitrary_types_allowed=True)

    pyxis_field_code: str = Field(
        ..., description="Unique identifier for the Pyxis field"
    )
    name: Optional[str] = Field(None, description="Name of the field")
    country: Optional[str] = Field(
        None, description="Country where the field is located"
    )
    latitude: Optional[float] = Field(None, description="Latitude of the field")
    longitude: Optional[float] = Field(None, description="Longitude of the field")
    centroid_h3_index: Optional[str] = Field(
        None, description="H3 index of the field centroid"
    )
    geometry: Optional[WKBElement] = Field(
        None, description="Geometry of the field", exclude=True
    )
    
    # Functional attributes
    functional_unit: Optional[FunctionalUnit] = Field(
        None, description="Whether the field produces primarily oil or gas"
    )

    # Production methods
    downhole_pump: Optional[bool] = Field(
        None, description="Whether the field uses downhole pumps"
    )
    water_reinjection: Optional[bool] = Field(
        None, description="Whether the field uses water reinjection"
    )
    natural_gas_reinjection: Optional[bool] = Field(
        None, description="Whether the field uses natural gas reinjection"
    )
    water_flooding: Optional[bool] = Field(
        None, description="Whether the field uses water flooding"
    )
    gas_lifting: Optional[bool] = Field(
        None, description="Whether the field uses gas lifting"
    )
    gas_flooding: Optional[bool] = Field(
        None, description="Whether the field uses gas flooding"
    )
    steam_flooding: Optional[bool] = Field(
        None, description="Whether the field uses steam flooding"
    )
    oil_sands_mine_type: Optional[OilSandsMineType] = Field(
        None, description="Type of oil sands mining operation"
    )

    # Field properties
    age: Optional[float] = Field(None, description="Age of the field in years")
    depth: Optional[float] = Field(None, description="Depth of the field in feet")
    oil_prod: Optional[float] = Field(
        None, description="Oil production volume in barrels per day"
    )
    num_prod_wells: Optional[int] = Field(None, description="Number of producing wells")
    num_water_inj_wells: Optional[int] = Field(
        None, description="Number of water injecting wells"
    )
    well_diam: Optional[float] = Field(
        None, description="Production tubing diameter in inches"
    )
    prod_index: Optional[float] = Field(
        None, description="Productivity index in bbl_oil/(psi*day)"
    )
    res_press: Optional[float] = Field(None, description="Reservoir pressure in psi")
    res_temp: Optional[float] = Field(
        None, description="Reservoir temperature in degrees Fahrenheit"
    )
    offshore: Optional[bool] = Field(None, description="Whether the field is offshore")

    # Oil and gas properties
    api: Optional[float] = Field(
        None, description="API gravity of oil at standard pressure and temperature"
    )
    gas_comp_n2: Optional[float] = Field(
        None, description="Percentage of N2 in the gas composition"
    )
    gas_comp_co2: Optional[float] = Field(
        None, description="Percentage of CO2 in the gas composition"
    )
    gas_comp_c1: Optional[float] = Field(
        None, description="Percentage of C1 (methane) in the gas composition"
    )
    gas_comp_c2: Optional[float] = Field(
        None, description="Percentage of C2 (ethane) in the gas composition"
    )
    gas_comp_c3: Optional[float] = Field(
        None, description="Percentage of C3 (propane) in the gas composition"
    )
    gas_comp_c4: Optional[float] = Field(
        None, description="Percentage of C4+ (butane+) in the gas composition"
    )
    gas_comp_h2s: Optional[float] = Field(
        None, description="Percentage of H2S in the gas composition"
    )

    # Ratios
    gor: Optional[float] = Field(
        None, description="Gas-to-oil ratio in scf/bbl_oil"
    )
    wor: Optional[float] = Field(
        None, description="Water-to-oil ratio in bbl_water/bbl_oil"
    )
    wir: Optional[float] = Field(
        None, description="Water injection ratio in bbl_water/bbl_oil"
    )
    glir: Optional[float] = Field(
        None, description="Gas lifting injection ratio in scf/bbl_liquid"
    )
    gfir: Optional[float] = Field(
        None, description="Gas flooding injection ratio in scf/bbl_oil"
    )
    flood_gas_type: Optional[FloodGasType] = Field(
        None, description="Type of gas used for flooding"
    )
    frac_co2_breakthrough: Optional[float] = Field(
        None, description="Fraction of CO2 breaking through to producers"
    )
    co2_source: Optional[CO2SourceType] = Field(
        None, description="Source of makeup CO2"
    )
    perc_sequestration_credit: Optional[float] = Field(
        None, description="Percentage of sequestration credit assigned to the oilfield"
    )
    sor: Optional[float] = Field(
        None, description="Steam-to-oil ratio in bbl_steam/bbl_oil"
    )

    # Fractions and processing
    fraction_elec_onsite: Optional[float] = Field(
        None, description="Fraction of required fossil electricity generated onsite"
    )
    fraction_remaining_gas_inj: Optional[float] = Field(
        None, description="Fraction of remaining natural gas reinjected"
    )
    fraction_water_reinjected: Optional[float] = Field(
        None, description="Fraction of produced water reinjected"
    )
    fraction_steam_cogen: Optional[float] = Field(
        None, description="Fraction of steam generation via cogeneration"
    )
    fraction_steam_solar: Optional[float] = Field(
        None, description="Fraction of steam generation via solar thermal"
    )
    heater_treater: Optional[bool] = Field(
        None, description="Whether a heater/treater is used"
    )
    stabilizer_column: Optional[bool] = Field(
        None, description="Whether a stabilizer column is used"
    )
    upgrader_type: Optional[UpgraderType] = Field(
        None, description="Type of upgrader used"
    )
    gas_processing_path: Optional[GasProcessingPath] = Field(
        None, description="Associated gas processing path"
    )
    for_value: Optional[float] = Field(
        None, description="Flaring-to-oil ratio in scf/bbl_oil"
    )
    frac_venting: Optional[float] = Field(
        None, description="Purposeful venting fraction (post-flare gas fraction vented)"
    )
    fraction_diluent: Optional[float] = Field(
        None, description="Volume fraction of diluent"
    )

    # Land use impact
    ecosystem_richness: Optional[EcosystemRichness] = Field(
        None, description="Ecosystem carbon richness category"
    )
    field_development_intensity: Optional[FieldDevelopmentIntensity] = Field(
        None, description="Field development intensity category"
    )

    # Transportation
    frac_transport_tanker: Optional[float] = Field(
        None, description="Fraction of product transported by ocean tanker"
    )
    frac_transport_barge: Optional[float] = Field(
        None, description="Fraction of product transported by barge"
    )
    frac_transport_pipeline: Optional[float] = Field(
        None, description="Fraction of product transported by pipeline"
    )
    frac_transport_rail: Optional[float] = Field(
        None, description="Fraction of product transported by rail"
    )
    frac_transport_truck: Optional[float] = Field(
        None, description="Fraction of product transported by truck"
    )
    transport_dist_tanker: Optional[float] = Field(
        None, description="Transportation distance by ocean tanker in miles"
    )
    transport_dist_barge: Optional[float] = Field(
        None, description="Transportation distance by barge in miles"
    )
    transport_dist_pipeline: Optional[float] = Field(
        None, description="Transportation distance by pipeline in miles"
    )
    transport_dist_rail: Optional[float] = Field(
        None, description="Transportation distance by rail in miles"
    )
    transport_dist_truck: Optional[float] = Field(
        None, description="Transportation distance by truck in miles"
    )
    ocean_tanker_size: Optional[float] = Field(
        None, description="Ocean tanker size in tonnes"
    )
    small_sources_emissions: Optional[float] = Field(
        None, description="Small sources emissions"
    )

    # Additional attributes
    additional_attributes: Optional[Dict[str, Any]] = Field(
        None, description="Additional attributes not explicitly defined in the schema"
    )

    @field_serializer("geometry")
    def serialize_geometry(self, geometry: WKBElement):
        if geometry:
            return to_shape(geometry).wkt
        return None

    # Validators for fraction fields to ensure they're between 0 and 1
    @field_validator(
        "fraction_elec_onsite",
        "fraction_remaining_gas_inj",
        "fraction_water_reinjected",
        "fraction_steam_cogen",
        "fraction_steam_solar",
        "frac_venting",
        "fraction_diluent",
        "frac_transport_tanker",
        "frac_transport_barge",
        "frac_transport_pipeline",
        "frac_transport_rail",
        "frac_transport_truck",
    )
    @classmethod
    def validate_fractions(cls, v):
        """Validate fractions to ensure they're between 0 and 1."""
        if v is not None and (v < 0 or v > 100):
            raise ValueError("Fraction value must be between 0 and 1")
        return v


class PyxisFieldMetaResponse(PyxisFieldMetaBase):
    """Schema for returning a PyxisFieldMeta"""

    id: int
    geometry_wkt: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


# PyxisFieldData schemas
class PyxisFieldDataBase(BaseModel):
    """Base schema for PyxisFieldData"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    pyxis_field_meta_id: Optional[int] = Field(
        ..., description="Reference to the Pyxis field meta ID"
    )
    data_entry_id: int = Field(..., description="Reference to the data entry ID")
    effective_start_date: datetime = Field(
        ..., description="Start date when these attributes became effective"
    )
    effective_end_date: Optional[datetime] = Field(
        None, description="End date when these attributes were superseded"
    )

    name: Optional[str] = Field(None, description="Name of the field")
    country: Optional[str] = Field(None, description="Country of the field")
    latitude: Optional[float] = Field(None, description="Latitude of the field")
    longitude: Optional[float] = Field(None, description="Longitude of the field")
    centroid_h3_index: Optional[str] = Field(
        None, description="H3 index of the field centroid"
    )
    geometry: Optional[WKBElement] = Field(
        None, description="Geometry of the field", exclude=True
    )

    # Functional attributes
    functional_unit: Optional[FunctionalUnit] = Field(
        None, description="Whether the field produces primarily oil or gas"
    )

    # Production methods
    downhole_pump: Optional[bool] = Field(
        None, description="Whether the field uses downhole pumps"
    )
    water_reinjection: Optional[bool] = Field(
        None, description="Whether the field uses water reinjection"
    )
    natural_gas_reinjection: Optional[bool] = Field(
        None, description="Whether the field uses natural gas reinjection"
    )
    water_flooding: Optional[bool] = Field(
        None, description="Whether the field uses water flooding"
    )
    gas_lifting: Optional[bool] = Field(
        None, description="Whether the field uses gas lifting"
    )
    gas_flooding: Optional[bool] = Field(
        None, description="Whether the field uses gas flooding"
    )
    steam_flooding: Optional[bool] = Field(
        None, description="Whether the field uses steam flooding"
    )
    oil_sands_mine_type: Optional[OilSandsMineType] = Field(
        None, description="Type of oil sands mining operation"
    )

    # Field properties
    age: Optional[float] = Field(None, description="Age of the field in years")
    depth: Optional[float] = Field(None, description="Depth of the field in feet")
    oil_prod: Optional[float] = Field(
        None, description="Oil production volume in barrels per day"
    )
    num_prod_wells: Optional[int] = Field(None, description="Number of producing wells")
    num_water_inj_wells: Optional[int] = Field(
        None, description="Number of water injecting wells"
    )
    well_diam: Optional[float] = Field(
        None, description="Production tubing diameter in inches"
    )
    prod_index: Optional[float] = Field(
        None, description="Productivity index in bbl_oil/(psi*day)"
    )
    res_press: Optional[float] = Field(None, description="Reservoir pressure in psi")
    res_temp: Optional[float] = Field(
        None, description="Reservoir temperature in degrees Fahrenheit"
    )
    offshore: Optional[bool] = Field(None, description="Whether the field is offshore")

    # Oil and gas properties
    api: Optional[float] = Field(
        None, description="API gravity of oil at standard pressure and temperature"
    )
    gas_comp_n2: Optional[float] = Field(
        None, description="Percentage of N2 in the gas composition"
    )
    gas_comp_co2: Optional[float] = Field(
        None, description="Percentage of CO2 in the gas composition"
    )
    gas_comp_c1: Optional[float] = Field(
        None, description="Percentage of C1 (methane) in the gas composition"
    )
    gas_comp_c2: Optional[float] = Field(
        None, description="Percentage of C2 (ethane) in the gas composition"
    )
    gas_comp_c3: Optional[float] = Field(
        None, description="Percentage of C3 (propane) in the gas composition"
    )
    gas_comp_c4: Optional[float] = Field(
        None, description="Percentage of C4+ (butane+) in the gas composition"
    )
    gas_comp_h2s: Optional[float] = Field(
        None, description="Percentage of H2S in the gas composition"
    )

    # Ratios
    gor: Optional[float] = Field(None, description="Gas-to-oil ratio in scf/bbl_oil")
    wor: Optional[float] = Field(
        None, description="Water-to-oil ratio in bbl_water/bbl_oil"
    )
    wir: Optional[float] = Field(
        None, description="Water injection ratio in bbl_water/bbl_oil"
    )
    glir: Optional[float] = Field(
        None, description="Gas lifting injection ratio in scf/bbl_liquid"
    )
    gfir: Optional[float] = Field(
        None, description="Gas flooding injection ratio in scf/bbl_oil"
    )
    flood_gas_type: Optional[FloodGasType] = Field(
        None, description="Type of gas used for flooding"
    )
    frac_co2_breakthrough: Optional[float] = Field(
        None, description="Fraction of CO2 breaking through to producers"
    )
    co2_source: Optional[CO2SourceType] = Field(
        None, description="Source of makeup CO2"
    )
    perc_sequestration_credit: Optional[float] = Field(
        None, description="Percentage of sequestration credit assigned to the oilfield"
    )
    sor: Optional[float] = Field(
        None, description="Steam-to-oil ratio in bbl_steam/bbl_oil"
    )

    # Fractions and processing
    fraction_elec_onsite: Optional[float] = Field(
        None, description="Fraction of required fossil electricity generated onsite"
    )
    fraction_remaining_gas_inj: Optional[float] = Field(
        None, description="Fraction of remaining natural gas reinjected"
    )
    fraction_water_reinjected: Optional[float] = Field(
        None, description="Fraction of produced water reinjected"
    )
    fraction_steam_cogen: Optional[float] = Field(
        None, description="Fraction of steam generation via cogeneration"
    )
    fraction_steam_solar: Optional[float] = Field(
        None, description="Fraction of steam generation via solar thermal"
    )
    heater_treater: Optional[bool] = Field(
        None, description="Whether a heater/treater is used"
    )
    stabilizer_column: Optional[bool] = Field(
        None, description="Whether a stabilizer column is used"
    )
    upgrader_type: Optional[UpgraderType] = Field(
        None, description="Type of upgrader used"
    )
    gas_processing_path: Optional[GasProcessingPath] = Field(
        None, description="Associated gas processing path"
    )
    for_value: Optional[float] = Field(
        None, description="Flaring-to-oil ratio in scf/bbl_oil"
    )
    frac_venting: Optional[float] = Field(
        None, description="Purposeful venting fraction (post-flare gas fraction vented)"
    )
    fraction_diluent: Optional[float] = Field(
        None, description="Volume fraction of diluent"
    )

    # Land use impact
    ecosystem_richness: Optional[EcosystemRichness] = Field(
        None, description="Ecosystem carbon richness category"
    )
    field_development_intensity: Optional[FieldDevelopmentIntensity] = Field(
        None, description="Field development intensity category"
    )

    # Transportation
    frac_transport_tanker: Optional[float] = Field(
        None, description="Fraction of product transported by ocean tanker"
    )
    frac_transport_barge: Optional[float] = Field(
        None, description="Fraction of product transported by barge"
    )
    frac_transport_pipeline: Optional[float] = Field(
        None, description="Fraction of product transported by pipeline"
    )
    frac_transport_rail: Optional[float] = Field(
        None, description="Fraction of product transported by rail"
    )
    frac_transport_truck: Optional[float] = Field(
        None, description="Fraction of product transported by truck"
    )
    transport_dist_tanker: Optional[float] = Field(
        None, description="Transportation distance by ocean tanker in miles"
    )
    transport_dist_barge: Optional[float] = Field(
        None, description="Transportation distance by barge in miles"
    )
    transport_dist_pipeline: Optional[float] = Field(
        None, description="Transportation distance by pipeline in miles"
    )
    transport_dist_rail: Optional[float] = Field(
        None, description="Transportation distance by rail in miles"
    )
    transport_dist_truck: Optional[float] = Field(
        None, description="Transportation distance by truck in miles"
    )
    ocean_tanker_size: Optional[float] = Field(
        None, description="Ocean tanker size in tonnes"
    )
    small_sources_emissions: Optional[float] = Field(
        None, description="Small sources emissions"
    )

    # Additional data
    additional_attributes: Optional[Dict[str, Any]] = Field(
        None, description="Additional attributes not explicitly defined"
    )

    @field_serializer("geometry")
    def serialize_geometry(self, geometry: WKBElement):
        return to_shape(geometry).wkt if geometry else None

    # Validators for fraction fields to ensure they're between 0 and 1
    @field_validator(
        "fraction_elec_onsite",
        "fraction_remaining_gas_inj",
        "fraction_water_reinjected",
        "fraction_steam_cogen",
        "fraction_steam_solar",
        "frac_venting",
        "fraction_diluent",
        "frac_transport_tanker",
        "frac_transport_barge",
        "frac_transport_pipeline",
        "frac_transport_rail",
        "frac_transport_truck",
    )
    @classmethod
    def validate_fractions(cls, v):
        """Validate fractions to ensure they're between 0 and 1."""
        if v is not None and (v < 0 or v > 100):
            raise ValueError("Fraction value must be between 0 and 1")
        return v


class PyxisFieldDataResponse(PyxisFieldDataBase):
    """Schema for returning PyxisFieldData"""

    id: int