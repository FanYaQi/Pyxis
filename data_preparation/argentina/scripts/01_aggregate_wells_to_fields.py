"""
Script 1: Aggregate Well Production Data to Field-Level

Takes monthly well production data and aggregates it to field-level monthly data.

Input:
    - argentina/raw/well_prod_2025_cleaned.csv

Output:
    - argentina/output/field_monthly_production.csv

Processing:
    - Group by field_id, field_name, year, month
    - Sum production volumes (oil, gas, water)
    - Sum injection volumes
    - Count number of producing wells
    - Average field-level attributes (depth, etc.)
    - Calculate ratios (GOR, WOR)
"""

import sys
from pathlib import Path

# Add utils to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
from utils.pyxis_mappings import determine_functional_unit


def aggregate_wells_to_fields(
    input_csv: Path,
    output_csv: Path,
) -> None:
    """
    Aggregate well-level production data to field-level monthly data.

    Args:
        input_csv: Path to cleaned well production CSV
        output_csv: Path for output field aggregated CSV
    """
    print(f"Reading well production data from: {input_csv}")
    df = pd.read_csv(input_csv)

    print(f"Input data shape: {df.shape}")
    print(f"Date range: {df['year'].min()}/{df['month'].min()} to {df['year'].max()}/{df['month'].max()}")
    print(f"Unique wells: {df['well_id'].nunique()}")
    print(f"Unique fields: {df['field_id'].nunique()}")

    # Grouping columns
    group_cols = [
        'field_id',
        'field_name',
        'year',
        'month',
        'basin',
        'province',
        'resource_type',
    ]

    # Production columns to sum
    sum_cols = [
        'oil_prod_m3',
        'gas_prod_km3',
        'water_prod_m3',
        'water_injected_m3',
        'gas_injected_km3',
        'co2_injected',
        'other_injected',
    ]

    # Columns to average
    avg_cols = [
        'depth_m',
    ]

    print("\nAggregating data...")

    # Build aggregation dictionary
    agg_dict = {}

    # Sum production/injection volumes
    for col in sum_cols:
        if col in df.columns:
            agg_dict[col] = 'sum'

    # Average field attributes
    for col in avg_cols:
        if col in df.columns:
            agg_dict[col] = 'mean'

    # Count wells
    agg_dict['well_id'] = 'count'  # Will rename to num_prod_wells

    # Perform aggregation
    field_agg = df.groupby(group_cols, as_index=False).agg(agg_dict)

    # Rename well count column
    field_agg.rename(columns={'well_id': 'num_prod_wells'}, inplace=True)

    # Calculate ratios
    print("Calculating GOR and WOR ratios...")

    # GOR: Gas-to-Oil Ratio (handle division by zero)
    field_agg['gor'] = field_agg.apply(
        lambda row: (row['gas_prod_km3'] * 1e9 / row['oil_prod_m3'])
        if row['oil_prod_m3'] > 0 else 0,
        axis=1
    )

    # WOR: Water-to-Oil Ratio
    field_agg['wor'] = field_agg.apply(
        lambda row: (row['water_prod_m3'] / row['oil_prod_m3'])
        if row['oil_prod_m3'] > 0 else 0,
        axis=1
    )

    # Determine functional unit (oil vs gas field)
    print("Determining functional units...")
    field_agg['functional_unit'] = field_agg.apply(
        lambda row: determine_functional_unit(row['oil_prod_m3'], row['gas_prod_km3']),
        axis=1
    )

    # Sort by field and date
    field_agg = field_agg.sort_values(['field_id', 'year', 'month'])

    print(f"\nOutput data shape: {field_agg.shape}")
    print(f"Aggregated to {field_agg['field_id'].nunique()} fields")

    # Save output
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    field_agg.to_csv(output_csv, index=False, encoding='utf-8')
    print(f"\n✅ Field aggregated data saved to: {output_csv}")


if __name__ == "__main__":
    # Define paths
    base_dir = Path(__file__).parent.parent
    input_file = base_dir / "raw" / "well_prod_2025_cleaned.csv"
    output_file = base_dir / "output" / "field_monthly_production.csv"

    if not input_file.exists():
        print(f"❌ Error: Input file not found: {input_file}")
        print("Please place your cleaned well production CSV in argentina/raw/")
        sys.exit(1)

    aggregate_wells_to_fields(input_file, output_file)
