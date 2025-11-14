"""
Generate Static Pyxis Field Data for Argentina

This script creates a static field-level dataset for API upload to Pyxis database.
Includes only static attributes as defined in OPGEE_cols_merge_rules.json.

Static attributes include:
- Geometry (from field_shapes_depth_english.csv)
- Functional unit (vote-based from well types across all years)
- Field identifiers (name, country, api_number)
- Reservoir properties (depth, res_press, res_temp, api, gas compositions)
- Production methods (downhole_pump, gas_lifting, water/gas flooding, etc.)
- Transport and infrastructure attributes

Output:
    - argentina_pyxis_static_fields.csv
    - argentina_pyxis_static_fields_config.json

Usage:
    cd data_preparation/argentina/scripts
    pipenv run python 06_generate_static_pyxis_file.py
"""

import sys
from pathlib import Path
from datetime import datetime
import json

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

# ============================================================================
# CONFIGURATION
# ============================================================================

# Unit conversion constants
M3_TO_BBL = 6.28981
MM3_TO_SCF = 35314666.7  # 10^6 * 35.3147
KM3_TO_SCF = 35314.7      # 1000 * 35.3147
M_TO_FT = 3.28084
GOR_THRESHOLD_GAS_FIELD = 100000  # scf/bbl

# Years to aggregate (2009-2024 complete, 2025 partial)
YEARS = list(range(2009, 2025))  # Don't include 2025 since it's incomplete

# Static attributes (from OPGEE_cols_merge_rules.json)
STATIC_ATTRIBUTES = [
    'functional_unit', 'name', 'country', 'downhole_pump', 'water_reinjection',
    'natural_gas_reinjection', 'water_flooding', 'gas_lifting', 'gas_flooding',
    'steam_flooding', 'oil_sands_mine_type', 'age', 'depth', 'well_diam',
    'prod_index', 'res_press', 'res_temp', 'offshore', 'api',
    'gas_comp_n2', 'gas_comp_co2', 'gas_comp_c1', 'gas_comp_c2',
    'gas_comp_c3', 'gas_comp_c4', 'gas_comp_h2s', 'gfir', 'flood_gas_type',
    'frac_co2_breakthrough', 'co2_source', 'perc_sequestration_credit',
    'heater_treater', 'stabilizer_column', 'upgrader_type', 'gas_processing_path',
    'frac_venting', 'fraction_diluent', 'ecosystem_richness',
    'field_development_intensity', 'frac_transport_tanker', 'frac_transport_barge',
    'frac_transport_pipeline', 'frac_transport_rail', 'frac_transport_truck',
    'transport_dist_tanker', 'transport_dist_barge', 'transport_dist_pipeline',
    'transport_dist_rail', 'transport_dist_truck', 'ocean_tanker_size',
    'small_sources_emissions', 'geometry'
]


# ============================================================================
# DATA LOADING FUNCTIONS
# ============================================================================

def load_all_data(translated_dir: Path):
    """Load all required data files."""
    print("Loading data files...")

    data = {}

    # Field shapes (geometry + depth)
    data['field_shapes'] = pd.read_csv(translated_dir / 'field_shapes_depth_english.csv')
    print(f"  ✓ Field shapes: {len(data['field_shapes']):,} fields")

    # Daily production (for functional unit)
    data['daily_oil'] = pd.read_csv(translated_dir / 'daily_oil_production_english.csv')
    data['daily_gas'] = pd.read_csv(translated_dir / 'daily_gas_production_english.csv')
    print(f"  ✓ Daily production: {len(data['daily_oil']):,} oil + {len(data['daily_gas']):,} gas records")

    # Gas field production (for gas data fallback)
    data['gas_field'] = pd.read_csv(translated_dir / 'gas_field_production_english.csv')
    print(f"  ✓ Gas field production: {len(data['gas_field']):,} records")

    # Oil field production (for API gravity)
    data['oil_field'] = pd.read_csv(translated_dir / 'oil_field_production_english.csv')
    print(f"  ✓ Oil field production: {len(data['oil_field']):,} records")

    # Formation/vintage (for injection flags and age)
    data['formation_vintage'] = pd.read_csv(translated_dir / 'field_production_by_formation_vintage_english.csv')
    print(f"  ✓ Formation/vintage: {len(data['formation_vintage']):,} records")

    # Well production files (for well types and extraction methods)
    data['well_prod'] = []
    for year in YEARS:
        well_file = translated_dir / f'well_production_{year}_english.csv'
        if well_file.exists():
            df = pd.read_csv(well_file)
            df['year'] = year
            data['well_prod'].append(df)
            print(f"  ✓ Well production {year}: {len(df):,} records")
        else:
            print(f"  ⚠ Well production file not found for {year}")

    if data['well_prod']:
        data['well_prod'] = pd.concat(data['well_prod'], ignore_index=True)
    else:
        data['well_prod'] = None

    return data


# ============================================================================
# FUNCTIONAL UNIT DETERMINATION (VOTE-BASED)
# ============================================================================

def determine_functional_unit_from_wells(well_data):
    """
    Determine functional unit by voting across well types.

    Args:
        well_data: Well production data with 'well_type' column

    Returns:
        'oil' or 'gas' based on majority vote
    """
    if well_data is None or len(well_data) == 0:
        return 'oil'  # Default

    # Count well types (assuming well_type contains 'oil' or 'gas')
    oil_wells = well_data['well_type'].str.contains('oil', case=False, na=False).sum()
    gas_wells = well_data['well_type'].str.contains('gas', case=False, na=False).sum()

    if gas_wells > oil_wells:
        return 'gas'
    else:
        return 'oil'


def calculate_field_functional_units(well_prod_df, daily_oil, daily_gas, gas_field):
    """
    Calculate functional unit for each field using vote-based approach on well types.

    Args:
        well_prod_df: Combined well production data across all years
        daily_oil: Daily oil production DataFrame
        daily_gas: Daily gas production DataFrame
        gas_field: Gas field production DataFrame (fallback)

    Returns:
        DataFrame with field_id and functional_unit
    """
    print("\nCalculating functional units (vote-based on well types)...")

    functional_units = []

    # Get all unique fields
    all_fields = set()
    if well_prod_df is not None:
        all_fields.update(well_prod_df['field_id'].unique())
    all_fields.update(daily_oil['field_id'].unique())
    all_fields.update(daily_gas['field_id'].unique())

    for field_id in all_fields:
        # Get well data for this field across all years
        if well_prod_df is not None:
            field_wells = well_prod_df[well_prod_df['field_id'] == field_id]
        else:
            field_wells = None

        functional_unit = determine_functional_unit_from_wells(field_wells)

        # Get field name
        field_name = None
        oil_match = daily_oil[daily_oil['field_id'] == field_id]
        gas_match = daily_gas[daily_gas['field_id'] == field_id]

        if len(oil_match) > 0:
            field_name = oil_match['field_name'].iloc[0]
        elif len(gas_match) > 0:
            field_name = gas_match['field_name'].iloc[0]
        else:
            field_name = field_id

        functional_units.append({
            'field_id': field_id,
            'field_name': field_name,
            'functional_unit': functional_unit
        })

    func_units_df = pd.DataFrame(functional_units)

    # Summary
    type_counts = func_units_df['functional_unit'].value_counts()
    print(f"  Functional unit distribution:")
    for ftype, count in type_counts.items():
        print(f"    {ftype}: {count} fields ({count/len(func_units_df)*100:.1f}%)")

    return func_units_df


# ============================================================================
# STATIC ATTRIBUTE AGGREGATION
# ============================================================================

def calculate_api_from_density(density_ton_m3):
    """Calculate API gravity from density."""
    if pd.isna(density_ton_m3) or density_ton_m3 <= 0:
        return None
    api = (141.5 / density_ton_m3) - 131.5
    return api if api > 0 else None


def aggregate_static_attributes(data, field_id, field_name):
    """
    Aggregate static attributes for a field across all years.

    Uses voting for binary/discrete values and averaging for numeric values.

    Args:
        data: Dictionary of loaded DataFrames
        field_id: Field ID
        field_name: Field name

    Returns:
        Dictionary of aggregated static attributes
    """
    field_data = {
        'field_id': field_id,
        'name': field_name,
        'country': 'Argentina'
    }

    # ========================================================================
    # GEOMETRY & DEPTH (from field_shapes)
    # ========================================================================
    shapes = data['field_shapes'][data['field_shapes']['field_id'] == field_id]
    if len(shapes) > 0:
        # Use most recent geometry (last row)
        shape = shapes.iloc[-1]
        field_data['geometry'] = shape.get('field_boundary_geojson')  # GeoJSON format
        depth_m = shape.get('depth_avg_m')
        field_data['depth'] = depth_m * M_TO_FT if pd.notna(depth_m) else None
    else:
        field_data['geometry'] = None
        field_data['depth'] = None

    # ========================================================================
    # AGE (from formation_vintage - store YEAR not age)
    # ========================================================================
    formation = data['formation_vintage'][data['formation_vintage']['field_id'] == field_id]
    if len(formation) > 0 and 'well_vintage_year' in formation.columns:
        vintage_years = formation['well_vintage_year'].dropna()
        if len(vintage_years) > 0:
            field_data['age'] = int(vintage_years.min())  # Earliest year
        else:
            field_data['age'] = None
    else:
        field_data['age'] = None

    # ========================================================================
    # API GRAVITY (from oil_field - average across all years)
    # ========================================================================
    oil_field = data['oil_field'][data['oil_field']['field_id'] == field_id]
    density_data = oil_field[oil_field['concept'] == 'oil_density_avg_ton_per_m3']
    if len(density_data) > 0:
        avg_density = density_data['quantity'].mean()
        field_data['api'] = calculate_api_from_density(avg_density)
    else:
        field_data['api'] = None

    # ========================================================================
    # INJECTION FLAGS & METHODS (vote across all years)
    # ========================================================================
    if len(formation) > 0:
        # Water flooding (vote)
        water_inj_records = formation['water_injection_m3'].fillna(0) > 0
        field_data['water_flooding'] = water_inj_records.sum() > len(formation) / 2

        # Gas flooding (vote)
        gas_inj_records = formation['gas_injection_km3'].fillna(0) > 0
        field_data['gas_flooding'] = gas_inj_records.sum() > len(formation) / 2
    else:
        field_data['water_flooding'] = False
        field_data['gas_flooding'] = False

    # ========================================================================
    # GAS REINJECTION (vote from gas_field)
    # ========================================================================
    gas_field = data['gas_field'][data['gas_field']['field_id'] == field_id]
    if len(gas_field) > 0:
        gas_reinj = gas_field[gas_field['concept'] == 'gas_reinjection_formation_mm3']
        field_data['natural_gas_reinjection'] = len(gas_reinj[gas_reinj['quantity'] > 0]) > 0
    else:
        field_data['natural_gas_reinjection'] = False

    # ========================================================================
    # EXTRACTION METHODS (vote from well_prod)
    # ========================================================================
    if data['well_prod'] is not None:
        well_data = data['well_prod'][data['well_prod']['field_id'] == field_id]
        if len(well_data) > 0:
            extraction_methods = well_data['extraction_method'].value_counts()
            field_data['downhole_pump'] = 'mechanical_pump' in extraction_methods.index
            field_data['gas_lifting'] = 'gas_lift' in extraction_methods.index
        else:
            field_data['downhole_pump'] = None
            field_data['gas_lifting'] = None
    else:
        field_data['downhole_pump'] = None
        field_data['gas_lifting'] = None

    # ========================================================================
    # OFFSHORE (vote from gas_field location)
    # ========================================================================
    if len(gas_field) > 0 and 'location' in gas_field.columns:
        offshore_records = gas_field['location'] == 'Offshore'
        field_data['offshore'] = offshore_records.sum() > len(gas_field) / 2
    else:
        field_data['offshore'] = False

    # ========================================================================
    # ADDITIONAL STATIC ATTRIBUTES (set to None - not in Argentina data)
    # ========================================================================
    # These would come from other data sources in future
    for attr in ['water_reinjection', 'steam_flooding', 'oil_sands_mine_type',
                 'well_diam', 'prod_index', 'res_press', 'res_temp',
                 'gas_comp_n2', 'gas_comp_co2', 'gas_comp_c1', 'gas_comp_c2',
                 'gas_comp_c3', 'gas_comp_c4', 'gas_comp_h2s', 'gfir',
                 'flood_gas_type', 'frac_co2_breakthrough', 'co2_source',
                 'perc_sequestration_credit', 'heater_treater', 'stabilizer_column',
                 'upgrader_type', 'gas_processing_path', 'frac_venting',
                 'fraction_diluent', 'ecosystem_richness', 'field_development_intensity',
                 'frac_transport_tanker', 'frac_transport_barge', 'frac_transport_pipeline',
                 'frac_transport_rail', 'frac_transport_truck', 'transport_dist_tanker',
                 'transport_dist_barge', 'transport_dist_pipeline', 'transport_dist_rail',
                 'transport_dist_truck', 'ocean_tanker_size', 'small_sources_emissions']:
        if attr not in field_data:
            field_data[attr] = None

    return field_data


# ============================================================================
# CONFIG FILE GENERATION
# ============================================================================

def generate_config_json(output_dir: Path):
    """Generate config JSON for static data upload."""
    config = {
        "data_metadata": {
            "name": "Argentina Static Field Data",
            "description": "Static field attributes for Argentina oil and gas fields (2009-2024)",
            "type": "csv",
            "version": "1.0.0",
            "attributes": [
                {"name": "field_id", "type": "string", "units": None},
                {"name": "name", "type": "string", "units": None},
                {"name": "country", "type": "string", "units": None},
                {"name": "functional_unit", "type": "string", "units": None},
                {"name": "geometry", "type": "geometry", "units": None},
                {"name": "depth", "type": "number", "units": "ft"},
                {"name": "age", "type": "integer", "units": "year"},
                {"name": "api", "type": "number", "units": "degrees"},
                {"name": "offshore", "type": "boolean", "units": None},
                {"name": "water_flooding", "type": "boolean", "units": None},
                {"name": "gas_flooding", "type": "boolean", "units": None},
                {"name": "natural_gas_reinjection", "type": "boolean", "units": None},
                {"name": "downhole_pump", "type": "boolean", "units": None},
                {"name": "gas_lifting", "type": "boolean", "units": None}
            ]
        },
        "mappings": [
            {"source_attribute": "name", "target_attribute": "name"},
            {"source_attribute": "country", "target_attribute": "country"},
            {"source_attribute": "functional_unit", "target_attribute": "functional_unit"},
            {"source_attribute": "geometry", "target_attribute": "geometry"},
            {"source_attribute": "depth", "target_attribute": "depth"},
            {"source_attribute": "age", "target_attribute": "age"},
            {"source_attribute": "api", "target_attribute": "api"},
            {"source_attribute": "offshore", "target_attribute": "offshore"},
            {"source_attribute": "water_flooding", "target_attribute": "water_flooding"},
            {"source_attribute": "gas_flooding", "target_attribute": "gas_flooding"},
            {"source_attribute": "natural_gas_reinjection", "target_attribute": "natural_gas_reinjection"},
            {"source_attribute": "downhole_pump", "target_attribute": "downhole_pump"},
            {"source_attribute": "gas_lifting", "target_attribute": "gas_lifting"}
        ],
        "file_specific": {
            "csv": {
                "delimiter": ",",
                "encoding": "utf-8",
                "header_row": 0
            }
        }
    }

    config_file = output_dir / 'argentina_pyxis_static_fields_config.json'
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)

    print(f"\n✅ Config file saved: {config_file}")
    return config_file


# ============================================================================
# MAIN PIPELINE
# ============================================================================

def main():
    """Main pipeline execution."""
    print("="*70)
    print("ARGENTINA → PYXIS STATIC FIELD DATA GENERATION")
    print("="*70)
    print(f"Aggregating data from {YEARS[0]}-{YEARS[-1]}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Paths
    base_dir = Path(__file__).parent.parent
    translated_dir = base_dir / 'raw' / 'translated'
    output_dir = base_dir / 'output'
    output_dir.mkdir(exist_ok=True)

    # Load all data
    data = load_all_data(translated_dir)

    # Calculate functional units
    func_units = calculate_field_functional_units(
        data['well_prod'],
        data['daily_oil'],
        data['daily_gas'],
        data['gas_field']
    )

    # Process each field
    print("\nAggregating static attributes...")
    static_fields = []

    for _, row in func_units.iterrows():
        field_id = row['field_id']
        field_name = row['field_name']
        functional_unit = row['functional_unit']

        field_static = aggregate_static_attributes(data, field_id, field_name)
        field_static['functional_unit'] = functional_unit

        static_fields.append(field_static)

    # Create DataFrame
    output_df = pd.DataFrame(static_fields)

    # Reorder columns
    column_order = ['field_id', 'name', 'country', 'functional_unit', 'geometry',
                    'depth', 'age', 'api', 'offshore', 'water_flooding', 'gas_flooding',
                    'natural_gas_reinjection', 'downhole_pump', 'gas_lifting']

    # Add remaining columns not in order
    remaining_cols = [col for col in output_df.columns if col not in column_order]
    column_order.extend(remaining_cols)

    output_df = output_df[column_order]

    # Save CSV
    output_file = output_dir / 'argentina_pyxis_static_fields.csv'
    output_df.to_csv(output_file, index=False)

    # Generate config JSON
    config_file = generate_config_json(output_dir)

    # Summary
    print(f"\n{'='*70}")
    print(f"✅ PROCESSING COMPLETE")
    print(f"{'='*70}")
    print(f"Output file: {output_file}")
    print(f"Config file: {config_file}")
    print(f"Total fields: {len(output_df):,}")
    print(f"\nFunctional unit distribution:")
    for ftype, count in output_df['functional_unit'].value_counts().items():
        print(f"  {ftype}: {count:,} fields ({count/len(output_df)*100:.1f}%)")

    print(f"\nData completeness:")
    total = len(output_df)
    for col in ['geometry', 'depth', 'age', 'api', 'offshore']:
        non_null = output_df[col].notna().sum()
        print(f"  {col}: {non_null:,}/{total:,} ({non_null/total*100:.1f}%)")

    print(f"\nFinished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
