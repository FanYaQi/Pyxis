"""
Common mappings and utilities for OPGEE/Pyxis attributes.
"""

# Unit conversion constants
M3_TO_BBL = 6.28981  # Cubic meters to barrels
KM3_TO_MCF = 35314666.7  # Cubic kilometers to thousand cubic feet
KM3_TO_M3 = 1e9  # Cubic kilometers to cubic meters


def convert_oil_m3_to_bbl(volume_m3: float) -> float:
    """Convert oil volume from cubic meters to barrels."""
    return volume_m3 * M3_TO_BBL


def convert_gas_km3_to_mcf(volume_km3: float) -> float:
    """Convert gas volume from cubic kilometers to thousand cubic feet."""
    return volume_km3 * KM3_TO_MCF


def convert_gas_km3_to_m3(volume_km3: float) -> float:
    """Convert gas volume from cubic kilometers to cubic meters."""
    return volume_km3 * KM3_TO_M3


def determine_functional_unit(oil_prod: float, gas_prod: float, threshold_gor: float = 100) -> str:
    """
    Determine if a field is primarily 'oil' or 'gas' based on production ratio.

    Args:
        oil_prod: Oil production volume (any unit, as long as consistent)
        gas_prod: Gas production volume (any unit, as long as consistent)
        threshold_gor: GOR threshold to classify as gas field (default: 100)

    Returns:
        'oil' or 'gas'
    """
    if oil_prod == 0 and gas_prod == 0:
        return "oil"  # Default to oil if no production

    if oil_prod == 0:
        return "gas"

    # Calculate GOR (gas-to-oil ratio)
    gor = gas_prod / oil_prod if oil_prod > 0 else float('inf')

    return "gas" if gor > threshold_gor else "oil"


# Common OPGEE attribute mappings (reference)
OPGEE_CORE_ATTRIBUTES = {
    # Identification
    "name": "Field name",
    "country": "Country",
    "field_location": "Field location",

    # Spatial
    "latitude": "Latitude",
    "longitude": "Longitude",
    "centroid_h3_index": "H3 spatial index",
    "geometry": "Geometry (WKT)",

    # Temporal
    "start_date": "Start date (YYYY-MM-DD)",
    "end_date": "End date (YYYY-MM-DD)",

    # Production
    "functional_unit": "Oil or gas (functional unit)",
    "oil_prod": "Oil production volume",
    "gas_prod": "Gas production volume",
    "num_prod_wells": "Number of producing wells",
    "gor": "Gas-to-oil ratio",
    "wor": "Water-to-oil ratio",

    # Technical
    "api": "API gravity",
    "depth": "Well depth",
    "offshore": "Offshore (0/1)",

    # Operations
    "downhole_pump": "Downhole pump (0/1)",
    "water_reinjection": "Water reinjection (0/1)",
    "gas_lifting": "Gas lifting (0/1)",
    "water_flooding": "Water flooding (0/1)",
    "steam_flooding": "Steam flooding (0/1)",

    # Emissions
    "flaring_to_oil_ratio": "Flaring to oil ratio",
}
