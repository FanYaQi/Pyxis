"""
Additional Transformation Steps: Well Counts and Geometry

This script adds the missing transformation steps:
- Well counts from monthly well production data
- Geometry from well characteristics

These functions will be integrated into the main pipeline.
"""

import pandas as pd
import numpy as np
from pathlib import Path


# ============================================================================
# STEP 10a: AGGREGATE WELL COUNTS FROM MONTHLY WELL DATA
# ============================================================================

def load_and_aggregate_well_counts(
    well_production_csv: Path,
    year: int = 2025
) -> pd.DataFrame:
    """
    Aggregate monthly well production to get field-level well counts.

    INPUT: produccin-de-pozos-de-gas-y-petrleo-2025.csv
        Well-level monthly data with:
        - idpozo (well_id)
        - idareayacimiento (field_id)
        - anio, mes (year, month)
        - prod_pet, prod_gas (production volumes)
        - iny_agua, iny_gas (injection volumes)
        - tipoestado (well status)
        - tipoextraccion (extraction method)

    OUTPUT: DataFrame with field-month well counts
        - field_id, year, month
        - num_prod_wells: count of producing wells
        - num_water_inj_wells: count of water injection wells
        - num_gas_inj_wells: count of gas injection wells
        - extraction_method_dominant: most common extraction method

    TRANSFORMATION: Many-to-one aggregation
        Multiple wells per field-month → counts and mode
    """
    print(f"\n{'='*70}")
    print(f"STEP 10a: Aggregating Well Counts from Monthly Well Data")
    print(f"{'='*70}")

    if not well_production_csv.exists():
        print(f"⚠️  Well production file not found: {well_production_csv}")
        print("   Skipping well count aggregation")
        return None

    print(f"Reading: {well_production_csv}")
    df = pd.read_csv(well_production_csv, encoding='utf-8')
    print(f"  Loaded: {len(df):,} rows")

    # Filter to target year
    df = df[df['anio'] == year].copy()
    print(f"  Filtered to {year}: {len(df):,} rows")

    # Translate column names
    df.rename(columns={
        'idpozo': 'well_id',
        'idareayacimiento': 'field_id',
        'anio': 'year',
        'mes': 'month',
        'prod_pet': 'oil_prod_m3',
        'prod_gas': 'gas_prod_km3',
        'iny_agua': 'water_injected_m3',
        'iny_gas': 'gas_injected_km3',
        'tipoestado': 'well_status',
        'tipoextraccion': 'extraction_method',
    }, inplace=True)

    print("\nAggregating by (field_id, year, month)...")

    # Count producing wells (status contains "Extracción")
    producing_wells = df[df['well_status'].str.contains('Extracción', na=False)]

    # Aggregate
    well_counts = df.groupby(['field_id', 'year', 'month']).agg({
        'well_id': 'count',  # Total wells reporting
        'extraction_method': lambda x: x.mode()[0] if len(x.mode()) > 0 else 'Unknown',
    }).reset_index()

    well_counts.rename(columns={
        'well_id': 'num_wells_total',
        'extraction_method': 'extraction_method_dominant'
    }, inplace=True)

    # Count producing wells
    prod_counts = producing_wells.groupby(['field_id', 'year', 'month']).size().reset_index(name='num_prod_wells')
    well_counts = well_counts.merge(prod_counts, on=['field_id', 'year', 'month'], how='left')
    well_counts['num_prod_wells'] = well_counts['num_prod_wells'].fillna(0).astype(int)

    # Count water injection wells
    water_inj = df[df['water_injected_m3'] > 0].groupby(['field_id', 'year', 'month']).size().reset_index(name='num_water_inj_wells')
    well_counts = well_counts.merge(water_inj, on=['field_id', 'year', 'month'], how='left')
    well_counts['num_water_inj_wells'] = well_counts['num_water_inj_wells'].fillna(0).astype(int)

    # Count gas injection wells
    gas_inj = df[df['gas_injected_km3'] > 0].groupby(['field_id', 'year', 'month']).size().reset_index(name='num_gas_inj_wells')
    well_counts = well_counts.merge(gas_inj, on=['field_id', 'year', 'month'], how='left')
    well_counts['num_gas_inj_wells'] = well_counts['num_gas_inj_wells'].fillna(0).astype(int)

    print(f"\n✅ Well counts aggregated")
    print(f"   Fields with well data: {well_counts['field_id'].nunique():,}")
    print(f"   Total field-month records: {len(well_counts):,}")
    print(f"\nWell Count Statistics:")
    print(f"   Avg producing wells per field-month: {well_counts['num_prod_wells'].mean():.1f}")
    print(f"   Avg water inj wells per field-month: {well_counts['num_water_inj_wells'].mean():.1f}")
    print(f"   Avg gas inj wells per field-month: {well_counts['num_gas_inj_wells'].mean():.1f}")

    return well_counts


def parse_extraction_methods(df: pd.DataFrame) -> pd.DataFrame:
    """
    Parse extraction method strings into binary OPGEE flags.

    ONE-TO-MANY TRANSFORMATION:
        extraction_method_dominant (string) → binary flags

    BINARY FLAGS:
        downhole_pump: 1 if method contains "Bombeo"
        gas_lifting: 1 if method contains "Gas Lift"

    PATTERNS:
        - "Bombeo Mecánico" → downhole_pump = 1
        - "Bombeo Electrosumergible" → downhole_pump = 1
        - "Bombeo por Cavidades Progresivas" → downhole_pump = 1
        - "Gas Lift" / "Extracción con gas" → gas_lifting = 1
        - "Surgencia Natural" → neither flag
    """
    print("\nParsing extraction methods to binary flags...")

    if 'extraction_method_dominant' not in df.columns:
        print("  ⚠️ No extraction method column, skipping")
        df['downhole_pump'] = 0
        df['gas_lifting'] = 0
        return df

    # Downhole pump
    df['downhole_pump'] = df['extraction_method_dominant'].str.contains(
        'Bombeo|Electrosumergible|Cavidades',
        case=False,
        na=False
    ).astype(int)

    # Gas lifting
    df['gas_lifting'] = df['extraction_method_dominant'].str.contains(
        'Gas Lift|Extracción con gas',
        case=False,
        na=False
    ).astype(int)

    pump_count = df['downhole_pump'].sum()
    lift_count = df['gas_lifting'].sum()

    print(f"  Fields using downhole pump: {pump_count:,}")
    print(f"  Fields using gas lifting: {lift_count:,}")

    return df


# ============================================================================
# STEP 10b: ADD GEOMETRY FROM WELL CHARACTERISTICS
# ============================================================================

def load_and_aggregate_well_characteristics(
    well_chars_csv: Path
) -> pd.DataFrame:
    """
    Load well characteristics and aggregate to field level.

    INPUT: capitulo-iv-pozos.csv
        Well-level static data with:
        - sigla (well_name)
        - cod_yacimiento or idpozo (well identifiers)
        - yacimiento (field_name)
        - profundidad (depth)
        - cuenca (basin)
        - provincia (province)
        - geojson (well location)

    OUTPUT: DataFrame with field-level aggregated data
        - field_id
        - depth_avg: average well depth
        - basin: basin name (most common)
        - province: province name (most common)
        - geometry: aggregated geometry (if available)

    TRANSFORMATION: Many-to-one aggregation
        Multiple wells per field → average depth, mode for categories
    """
    print(f"\n{'='*70}")
    print(f"STEP 10b: Aggregating Well Characteristics to Field Level")
    print(f"{'='*70}")

    if not well_chars_csv.exists():
        print(f"⚠️  Well characteristics file not found: {well_chars_csv}")
        print("   Skipping geometry enrichment")
        return None

    print(f"Reading: {well_chars_csv}")
    df = pd.read_csv(well_chars_csv, encoding='utf-8')
    print(f"  Loaded: {len(df):,} rows")

    # Check for field identifier column
    if 'cod_yacimiento' in df.columns:
        field_col = 'cod_yacimiento'
    elif 'idareayacimiento' in df.columns:
        field_col = 'idareayacimiento'
    else:
        print("  ⚠️ No field identifier column found")
        return None

    # Rename columns
    df.rename(columns={
        field_col: 'field_id',
        'yacimiento': 'field_name',
        'profundidad': 'depth_m',
        'cuenca': 'basin',
        'provincia': 'province',
        'geojson': 'geometry',
    }, inplace=True)

    # Aggregate by field
    print("\nAggregating by field_id...")

    aggregations = {
        'depth_m': 'mean',  # Average depth
    }

    # Add basin and province if available
    if 'basin' in df.columns:
        aggregations['basin'] = lambda x: x.mode()[0] if len(x.mode()) > 0 else None
    if 'province' in df.columns:
        aggregations['province'] = lambda x: x.mode()[0] if len(x.mode()) > 0 else None

    field_agg = df.groupby('field_id').agg(aggregations).reset_index()

    field_agg.rename(columns={'depth_m': 'depth_avg'}, inplace=True)

    print(f"\n✅ Well characteristics aggregated")
    print(f"   Fields: {len(field_agg):,}")
    if 'depth_avg' in field_agg.columns:
        print(f"   Avg depth range: {field_agg['depth_avg'].min():.0f} to {field_agg['depth_avg'].max():.0f} m")

    return field_agg


def merge_well_counts(
    field_df: pd.DataFrame,
    well_counts: pd.DataFrame
) -> pd.DataFrame:
    """
    Merge well counts with field production data.

    MERGE TYPE: Left join
    MERGE KEYS: ['field_id', 'year', 'month']

    Adds:
        - num_prod_wells
        - num_water_inj_wells
        - num_gas_inj_wells
        - extraction_method_dominant
        - downhole_pump
        - gas_lifting
    """
    print(f"\n{'='*70}")
    print(f"Merging Well Counts with Field Production")
    print(f"{'='*70}")

    if well_counts is None or len(well_counts) == 0:
        print("⚠️  No well count data to merge")
        # Add empty columns
        field_df['num_prod_wells'] = 0
        field_df['num_water_inj_wells'] = 0
        field_df['num_gas_inj_wells'] = 0
        field_df['downhole_pump'] = 0
        field_df['gas_lifting'] = 0
        return field_df

    print(f"Field data: {len(field_df):,} rows")
    print(f"Well counts: {len(well_counts):,} rows")

    # Parse extraction methods before merge
    well_counts = parse_extraction_methods(well_counts)

    # Merge
    merged = field_df.merge(
        well_counts[['field_id', 'year', 'month', 'num_prod_wells',
                     'num_water_inj_wells', 'num_gas_inj_wells',
                     'downhole_pump', 'gas_lifting']],
        on=['field_id', 'year', 'month'],
        how='left'
    )

    # Fill NaN with 0
    for col in ['num_prod_wells', 'num_water_inj_wells', 'num_gas_inj_wells',
                'downhole_pump', 'gas_lifting']:
        merged[col] = merged[col].fillna(0).astype(int)

    print(f"\n✅ Well counts merged")
    print(f"   Result: {len(merged):,} rows")
    print(f"   Fields with well count data: {(merged['num_prod_wells'] > 0).sum():,}")

    return merged


def merge_well_characteristics(
    field_df: pd.DataFrame,
    well_chars: pd.DataFrame
) -> pd.DataFrame:
    """
    Merge well characteristics with field production data.

    MERGE TYPE: Left join
    MERGE KEYS: ['field_id']

    Adds:
        - depth_avg (if not already present)
        - basin (if not already present)
        - province (if not already present)
    """
    print(f"\n{'='*70}")
    print(f"Merging Well Characteristics with Field Production")
    print(f"{'='*70}")

    if well_chars is None or len(well_chars) == 0:
        print("⚠️  No well characteristics data to merge")
        return field_df

    print(f"Field data: {len(field_df):,} rows")
    print(f"Well chars: {len(well_chars):,} fields")

    # Only merge columns that don't already exist
    cols_to_merge = ['field_id']
    if 'depth_avg' in well_chars.columns and 'depth' not in field_df.columns:
        cols_to_merge.append('depth_avg')
        merge_depth = True
    else:
        merge_depth = False

    # Merge
    if len(cols_to_merge) > 1:
        merged = field_df.merge(
            well_chars[cols_to_merge],
            on='field_id',
            how='left'
        )

        if merge_depth:
            merged.rename(columns={'depth_avg': 'depth'}, inplace=True)
    else:
        merged = field_df

    print(f"\n✅ Well characteristics merged")

    return merged


if __name__ == "__main__":
    print("This module contains additional transformation functions.")
    print("Import and use in the main pipeline script.")
