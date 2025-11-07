"""
Argentina Data Transformation Pipeline - Using Translated Data

This script transforms TRANSLATED Argentina oil & gas production data into
Pyxis-compatible format. It reads from raw/translated/ directory which contains
English column names and meaningful O&G terminology.

INPUT FILES (from raw/translated/):
    - oil_field_production_english.csv (field-month-concept)
    - gas_field_production_english.csv (field-month-concept)
    - well_production_{year}_english.csv (well-month)
    - well_characteristics_english.csv (well static)

OUTPUT FILES:
    - field_production_complete.csv (English, WIDE format)

TRANSFORMATION SUMMARY:
    - Pivot LONG → WIDE format (concept → columns)
    - Merge oil + gas production (OUTER join)
    - Calculate API gravity from density (time-varying!)
    - Classify functional unit (oil/gas) using GOR threshold
    - Calculate production ratios (GOR, WOR, WIR, GLIR)
    - Derive EOR methods (water flooding, gas reinjection, etc.)
    - Aggregate well characteristics to field level
    - All data in ENGLISH with meaningful O&G terminology

TIME SCOPE: 2025 only (12 months)
GOR THRESHOLD: 10,000 scf/bbl = 1,781 m³/m³

Author: Pyxis Data Preparation Pipeline
Date: 2025-10-31
"""

import sys
from pathlib import Path

# Add utils to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
import numpy as np
import json
from datetime import datetime
from calendar import monthrange
import importlib.util

# Import well count and geometry functions
spec = importlib.util.spec_from_file_location(
    "well_functions",
    Path(__file__).parent / "00a_add_well_counts_and_geometry.py"
)
well_functions = importlib.util.module_from_spec(spec)
spec.loader.exec_module(well_functions)

load_and_aggregate_well_counts_translated = well_functions.load_and_aggregate_well_counts
load_and_aggregate_well_characteristics_translated = well_functions.load_and_aggregate_well_characteristics
merge_well_counts = well_functions.merge_well_counts
merge_well_characteristics = well_functions.merge_well_characteristics


# ============================================================================
# CONFIGURATION
# ============================================================================

def load_config(config_path: Path) -> dict:
    """Load configuration parameters from JSON file."""
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


# ============================================================================
# STEP 1: LOAD AND PIVOT OIL PRODUCTION DATA (TRANSLATED)
# ============================================================================

def load_and_pivot_oil_production_translated(
    input_csv: Path,
    year: int = 2025
) -> pd.DataFrame:
    """
    Load TRANSLATED oil field production data and pivot from LONG to WIDE format.

    INPUT: Translated CSV with English column names and concept values
    """
    print(f"\n{'='*70}")
    print(f"STEP 1: Loading TRANSLATED Oil Production Data")
    print(f"{'='*70}")

    print(f"Reading: {input_csv}")
    df = pd.read_csv(input_csv, encoding='utf-8')
    print(f"  Loaded: {len(df):,} rows, {len(df.columns)} columns")

    # Filter to target year
    df = df[df['year'] == year].copy()
    print(f"  Filtered to {year}: {len(df):,} rows")

    # Check unique concept values (already in English!)
    concept_values = df['concept'].unique()
    print(f"  Unique concept values: {len(concept_values)}")
    for i, val in enumerate(sorted(concept_values)[:10], 1):
        print(f"    {i}. {val}")

    # Pivot: concept becomes columns
    print("\nPivoting LONG → WIDE format...")
    oil_wide = df.pivot_table(
        index=['field_id', 'field_name', 'year', 'month',
               'basin', 'province', 'location', 'company_name'],
        columns='concept',
        values='quantity',
        aggfunc='first'
    ).reset_index()

    print(f"  After pivot: {len(oil_wide):,} rows, {len(oil_wide.columns)} columns")

    # Rename concept columns to standard format (match original pipeline expectations)
    concept_mapping = {
        'primary_production_m3': 'primary_prod_m3',
        'secondary_production_m3': 'secondary_prod_m3',
        'tertiary_eor_production_m3': 'assisted_recovery_m3',
        'unconventional_production_m3': 'unconventional_prod_m3',
        'water_production_m3': 'water_prod_m3',
        'water_injection_m3': 'water_injected_m3',
        'condensate_production_m3': 'condensate_prod_m3',
        'stabilized_gasoline_production_m3': 'stabilized_gasoline_m3',
        'field_fuel_consumption_m3': 'field_consumption_m3',
        'oil_density_avg_ton_per_m3': 'density_ton_m3',
    }

    oil_wide.rename(columns=concept_mapping, inplace=True)

    # Rename field_name to name for consistency
    oil_wide.rename(columns={'field_name': 'name'}, inplace=True)

    print(f"\n✅ Oil production data loaded and pivoted")
    print(f"   Fields: {oil_wide['field_id'].nunique()}")
    print(f"   Rows: {len(oil_wide):,} (field-month records)")

    return oil_wide


# ============================================================================
# STEP 2: LOAD AND PIVOT GAS PRODUCTION DATA (TRANSLATED)
# ============================================================================

def load_and_pivot_gas_production_translated(
    input_csv: Path,
    year: int = 2025
) -> pd.DataFrame:
    """
    Load TRANSLATED gas field production data and pivot from LONG to WIDE format.

    INPUT: Translated CSV with English column names and concept values
    """
    print(f"\n{'='*70}")
    print(f"STEP 2: Loading TRANSLATED Gas Production Data")
    print(f"{'='*70}")

    print(f"Reading: {input_csv}")
    df = pd.read_csv(input_csv, encoding='utf-8')
    print(f"  Loaded: {len(df):,} rows, {len(df.columns)} columns")

    # Filter to target year
    df = df[df['year'] == year].copy()
    print(f"  Filtered to {year}: {len(df):,} rows")

    # Check unique concept values
    concept_values = df['concept'].unique()
    print(f"  Unique concept values: {len(concept_values)}")
    for i, val in enumerate(sorted(concept_values)[:10], 1):
        print(f"    {i}. {val}")

    # Pivot: concept becomes columns
    print("\nPivoting LONG → WIDE format...")
    gas_wide = df.pivot_table(
        index=['field_id', 'field_name', 'year', 'month',
               'basin', 'province', 'location', 'company_name'],
        columns='concept',
        values='quantity',
        aggfunc='first'
    ).reset_index()

    print(f"  After pivot: {len(gas_wide):,} rows, {len(gas_wide.columns)} columns")

    # Rename concept columns (match original pipeline expectations)
    concept_mapping = {
        'high_pressure_gas_mm3': 'gas_high_pressure_mm3',
        'medium_pressure_gas_mm3': 'gas_medium_pressure_mm3',
        'low_pressure_gas_mm3': 'gas_low_pressure_mm3',
        'unconventional_gas_mm3': 'gas_unconventional_mm3',
        'gas_reinjection_formation_mm3': 'gas_injected_formation_mm3',
        'gas_injection_storage_mm3': 'gas_injected_storage_mm3',
        'gas_extraction_storage_mm3': 'gas_extracted_storage_mm3',
        'gas_heating_value_kcal_per_m3': 'gas_heating_value_kcal_m3',
    }

    gas_wide.rename(columns=concept_mapping, inplace=True)

    # Rename field_name to name
    gas_wide.rename(columns={'field_name': 'name'}, inplace=True)

    print(f"\n✅ Gas production data loaded and pivoted")
    print(f"   Fields: {gas_wide['field_id'].nunique()}")
    print(f"   Rows: {len(gas_wide):,} (field-month records)")

    return gas_wide


# ============================================================================
# REMAINING STEPS: Import functions from original pipeline
# ============================================================================

# Import original pipeline functions via importlib
spec_pipeline = importlib.util.spec_from_file_location(
    "original_pipeline",
    Path(__file__).parent / "00_clean_and_merge_sources.py"
)
original_pipeline = importlib.util.module_from_spec(spec_pipeline)
spec_pipeline.loader.exec_module(original_pipeline)

# Reuse these functions (they work with English column names):
calculate_total_oil_production = original_pipeline.calculate_total_oil_production
calculate_total_gas_production = original_pipeline.calculate_total_gas_production
merge_oil_and_gas_production = original_pipeline.merge_oil_and_gas_production
calculate_api_gravity = original_pipeline.calculate_api_gravity
convert_units = original_pipeline.convert_units
determine_functional_unit = original_pipeline.determine_functional_unit
calculate_production_ratios = original_pipeline.calculate_production_ratios
detect_eor_methods = original_pipeline.detect_eor_methods
determine_offshore = original_pipeline.determine_offshore
generate_temporal_fields = original_pipeline.generate_temporal_fields
add_static_fields = original_pipeline.add_static_fields
select_final_columns = original_pipeline.select_final_columns


# ============================================================================
# MAIN PIPELINE
# ============================================================================

def main():
    """Execute complete transformation pipeline using TRANSLATED data."""

    print("\n" + "="*70)
    print("ARGENTINA DATA TRANSFORMATION PIPELINE")
    print("Using TRANSLATED Data with O&G Terminology")
    print("="*70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Paths
    base_dir = Path(__file__).parent.parent
    translated_dir = base_dir / "raw" / "translated"
    output_dir = base_dir / "output"
    config_dir = base_dir / "config"

    # Load configuration
    print("\nLoading configuration...")
    config = load_config(config_dir / "opgee_calculation_params.json")
    year = config['time_scope']['start_year']
    print(f"  Processing year: {year}")

    # Input files (TRANSLATED)
    oil_file = translated_dir / "oil_field_production_english.csv"
    gas_file = translated_dir / "gas_field_production_english.csv"
    well_prod_file = translated_dir / f"well_production_{year}_english.csv"
    well_chars_file = translated_dir / "well_characteristics_english.csv"

    # Check files exist
    if not oil_file.exists():
        print(f"\n❌ ERROR: Translated oil production file not found: {oil_file}")
        print("   Run 01_translate_all_raw_data.py first!")
        return
    if not gas_file.exists():
        print(f"\n❌ ERROR: Translated gas production file not found: {gas_file}")
        print("   Run 01_translate_all_raw_data.py first!")
        return

    # Optional files
    has_well_prod = well_prod_file.exists()
    has_well_chars = well_chars_file.exists()

    if not has_well_prod:
        print(f"\n⚠️  WARNING: Well production file not found: {well_prod_file}")
    if not has_well_chars:
        print(f"\n⚠️  WARNING: Well characteristics file not found: {well_chars_file}")

    # Execute pipeline
    try:
        # Step 1: Load and pivot oil production
        oil_df = load_and_pivot_oil_production_translated(oil_file, year)
        oil_df = calculate_total_oil_production(oil_df)

        # Step 2: Load and pivot gas production
        gas_df = load_and_pivot_gas_production_translated(gas_file, year)
        gas_df = calculate_total_gas_production(gas_df)

        # Step 4: Merge oil and gas
        combined = merge_oil_and_gas_production(oil_df, gas_df)

        # Step 5: Calculate API gravity
        combined = calculate_api_gravity(combined)

        # Step 6: Unit conversions
        combined = convert_units(combined, config)

        # Step 7: Determine functional unit
        combined = determine_functional_unit(combined, config)

        # Step 8: Calculate ratios
        combined = calculate_production_ratios(combined)

        # Step 9: Detect EOR methods
        combined = detect_eor_methods(combined, config)

        # Step 10: Determine offshore
        combined = determine_offshore(combined)

        # Step 10a: Load and merge well counts (if available)
        # TODO: Update well processing functions to handle translated column names
        # if has_well_prod:
        #     well_counts = load_and_aggregate_well_counts_translated(well_prod_file, year)
        #     combined = merge_well_counts(combined, well_counts)

        # # Step 10b: Load and merge well characteristics (if available)
        # if has_well_chars:
        #     well_chars = load_and_aggregate_well_characteristics_translated(well_chars_file)
        #     combined = merge_well_characteristics(combined, well_chars)

        # Note: Skipping well count aggregation - the comprehensive pipeline (Step 4)
        # will integrate well data from field-level aggregations

        # Step 11: Generate temporal fields
        combined = generate_temporal_fields(combined)

        # Step 12: Add static fields
        combined = add_static_fields(combined)

        # Step 13: Select final columns
        final_df = select_final_columns(combined)

        # Save output
        output_file = output_dir / "field_production_complete.csv"
        output_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n{'='*70}")
        print(f"SAVING OUTPUT")
        print(f"{'='*70}")

        final_df.to_csv(output_file, index=False, encoding='utf-8')
        print(f"✅ Saved: {output_file}")
        print(f"   Rows: {len(final_df):,}")
        print(f"   Columns: {len(final_df.columns)}")
        print(f"   Size: {output_file.stat().st_size / 1024 / 1024:.2f} MB")

        # Summary statistics
        print(f"\n{'='*70}")
        print(f"SUMMARY STATISTICS")
        print(f"{'='*70}")
        print(f"Fields: {final_df['field_id'].nunique():,}")
        print(f"Months: {final_df['month'].nunique()}")
        print(f"Date range: {final_df['start_date'].min()} to {final_df['end_date'].max()}")
        print(f"Oil fields: {(final_df['functional_unit'] == 'oil').sum():,}")
        print(f"Gas fields: {(final_df['functional_unit'] == 'gas').sum():,}")

        print(f"\n{'='*70}")
        print(f"✅ PIPELINE COMPLETE")
        print(f"{'='*70}")
        print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    except Exception as e:
        print(f"\n❌ ERROR: Pipeline failed")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return


if __name__ == "__main__":
    main()
