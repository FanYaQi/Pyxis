"""
Extract static field data from GOGI (Global Oil & Gas Infrastructure) for a specific country.

Usage:
    python extract_gogi_fields.py --country Argentina
"""

import sys
import json
import struct
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

# Data paths
SCRIPTS_DIR = Path(__file__).parent
OUTPUT_DIR = SCRIPTS_DIR.parent / 'output'
DATA_DIR = Path(__file__).parent.parent.parent.parent / 'scripts_n_notebooks' / 'data'
SHAPEFILE_PATH = DATA_DIR / 'GOGI_field' / 'Fields.shp'
DBF_PATH = DATA_DIR / 'GOGI_field' / 'Fields.dbf'


def read_dbf_records(dbf_path: Path, country_filter: str = None) -> List[Dict]:
    """
    Read DBF file and return records.

    Args:
        dbf_path: Path to DBF file
        country_filter: Optional country name to filter (e.g., "Argentina")

    Returns:
        List of record dictionaries
    """
    with open(dbf_path, 'rb') as f:
        # Read header
        f.seek(4)
        num_records = struct.unpack('<I', f.read(4))[0]
        header_len = struct.unpack('<H', f.read(2))[0]
        record_len = struct.unpack('<H', f.read(2))[0]

        # Read field descriptors
        f.seek(32)
        fields = []
        while True:
            field_info = f.read(32)
            if field_info[0] == 0x0D:  # End of field descriptors
                break
            name = field_info[0:11].decode('utf-8', errors='ignore').strip('\x00')
            field_type = chr(field_info[11])
            field_len = field_info[16]
            fields.append((name, field_type, field_len))

        # Read records
        f.seek(header_len)
        records = []

        for i in range(num_records):
            record = f.read(record_len)
            if record[0] == 0x2A:  # Deleted record
                continue

            # Parse fields
            parsed = {}
            pos = 1  # Skip deletion flag
            for fname, ftype, flen in fields:
                value = record[pos:pos+flen].decode('utf-8', errors='ignore').strip()

                # Convert numeric fields
                if ftype == 'F' and value:
                    try:
                        parsed[fname] = float(value)
                    except ValueError:
                        parsed[fname] = None
                else:
                    parsed[fname] = value if value else None

                pos += flen

            # Filter by country if specified
            if country_filter:
                country_field = parsed.get('MD_Country', '')
                if country_field and country_filter.lower() in country_field.lower():
                    records.append(parsed)
            else:
                records.append(parsed)

    return records


def read_shp_geometries(shp_path: Path) -> List[Dict]:
    """
    Read shapefile geometries using simple binary parsing.

    Returns:
        List of geometry dictionaries with index
    """
    # We'll use ogr or geopandas if available, otherwise skip geometry
    try:
        import geopandas as gpd
        from shapely.geometry import mapping
        gdf = gpd.read_file(shp_path)
        geometries = []
        for idx, row in gdf.iterrows():
            if row.geometry is not None:
                geometries.append({
                    'index': idx,
                    'geometry': json.dumps(mapping(row.geometry))
                })
        return geometries
    except ImportError:
        print("   WARNING: geopandas/shapely not available, skipping geometry extraction")
        return []


def parse_functional_unit(commodity: str) -> Optional[str]:
    """Parse functional unit from GOGI commodity field."""
    if not commodity:
        return None

    commodity_lower = commodity.lower()

    if 'oil' in commodity_lower:
        return 'oil'
    elif 'gas' in commodity_lower:
        return 'gas'

    return None


def parse_offshore(onshore_offshore: str) -> Optional[int]:
    """Parse offshore indicator from GOGI field."""
    if not onshore_offshore:
        return None

    onshore_offshore_lower = onshore_offshore.lower()

    if 'offshore' in onshore_offshore_lower:
        return 1
    elif 'onshore' in onshore_offshore_lower:
        return 0

    return None


def parse_age(installation: str) -> Optional[int]:
    """
    Parse discovery/installation year from GOGI installation field.
    Format is typically like "1965-01-01T00:00:00Z"
    """
    if not installation:
        return None

    try:
        # Try to extract year from ISO date format
        if 'T' in installation:
            year_str = installation.split('-')[0]
            year = int(year_str)
            if 1800 <= year <= 2030:  # Sanity check
                return year
    except (ValueError, IndexError):
        pass

    return None


def extract_gogi_fields(country: str) -> pd.DataFrame:
    """
    Extract static field data from GOGI for specified country.

    Args:
        country: Country name (e.g., "Argentina")

    Returns:
        DataFrame with extracted field data
    """
    print(f"=== Extracting GOGI Fields for {country} ===")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Read DBF records
    print(f"\n1. Reading DBF data from {DBF_PATH.name}...")
    records = read_dbf_records(DBF_PATH, country_filter=country)
    print(f"   {country} records: {len(records):,}")

    if len(records) == 0:
        print(f"   WARNING: No records found for {country}")
        return pd.DataFrame()

    # Read shapefile geometries
    print(f"\n2. Reading shapefile geometries from {SHAPEFILE_PATH.name}...")
    geometries = read_shp_geometries(SHAPEFILE_PATH)
    print(f"   Total geometries: {len(geometries):,}")

    # Convert to DataFrame
    df = pd.DataFrame(records)

    # Extract and transform attributes
    print(f"\n3. Extracting static attributes...")
    output_records = []

    for idx, row in df.iterrows():
        field_data = {}

        # ===== Identity =====
        field_data['field_id'] = str(row.get('MD_Fkey', f'GOGI_{idx}'))
        field_data['name'] = row.get('Facility_N')
        field_data['country'] = country

        # ===== Functional Unit =====
        field_data['functional_unit'] = parse_functional_unit(row.get('Commodity'))

        # ===== Geometry =====
        # Match by index (assuming DBF and SHP are in same order)
        if idx < len(geometries):
            field_data['geometry'] = geometries[idx].get('geometry')
        else:
            field_data['geometry'] = None

        # ===== Field Characteristics =====
        # Offshore
        field_data['offshore'] = parse_offshore(row.get('Onshore_Of'))

        # Age (installation year)
        field_data['age'] = parse_age(row.get('Installati'))

        output_records.append(field_data)

    output_df = pd.DataFrame(output_records)

    # Print summary statistics
    print(f"\n4. Extraction Summary:")
    print(f"   Total fields: {len(output_df):,}")
    print(f"\n   Attribute coverage:")
    for col in ['geometry', 'functional_unit', 'offshore', 'age']:
        non_null = output_df[col].notna().sum()
        print(f"     {col:20s} {non_null:6,}/{len(output_df):6,} ({non_null/len(output_df)*100:5.1f}%)")

    return output_df


def generate_config_json(country: str) -> Dict:
    """Generate config JSON for GOGI data upload."""
    return {
        "data_metadata": {
            "name": f"{country} GOGI Static Field Data",
            "description": f"Static field attributes from GOGI for {country} oil and gas fields",
            "type": "csv",
            "version": "1.0.0",
            "attributes": [
                {"name": "field_id", "type": "string", "units": None},
                {"name": "name", "type": "string", "units": None},
                {"name": "country", "type": "string", "units": None},
                {"name": "functional_unit", "type": "string", "units": None},
                {"name": "geometry", "type": "geometry", "units": None},
                {"name": "offshore", "type": "boolean", "units": None},
                {"name": "age", "type": "integer", "units": "year"}
            ]
        },
        "mappings": [
            {"source_attribute": "name", "target_attribute": "name"},
            {"source_attribute": "country", "target_attribute": "country"},
            {"source_attribute": "functional_unit", "target_attribute": "functional_unit"},
            {"source_attribute": "geometry", "target_attribute": "geometry"},
            {"source_attribute": "offshore", "target_attribute": "offshore"},
            {"source_attribute": "age", "target_attribute": "age"}
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
    parser = argparse.ArgumentParser(description='Extract GOGI static field data for a country')
    parser.add_argument('--country', type=str, required=True, help='Country name (e.g., Argentina)')
    args = parser.parse_args()

    country = args.country

    # Extract data
    output_df = extract_gogi_fields(country)

    if len(output_df) == 0:
        print(f"\nNo data extracted for {country}. Exiting.")
        sys.exit(1)

    # Prepare output directory
    country_output_dir = OUTPUT_DIR / country.lower()
    country_output_dir.mkdir(parents=True, exist_ok=True)

    # Save CSV
    csv_path = country_output_dir / f"{country.lower()}_pyxis_static_fields_gogi.csv"
    output_df.to_csv(csv_path, index=False)
    print(f"\n5. Saved CSV: {csv_path}")

    # Save config
    config = generate_config_json(country)
    config_path = country_output_dir / f"{country.lower()}_pyxis_static_fields_config_gogi.json"
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    print(f"   Saved config: {config_path}")

    print(f"\nFinished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
