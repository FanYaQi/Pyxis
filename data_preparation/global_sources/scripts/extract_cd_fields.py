"""
Extract static field data from CD (Commercial Dataset) for a specific country.

Usage:
    python extract_cd_fields.py --country Argentina
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

# Constants
M_TO_FT = 3.28084
GOR_THRESHOLD = 2000  # scf/bbl threshold for oil vs gas (typical industry standard)

# Data paths
SCRIPTS_DIR = Path(__file__).parent
OUTPUT_DIR = SCRIPTS_DIR.parent / 'output'
DATA_DIR = Path(__file__).parent.parent.parent.parent / 'scripts_n_notebooks' / 'data'
EXCEL_PATH = DATA_DIR / 'wm_well' / 'WM_LENS_upstream_weekly-field_summary_accessed 10052022_SEED.xlsx'
GEOMETRY_PATH = DATA_DIR / 'wm_well' / 'global_wm_fields.json'


def parse_flood_gas_type(tertiary_mechanism: str) -> Optional[str]:
    """Parse flood gas type from tertiary drive mechanism."""
    if pd.isna(tertiary_mechanism):
        return None

    mechanism = str(tertiary_mechanism).lower()

    if 'co2' in mechanism or 'carbon dioxide' in mechanism:
        return 'CO2'
    elif 'n2' in mechanism or 'nitrogen' in mechanism:
        return 'N2'
    elif 'natural gas' in mechanism or 'gas' in mechanism:
        return 'Natural Gas'

    return None


def parse_production_methods(row: pd.Series) -> Dict[str, int]:
    """
    Parse production methods from drive mechanism columns.
    Returns dict with binary indicators for each method.
    """
    methods = {
        'water_flooding': 0,
        'gas_flooding': 0,
        'natural_gas_reinjection': 0,
        'downhole_pump': 0,
        'gas_lifting': 0
    }

    # Concatenate all drive mechanism columns
    drive_cols = ['field_drive_mechanism_primary', 'field_drive_mechanism_second', 'field_drive_mechanism_tertiary']
    all_mechanisms = []

    for col in drive_cols:
        if col in row and pd.notna(row[col]):
            all_mechanisms.append(str(row[col]).lower())

    combined = ' '.join(all_mechanisms)

    # Check for each production method
    if 'water flood' in combined or 'waterflood' in combined or 'water injection' in combined:
        methods['water_flooding'] = 1

    if 'gas flood' in combined or 'gasflood' in combined or 'co2' in combined or 'nitrogen' in combined:
        methods['gas_flooding'] = 1

    if 'gas injection' in combined or 'gas reinjection' in combined:
        methods['natural_gas_reinjection'] = 1

    if 'pump' in combined or 'artificial lift' in combined or 'esp' in combined:
        methods['downhole_pump'] = 1

    if 'gas lift' in combined:
        methods['gas_lifting'] = 1

    return methods


def extract_cd_fields(country: str) -> pd.DataFrame:
    """
    Extract static field data from CD for specified country.

    Args:
        country: Country name (e.g., "Argentina")

    Returns:
        DataFrame with extracted field data
    """
    print(f"=== Extracting CD Fields for {country} ===")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Load Excel data
    print(f"\n1. Loading Excel data from {EXCEL_PATH.name}...")
    df = pd.read_excel(EXCEL_PATH)
    print(f"   Total records: {len(df):,}")

    # Filter by country
    country_df = df[df['country_name'] == country].copy()
    print(f"   {country} records: {len(country_df):,}")

    if len(country_df) == 0:
        print(f"   WARNING: No records found for {country}")
        return pd.DataFrame()

    # Load geometry data
    print(f"\n2. Loading geometry data from {GEOMETRY_PATH.name}...")
    with open(GEOMETRY_PATH, 'r') as f:
        geom_data = json.load(f)

    # Extract geometry features into DataFrame
    geom_records = []
    for feature in geom_data.get('features', []):
        props = feature.get('properties', {})
        geom_records.append({
            'id_field_a': props.get('id_field_a'),
            'geometry': json.dumps(feature.get('geometry'))
        })

    geom_df = pd.DataFrame(geom_records)
    print(f"   Total geometries: {len(geom_df):,}")

    # Join with geometry
    print(f"\n3. Joining with geometry data...")
    merged_df = country_df.merge(
        geom_df,
        left_on='id_field',
        right_on='id_field_a',
        how='left'
    )

    geom_matched = merged_df['geometry'].notna().sum()
    print(f"   Fields with geometry: {geom_matched}/{len(merged_df)} ({geom_matched/len(merged_df)*100:.1f}%)")

    # Extract and transform attributes
    print(f"\n4. Extracting static attributes...")
    output_records = []

    for idx, row in merged_df.iterrows():
        field_data = {}

        # ===== Identity =====
        field_data['field_id'] = str(row['id_field'])
        field_data['name'] = row['field_name']
        field_data['country'] = country

        # ===== Functional Unit (GOR-based) =====
        gor = row.get('f_gas_oil_ratio__fbl')
        if pd.notna(gor) and gor > GOR_THRESHOLD:
            field_data['functional_unit'] = 'gas'
        elif pd.notna(gor):
            field_data['functional_unit'] = 'oil'
        else:
            field_data['functional_unit'] = None

        # ===== Geometry =====
        field_data['geometry'] = row.get('geometry')

        # ===== Reservoir Properties =====
        # Depth (meters to feet)
        depth_m = row.get('f_reservoir_depth__mtr')
        field_data['depth'] = depth_m * M_TO_FT if pd.notna(depth_m) else None

        # Age (discovery year)
        field_data['age'] = int(row['field_year_discovery']) if pd.notna(row.get('field_year_discovery')) else None

        # API gravity (already in degrees)
        field_data['api'] = row.get('f_api__api')

        # Gas composition - CO2 (% to fraction)
        co2_prc = row.get('f_co2__prc')
        field_data['gas_comp_co2'] = co2_prc / 100 if pd.notna(co2_prc) else None

        # Gas composition - H2S (ppm to fraction)
        h2s_ppm = row.get('f_h2s__ppm')
        field_data['gas_comp_h2s'] = h2s_ppm / 1000000 if pd.notna(h2s_ppm) else None

        # ===== Field Characteristics =====
        # Offshore (1 = offshore, 0 = onshore)
        onshore_offshore = row.get('onshore_offshore_tags', '')
        if pd.notna(onshore_offshore) and 'Offshore' in str(onshore_offshore):
            field_data['offshore'] = 1
        elif pd.notna(onshore_offshore) and 'Onshore' in str(onshore_offshore):
            field_data['offshore'] = 0
        else:
            field_data['offshore'] = None

        # Flood gas type
        field_data['flood_gas_type'] = parse_flood_gas_type(row.get('field_drive_mechanism_tertiary'))

        # ===== Production Methods =====
        prod_methods = parse_production_methods(row)
        field_data.update(prod_methods)

        output_records.append(field_data)

    output_df = pd.DataFrame(output_records)

    # Print summary statistics
    print(f"\n5. Extraction Summary:")
    print(f"   Total fields: {len(output_df):,}")
    print(f"\n   Attribute coverage:")
    for col in ['geometry', 'depth', 'age', 'api', 'gas_comp_co2', 'gas_comp_h2s', 'offshore', 'flood_gas_type']:
        non_null = output_df[col].notna().sum()
        print(f"     {col:20s} {non_null:6,}/{len(output_df):6,} ({non_null/len(output_df)*100:5.1f}%)")

    print(f"\n   Production methods:")
    for col in ['water_flooding', 'gas_flooding', 'natural_gas_reinjection', 'downhole_pump', 'gas_lifting']:
        count = (output_df[col] == 1).sum()
        print(f"     {col:30s} {count:6,} fields")

    return output_df


def generate_config_json(country: str) -> Dict:
    """Generate config JSON for CD data upload."""
    return {
        "data_metadata": {
            "name": f"{country} CD Static Field Data",
            "description": f"Static field attributes from Commercial Dataset for {country} oil and gas fields",
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
                {"name": "gas_comp_co2", "type": "number", "units": "fraction"},
                {"name": "gas_comp_h2s", "type": "number", "units": "fraction"},
                {"name": "flood_gas_type", "type": "string", "units": None},
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
            {"source_attribute": "gas_comp_co2", "target_attribute": "gas_comp_co2"},
            {"source_attribute": "gas_comp_h2s", "target_attribute": "gas_comp_h2s"},
            {"source_attribute": "flood_gas_type", "target_attribute": "flood_gas_type"},
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


def main():
    parser = argparse.ArgumentParser(description='Extract CD static field data for a country')
    parser.add_argument('--country', type=str, required=True, help='Country name (e.g., Argentina)')
    args = parser.parse_args()

    country = args.country

    # Extract data
    output_df = extract_cd_fields(country)

    if len(output_df) == 0:
        print(f"\nNo data extracted for {country}. Exiting.")
        sys.exit(1)

    # Prepare output directory
    country_output_dir = OUTPUT_DIR / country.lower()
    country_output_dir.mkdir(parents=True, exist_ok=True)

    # Save CSV
    csv_path = country_output_dir / f"{country.lower()}_pyxis_static_fields_cd.csv"
    output_df.to_csv(csv_path, index=False)
    print(f"\n6. Saved CSV: {csv_path}")

    # Save config
    config = generate_config_json(country)
    config_path = country_output_dir / f"{country.lower()}_pyxis_static_fields_config_cd.json"
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    print(f"   Saved config: {config_path}")

    print(f"\nFinished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
