"""
Script 3: Generate Pyxis Ingestion Files

Takes merged field production data and generates files for Pyxis API ingestion:
- Final CSV with Pyxis-compatible column names and formats
- JSON configuration file for data mapping

Input:
    - argentina/output/field_production_with_geometry.csv
    - argentina/config/column_mappings.json

Output:
    - argentina/output/argentina_2025_pyxis_data.csv
    - argentina/output/argentina_2025_pyxis_config.json

Processing:
    - Map Argentina columns to OPGEE/Pyxis attributes
    - Convert units (m³ to bbl, km³ to Mcf)
    - Add temporal fields (start_date, end_date from year/month)
    - Add required Pyxis metadata (country, source)
    - Generate Pyxis configuration JSON
"""

import sys
from pathlib import Path

# Add utils to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
import json
from datetime import datetime
from calendar import monthrange
from utils.pyxis_mappings import convert_oil_m3_to_bbl, convert_gas_km3_to_m3


def generate_temporal_fields(df: pd.DataFrame) -> pd.DataFrame:
    """
    Generate start_date and end_date from year and month columns.

    Args:
        df: DataFrame with 'year' and 'month' columns

    Returns:
        DataFrame with added 'start_date' and 'end_date' columns
    """
    print("Generating temporal fields...")

    def get_date_range(row):
        year = int(row['year'])
        month = int(row['month'])
        start_date = f"{year}-{month:02d}-01"
        last_day = monthrange(year, month)[1]
        end_date = f"{year}-{month:02d}-{last_day}"
        return pd.Series({'start_date': start_date, 'end_date': end_date})

    date_fields = df.apply(get_date_range, axis=1)
    df = pd.concat([df, date_fields], axis=1)

    return df


def convert_units(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert Argentina units to OPGEE standard units.

    Argentina → OPGEE:
    - oil_prod_m3 → oil_prod (bbl)
    - gas_prod_km3 → gas_prod (m³)
    - water_prod_m3 → water_prod (m³) [no change]

    Args:
        df: DataFrame with Argentina unit columns

    Returns:
        DataFrame with converted unit columns
    """
    print("Converting units...")

    # Oil: m³ to barrels
    df['oil_prod'] = df['oil_prod_m3'].apply(convert_oil_m3_to_bbl)

    # Gas: km³ to m³
    df['gas_prod'] = df['gas_prod_km3'].apply(convert_gas_km3_to_m3)

    # Water: keep as m³
    df['water_prod'] = df['water_prod_m3']
    df['water_injected'] = df['water_injected_m3']

    # Gas injection: km³ to m³
    df['gas_injected'] = df['gas_injected_km3'].apply(convert_gas_km3_to_m3)

    return df


def generate_pyxis_data(
    input_csv: Path,
    column_mappings_json: Path,
    output_csv: Path,
) -> pd.DataFrame:
    """
    Generate Pyxis-compatible CSV with proper column names and units.

    Args:
        input_csv: Path to merged field production CSV
        column_mappings_json: Path to column mappings JSON
        output_csv: Path for output Pyxis CSV

    Returns:
        DataFrame with Pyxis-compatible data
    """
    print(f"Reading merged data from: {input_csv}")
    df = pd.read_csv(input_csv)

    print(f"Input data shape: {df.shape}")

    # Generate temporal fields
    df = generate_temporal_fields(df)

    # Convert units
    df = convert_units(df)

    # Add required Pyxis fields
    print("Adding Pyxis metadata fields...")
    df['country'] = 'Argentina'
    df['field_location'] = df['province']  # Use province as location

    # Load column mappings
    print(f"Loading column mappings from: {column_mappings_json}")
    with open(column_mappings_json, 'r', encoding='utf-8') as f:
        mappings = json.load(f)

    # Apply column mappings (rename columns)
    print("Applying column mappings...")
    df = df.rename(columns=mappings)

    # Select final columns for Pyxis (based on what's available)
    pyxis_columns = [
        # Identification
        'field_id', 'name', 'country', 'field_location',

        # Temporal
        'start_date', 'end_date',

        # Spatial
        'latitude', 'longitude', 'centroid_h3_index', 'geometry',

        # Production
        'functional_unit', 'oil_prod', 'gas_prod', 'water_prod',
        'num_prod_wells', 'gor', 'wor',

        # Injection
        'water_injected', 'gas_injected', 'co2_injected',

        # Technical
        'depth', 'basin', 'province', 'resource_type',

        # Company
        'operating_company', 'operating_company_id',
    ]

    # Keep only columns that exist
    available_columns = [col for col in pyxis_columns if col in df.columns]
    df_pyxis = df[available_columns]

    print(f"\nFinal Pyxis data shape: {df_pyxis.shape}")
    print(f"Columns: {len(available_columns)}")

    # Save output
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    df_pyxis.to_csv(output_csv, index=False, encoding='utf-8')
    print(f"\n✅ Pyxis data CSV saved to: {output_csv}")

    return df_pyxis


def generate_pyxis_config(
    data_df: pd.DataFrame,
    column_mappings_json: Path,
    output_json: Path,
) -> None:
    """
    Generate Pyxis configuration JSON for API upload.

    Args:
        data_df: DataFrame with Pyxis data
        column_mappings_json: Path to column mappings JSON
        output_json: Path for output config JSON
    """
    print("\nGenerating Pyxis configuration JSON...")

    # Load column mappings to generate attribute list
    with open(column_mappings_json, 'r', encoding='utf-8') as f:
        mappings = json.load(f)

    # Define attribute metadata
    attributes = []
    for col in data_df.columns:
        attr_type = "string"  # Default

        # Determine type based on column name
        if col in ['oil_prod', 'gas_prod', 'water_prod', 'gor', 'wor',
                   'latitude', 'longitude', 'depth', 'water_injected', 'gas_injected']:
            attr_type = "number"
        elif col in ['num_prod_wells', 'field_id', 'operating_company_id']:
            attr_type = "integer"
        elif col in ['start_date', 'end_date']:
            attr_type = "date"
        elif col == 'geometry':
            attr_type = "geometry"

        attributes.append({
            "name": col,
            "type": attr_type,
            "description": f"Argentina field data: {col}"
        })

    # Generate mappings for config
    config_mappings = []
    for source_col, target_col in mappings.items():
        if target_col in data_df.columns:
            config_mappings.append({
                "source_attribute": target_col,
                "target_attribute": target_col  # Already renamed
            })

    # Build configuration
    config = {
        "config_metadata": {
            "created_at": datetime.now().isoformat(),
            "author": "Pyxis Data Preparation Pipeline",
            "schema_id": "argentina_oil_gas_2025"
        },
        "data_metadata": {
            "name": "Argentina Oil & Gas Production 2025",
            "type": "csv",
            "version": "1.0",
            "attributes": attributes
        },
        "spatial_configuration": {
            "enabled": True,
            "geometry_field": "geometry",
            "source_crs": "EPSG:4326"
        },
        "temporal_configuration": {
            "enabled": True,
            "valid_from_field": "start_date",
            "valid_to_field": "end_date",
            "date_format": "%Y-%m-%d"
        },
        "file_specific": {
            "csv": {
                "delimiter": ",",
                "encoding": "utf-8",
                "header_row": 0
            }
        },
        "mappings": config_mappings
    }

    # Save configuration
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print(f"✅ Pyxis config JSON saved to: {output_json}")


if __name__ == "__main__":
    # Define paths
    base_dir = Path(__file__).parent.parent
    input_file = base_dir / "output" / "field_production_with_geometry.csv"
    mappings_file = base_dir / "config" / "column_mappings.json"
    output_data_csv = base_dir / "output" / "argentina_2025_pyxis_data.csv"
    output_config_json = base_dir / "output" / "argentina_2025_pyxis_config.json"

    if not input_file.exists():
        print(f"❌ Error: Input file not found: {input_file}")
        print("Please run 02_merge_with_geometry.py first")
        sys.exit(1)

    if not mappings_file.exists():
        print(f"❌ Error: Column mappings not found: {mappings_file}")
        print("Please create argentina/config/column_mappings.json")
        sys.exit(1)

    # Generate Pyxis data CSV
    pyxis_df = generate_pyxis_data(input_file, mappings_file, output_data_csv)

    # Generate Pyxis config JSON
    generate_pyxis_config(pyxis_df, mappings_file, output_config_json)

    print("\n" + "="*60)
    print("✅ Pyxis ingestion files generated successfully!")
    print("="*60)
    print(f"\nData CSV:   {output_data_csv}")
    print(f"Config JSON: {output_config_json}")
    print("\nNext steps:")
    print("1. Review the generated files")
    print("2. Upload to Pyxis via API:")
    print("   POST /api/v1/data-entries/")
    print("   - data_file: argentina_2025_pyxis_data.csv")
    print("   - config_file: argentina_2025_pyxis_config.json")
    print("   - granularity: field")
    print("   - source_id: <your_argentina_source_id>")
