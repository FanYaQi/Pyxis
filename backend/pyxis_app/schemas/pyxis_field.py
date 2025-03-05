"""Pyxis field related schemas."""
from typing import Optional, Dict, Any
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

# Import the same enums from models to ensure consistency
from pyxis_app.postgres.models.pyxis_field import (
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

    pyxis_field_id: str = Field(
        ..., description="Unique identifier for the Pyxis field"
    )
    field_name: Optional[str] = Field(None, description="Name of the field")
    country: Optional[str] = Field(
        None, description="Country where the field is located"
    )
    centroid_h3_index: Optional[str] = Field(
        None, description="H3 index of the field centroid"
    )

    # Geometry will be handled separately since it's a special type


class PyxisFieldMetaCreate(PyxisFieldMetaBase):
    """Schema for creating a new PyxisFieldMeta"""

    geometry_wkt: Optional[str] = Field(
        None, description="WKT representation of the geometry"
    )


class PyxisFieldMetaUpdate(BaseModel):
    """Schema for updating a PyxisFieldMeta"""

    field_name: Optional[str] = None
    country: Optional[str] = None
    centroid_h3_index: Optional[str] = None
    geometry_wkt: Optional[str] = None


class PyxisFieldMetaResponse(PyxisFieldMetaBase):
    """Schema for returning a PyxisFieldMeta"""

    id: int
    geometry_wkt: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# PyxisFieldData schemas
class PyxisFieldDataBase(BaseModel):
    """Base schema for PyxisFieldData"""

    pyxis_field_id: int = Field(..., description="Reference to the Pyxis field ID")
    data_entry_id: int = Field(..., description="Reference to the data entry ID")
    data_entry_version: str = Field(..., description="Version of the data entry")
    source_id: str = Field(..., description="Reference to the data source")
    effective_start_date: datetime = Field(
        ..., description="Start date when these attributes became effective"
    )
    effective_end_date: Optional[datetime] = Field(
        None, description="End date when these attributes were superseded"
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
        None, description="Productivity index in bbl_oil/(psia*day)"
    )
    res_press: Optional[float] = Field(None, description="Reservoir pressure in psia")
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

    # Additional data
    small_sources_emissions: Optional[float] = Field(
        None, description="Small sources emissions"
    )

    # Any additional attributes not explicitly defined
    additional_attributes: Optional[Dict[str, Any]] = Field(
        None, description="Additional attributes not explicitly defined"
    )

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
        if v is not None and (v < 0 or v > 1):
            raise ValueError("Fraction value must be between 0 and 1")
        return v


class PyxisFieldDataCreate(PyxisFieldDataBase):
    """Schema for creating a new PyxisFieldData"""

    pass


class PyxisFieldDataUpdate(BaseModel):
    """Schema for updating PyxisFieldData"""

    # All fields are optional for update
    data_entry_id: Optional[int] = None
    data_entry_version: Optional[str] = None
    source_id: Optional[str] = None
    effective_start_date: Optional[datetime] = None
    effective_end_date: Optional[datetime] = None
    functional_unit: Optional[FunctionalUnit] = None
    downhole_pump: Optional[bool] = None
    water_reinjection: Optional[bool] = None
    natural_gas_reinjection: Optional[bool] = None
    water_flooding: Optional[bool] = None
    gas_lifting: Optional[bool] = None
    gas_flooding: Optional[bool] = None
    steam_flooding: Optional[bool] = None
    oil_sands_mine_type: Optional[OilSandsMineType] = None
    age: Optional[float] = None
    depth: Optional[float] = None
    oil_prod: Optional[float] = None
    num_prod_wells: Optional[int] = None
    num_water_inj_wells: Optional[int] = None
    well_diam: Optional[float] = None
    prod_index: Optional[float] = None
    res_press: Optional[float] = None
    res_temp: Optional[float] = None
    offshore: Optional[bool] = None
    api: Optional[float] = None
    gas_comp_n2: Optional[float] = None
    gas_comp_co2: Optional[float] = None
    gas_comp_c1: Optional[float] = None
    gas_comp_c2: Optional[float] = None
    gas_comp_c3: Optional[float] = None
    gas_comp_c4: Optional[float] = None
    gas_comp_h2s: Optional[float] = None
    gor: Optional[float] = None
    wor: Optional[float] = None
    wir: Optional[float] = None
    glir: Optional[float] = None
    gfir: Optional[float] = None
    flood_gas_type: Optional[FloodGasType] = None
    frac_co2_breakthrough: Optional[float] = None
    co2_source: Optional[CO2SourceType] = None
    perc_sequestration_credit: Optional[float] = None
    sor: Optional[float] = None
    fraction_elec_onsite: Optional[float] = None
    fraction_remaining_gas_inj: Optional[float] = None
    fraction_water_reinjected: Optional[float] = None
    fraction_steam_cogen: Optional[float] = None
    fraction_steam_solar: Optional[float] = None
    heater_treater: Optional[bool] = None
    stabilizer_column: Optional[bool] = None
    upgrader_type: Optional[UpgraderType] = None
    gas_processing_path: Optional[GasProcessingPath] = None
    for_value: Optional[float] = None
    frac_venting: Optional[float] = None
    fraction_diluent: Optional[float] = None
    ecosystem_richness: Optional[EcosystemRichness] = None
    field_development_intensity: Optional[FieldDevelopmentIntensity] = None
    frac_transport_tanker: Optional[float] = None
    frac_transport_barge: Optional[float] = None
    frac_transport_pipeline: Optional[float] = None
    frac_transport_rail: Optional[float] = None
    frac_transport_truck: Optional[float] = None
    transport_dist_tanker: Optional[float] = None
    transport_dist_barge: Optional[float] = None
    transport_dist_pipeline: Optional[float] = None
    transport_dist_rail: Optional[float] = None
    transport_dist_truck: Optional[float] = None
    ocean_tanker_size: Optional[float] = None
    small_sources_emissions: Optional[float] = None
    additional_attributes: Optional[Dict[str, Any]] = None

    # Reuse the validators from the base class
    _validate_fractions = PyxisFieldDataBase.validate_fractions


class PyxisFieldDataResponse(PyxisFieldDataBase):
    """Schema for returning PyxisFieldData"""

    id: int

    class Config:
        from_attributes = True
