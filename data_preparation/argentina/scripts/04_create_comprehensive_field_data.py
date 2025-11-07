"""
Argentina Data Pipeline - Step 4: Create Comprehensive Field Data

This script integrates ALL translated data sources to create comprehensive field-level output:
- Production data (oil, gas, water) from Steps 0-2
- Fracture/completion metrics (proppant, fluids, equipment)
- Field geometry and depth
- Flaring data for emissions calculations

INPUT FILES (from translated/):
    - fracture_completion_data_english.csv - Hydraulic fracturing metrics
    - field_shapes_depth_english.csv - Field boundaries and depth
    - plant_gas_processing_english.csv - Flaring and processing data

INPUT FILES (from output/):
    - field_production_complete.csv - From Step 2 (clean_and_merge_translated)

OUTPUT:
    - comprehensive_field_data.csv - Complete field metrics for Pyxis

ADDED METRICS:
    Fracture:
        - Proppant intensity (tons/m)
        - Water usage (m³ per well)
        - Equipment specs (pressure, horsepower)
        - Completion type

    Geometry:
        - Centroid coordinates (lat, lon)
        - Depth (avg, min, max)

    Emissions:
        - Gas flared (mm³)
        - Field fuel consumption
        - Flaring intensity

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


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def extract_centroid_from_geojson(geojson_str):
    """
    Extract centroid coordinates from GeoJSON string.

    Returns (longitude, latitude) tuple or (None, None) if invalid.
    """
    if pd.isna(geojson_str):
        return None, None

    try:
        geom_dict = json.loads(geojson_str)
        all_coords = []

        if geom_dict['type'] == 'MultiPolygon':
            for polygon in geom_dict['coordinates']:
                all_coords.extend(polygon[0])
        elif geom_dict['type'] == 'Polygon':
            all_coords.extend(geom_dict['coordinates'][0])

        if all_coords:
            lons = [coord[0] for coord in all_coords]
            lats = [coord[1] for coord in all_coords]
            return sum(lons)/len(lons), sum(lats)/len(lats)
    except Exception as e:
        pass

    return None, None


# ============================================================================
# STEP 1: LOAD BASE FIELD PRODUCTION DATA
# ============================================================================

def load_base_field_data(input_file: Path) -> pd.DataFrame:
    """
    Load base field production data from Step 2 output.

    This includes:
    - Production metrics (oil, gas, water)
    - Well counts
    - Well characteristics
    - EOR methods
    - Production ratios
    """
    print(f"\n{'='*70}")
    print(f"STEP 1: Loading Base Field Production Data")
    print(f"{'='*70}")

    print(f"Reading: {input_file}")
    df = pd.read_csv(input_file, encoding='utf-8')
    print(f"  Loaded: {len(df):,} rows, {len(df.columns)} columns")
    print(f"  Fields: {df['field_id'].nunique()}")
    print(f"  Date range: {df['start_date'].min()} to {df['end_date'].max()}")

    return df


# ============================================================================
# STEP 2: LOAD AND AGGREGATE FRACTURE DATA
# ============================================================================

def load_fracture_data(fracture_file: Path) -> pd.DataFrame:
    """
    Load fracture/completion data and aggregate to field level.

    Aggregates:
    - Proppant: total, domestic, imported, intensity
    - Fluids: water, CO2
    - Design: lateral length, stages, spacing
    - Equipment: pressure, horsepower
    - Completion type (most common)
    """
    print(f"\n{'='*70}")
    print(f"STEP 2: Loading Fracture/Completion Data")
    print(f"{'='*70}")

    if not fracture_file.exists():
        print(f"  ⚠️  File not found: {fracture_file}")
        print(f"     Fracture metrics will not be available")
        return pd.DataFrame()

    print(f"Reading: {fracture_file}")
    df = pd.read_csv(fracture_file, encoding='utf-8')
    print(f"  Loaded: {len(df):,} fracture jobs")

    # Aggregate by field_name
    print("\nAggregating fracture metrics by field...")

    agg_dict = {
        # Proppant metrics
        'proppant_domestic_tons': 'sum',
        'proppant_imported_tons': 'sum',
        'horizontal_lateral_length_m': 'mean',
        'fracture_stages_count': 'mean',

        # Fluids
        'frac_water_m3': 'sum',
        'co2_m3': 'sum',

        # Equipment
        'max_treatment_pressure_psi': 'mean',
        'frac_equipment_total_horsepower': 'mean',

        # Formation info (use first/most common value)
        'formation': lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else (x.iloc[0] if len(x) > 0 else None),
        'reservoir_subtype': lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else (x.iloc[0] if len(x) > 0 else None),
        'completion_type': lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else (x.iloc[0] if len(x) > 0 else None),

        # Count jobs
        'well_name': 'count',  # Job count
    }

    # Only aggregate columns that exist
    available_cols = {k: v for k, v in agg_dict.items() if k in df.columns}

    frac_agg = df.groupby('field_name').agg(available_cols).reset_index()

    # Rename count column
    if 'well_name' in frac_agg.columns:
        frac_agg.rename(columns={'well_name': 'fracture_job_count'}, inplace=True)

    # Calculate derived metrics
    print("\nCalculating derived fracture metrics...")

    # Total proppant
    if 'proppant_domestic_tons' in frac_agg.columns and 'proppant_imported_tons' in frac_agg.columns:
        frac_agg['total_proppant_tons'] = (
            frac_agg['proppant_domestic_tons'].fillna(0) +
            frac_agg['proppant_imported_tons'].fillna(0)
        )

        # Proppant per well
        if 'fracture_job_count' in frac_agg.columns:
            frac_agg['avg_proppant_per_well_tons'] = (
                frac_agg['total_proppant_tons'] / frac_agg['fracture_job_count']
            )

        # Proppant intensity (tons/m)
        if 'horizontal_lateral_length_m' in frac_agg.columns:
            frac_agg['proppant_intensity_tons_per_m'] = (
                frac_agg['avg_proppant_per_well_tons'] /
                frac_agg['horizontal_lateral_length_m']
            )

    # Water per well
    if 'frac_water_m3' in frac_agg.columns and 'fracture_job_count' in frac_agg.columns:
        frac_agg['avg_frac_water_per_well_m3'] = (
            frac_agg['frac_water_m3'] / frac_agg['fracture_job_count']
        )

    # Stage spacing
    if 'horizontal_lateral_length_m' in frac_agg.columns and 'fracture_stages_count' in frac_agg.columns:
        frac_agg['stage_spacing_m'] = (
            frac_agg['horizontal_lateral_length_m'] / frac_agg['fracture_stages_count']
        )

    # Rename columns for consistency
    rename_dict = {
        'horizontal_lateral_length_m': 'avg_lateral_length_m',
        'fracture_stages_count': 'avg_fracture_stages',
        'max_treatment_pressure_psi': 'avg_max_pressure_psi',
        'frac_equipment_total_horsepower': 'avg_frac_horsepower',
        'frac_water_m3': 'total_frac_water_m3',
        'co2_m3': 'total_co2_m3',
        'formation': 'primary_formation',
    }

    frac_agg.rename(columns={k: v for k, v in rename_dict.items() if k in frac_agg.columns}, inplace=True)

    print(f"  Fields with fracture data: {len(frac_agg):,}")
    print(f"  Average proppant intensity: {frac_agg.get('proppant_intensity_tons_per_m', pd.Series([np.nan])).mean():.2f} tons/m")

    return frac_agg


# ============================================================================
# STEP 3: LOAD FIELD GEOMETRY AND DEPTH
# ============================================================================

def load_geometry_data(geometry_file: Path) -> pd.DataFrame:
    """
    Load field geometry and depth data.

    Extracts:
    - Centroid coordinates from GeoJSON
    - Depth statistics (avg, min, max)
    """
    print(f"\n{'='*70}")
    print(f"STEP 3: Loading Field Geometry and Depth")
    print(f"{'='*70}")

    if not geometry_file.exists():
        print(f"  ⚠️  File not found: {geometry_file}")
        print(f"     Geometry metrics will not be available")
        return pd.DataFrame()

    print(f"Reading: {geometry_file}")
    df = pd.read_csv(geometry_file, encoding='utf-8')
    print(f"  Loaded: {len(df):,} fields with geometry")

    # Extract centroids from GeoJSON
    print("\nExtracting centroids from GeoJSON...")
    centroids = df['field_boundary_geojson'].apply(extract_centroid_from_geojson)
    df['centroid_lon'] = centroids.apply(lambda x: x[0])
    df['centroid_lat'] = centroids.apply(lambda x: x[1])

    valid_centroids = df['centroid_lat'].notna().sum()
    print(f"  Valid centroids extracted: {valid_centroids:,}/{len(df):,}")

    # Select relevant columns
    geo_cols = ['field_name', 'centroid_lat', 'centroid_lon']

    # Add depth columns if they exist
    depth_cols = ['depth_avg_m', 'depth_min_m', 'depth_max_m']
    for col in depth_cols:
        if col in df.columns:
            geo_cols.append(col)

    geometry_df = df[geo_cols].copy()

    return geometry_df


# ============================================================================
# STEP 4: LOAD FLARING DATA
# ============================================================================

def load_flaring_data(plant_file: Path, year: int = 2025) -> pd.DataFrame:
    """
    Load and aggregate flaring data from plant gas processing.

    Aggregates by field:
    - Total gas flared (mm³)
    - Field fuel consumption (mm³)
    - Flaring intensity
    """
    print(f"\n{'='*70}")
    print(f"STEP 4: Loading Flaring Data")
    print(f"{'='*70}")

    if not plant_file.exists():
        print(f"  ⚠️  File not found: {plant_file}")
        print(f"     Flaring data will not be available")
        return pd.DataFrame()

    print(f"Reading: {plant_file}")
    df = pd.read_csv(plant_file, encoding='utf-8')
    print(f"  Loaded: {len(df):,} plant records")

    # Filter to target year
    if 'year' in df.columns:
        df = df[df['year'] == year].copy()
        print(f"  Filtered to {year}: {len(df):,} records")

    # Filter for flaring and consumption concepts
    flaring_concepts = ['gas_flared_mm3', 'field_fuel_consumption_mm3']

    if 'concept' not in df.columns:
        print(f"  ⚠️  No 'concept' column found")
        return pd.DataFrame()

    df_flaring = df[df['concept'].isin(flaring_concepts)].copy()

    if len(df_flaring) == 0:
        print(f"  ⚠️  No flaring data found for concepts: {flaring_concepts}")
        return pd.DataFrame()

    print(f"  Flaring records: {len(df_flaring):,}")

    # Pivot to get flaring columns
    flaring_wide = df_flaring.pivot_table(
        index='field_name',
        columns='concept',
        values='quantity_mm3',
        aggfunc='sum'
    ).reset_index()

    print(f"  Fields with flaring data: {len(flaring_wide):,}")

    return flaring_wide


# ============================================================================
# STEP 5: MERGE ALL DATA SOURCES
# ============================================================================

def merge_comprehensive_data(
    base_df: pd.DataFrame,
    fracture_df: pd.DataFrame,
    geometry_df: pd.DataFrame,
    flaring_df: pd.DataFrame
) -> pd.DataFrame:
    """
    Merge all data sources into comprehensive field dataset.

    Uses LEFT JOIN to preserve all fields from base production data.
    """
    print(f"\n{'='*70}")
    print(f"STEP 5: Merging All Data Sources")
    print(f"{'='*70}")

    result = base_df.copy()
    print(f"Starting with base production data: {len(result):,} rows")

    # Merge fracture data
    if len(fracture_df) > 0:
        print(f"\nMerging fracture data ({len(fracture_df):,} fields)...")
        result = result.merge(
            fracture_df,
            left_on='name',
            right_on='field_name',
            how='left',
            suffixes=('', '_frac')
        )

        # Drop duplicate field_name column
        if 'field_name_frac' in result.columns:
            result.drop(columns=['field_name_frac'], inplace=True)

        fracture_matched = result['fracture_job_count'].notna().sum()
        print(f"  Matched: {fracture_matched:,} field-months with fracture data")
    else:
        print(f"\n⚠️  No fracture data to merge")

    # Merge geometry data
    if len(geometry_df) > 0:
        print(f"\nMerging geometry data ({len(geometry_df):,} fields)...")
        result = result.merge(
            geometry_df,
            left_on='name',
            right_on='field_name',
            how='left',
            suffixes=('', '_geo')
        )

        # Drop duplicate field_name column
        if 'field_name_geo' in result.columns:
            result.drop(columns=['field_name_geo'], inplace=True)

        geometry_matched = result['centroid_lat'].notna().sum()
        print(f"  Matched: {geometry_matched:,} field-months with geometry")
    else:
        print(f"\n⚠️  No geometry data to merge")

    # Merge flaring data
    if len(flaring_df) > 0:
        print(f"\nMerging flaring data ({len(flaring_df):,} fields)...")
        result = result.merge(
            flaring_df,
            left_on='name',
            right_on='field_name',
            how='left',
            suffixes=('', '_flare')
        )

        # Drop duplicate field_name column
        if 'field_name_flare' in result.columns:
            result.drop(columns=['field_name_flare'], inplace=True)

        if 'gas_flared_mm3' in result.columns:
            flaring_matched = result['gas_flared_mm3'].notna().sum()
            print(f"  Matched: {flaring_matched:,} field-months with flaring data")
    else:
        print(f"\n⚠️  No flaring data to merge")

    print(f"\n✅ Comprehensive data merged: {len(result):,} rows, {len(result.columns)} columns")

    return result


# ============================================================================
# STEP 6: SAVE COMPREHENSIVE OUTPUT
# ============================================================================

def save_comprehensive_output(
    df: pd.DataFrame,
    output_file: Path
):
    """
    Save comprehensive field data to CSV.
    """
    print(f"\n{'='*70}")
    print(f"STEP 6: Saving Comprehensive Field Data")
    print(f"{'='*70}")

    # Ensure output directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Save
    df.to_csv(output_file, index=False, encoding='utf-8')

    size_mb = output_file.stat().st_size / 1024 / 1024
    print(f"\n✅ Saved: {output_file.name}")
    print(f"   Rows: {len(df):,}")
    print(f"   Columns: {len(df.columns)}")
    print(f"   Size: {size_mb:.2f} MB")

    # Summary statistics
    print(f"\n{'='*70}")
    print(f"DATA SUMMARY")
    print(f"{'='*70}")

    print(f"\nCore Metrics:")
    print(f"  Unique fields: {df['field_id'].nunique():,}")
    print(f"  Date range: {df['start_date'].min()} to {df['end_date'].max()}")
    print(f"  Oil fields: {(df['functional_unit'] == 'oil').sum():,}")
    print(f"  Gas fields: {(df['functional_unit'] == 'gas').sum():,}")

    print(f"\nFracture Data Coverage:")
    if 'fracture_job_count' in df.columns:
        frac_count = df['fracture_job_count'].notna().sum()
        print(f"  Field-months with fracture data: {frac_count:,} ({frac_count/len(df)*100:.1f}%)")
        if frac_count > 0:
            avg_intensity = df['proppant_intensity_tons_per_m'].mean()
            print(f"  Avg proppant intensity: {avg_intensity:.2f} tons/m")
    else:
        print(f"  No fracture data available")

    print(f"\nGeometry Data Coverage:")
    if 'centroid_lat' in df.columns:
        geo_count = df['centroid_lat'].notna().sum()
        print(f"  Field-months with geometry: {geo_count:,} ({geo_count/len(df)*100:.1f}%)")
    else:
        print(f"  No geometry data available")

    print(f"\nFlaring Data Coverage:")
    if 'gas_flared_mm3' in df.columns:
        flare_count = df['gas_flared_mm3'].notna().sum()
        print(f"  Field-months with flaring data: {flare_count:,} ({flare_count/len(df)*100:.1f}%)")
        if flare_count > 0:
            total_flared = df['gas_flared_mm3'].sum()
            print(f"  Total gas flared: {total_flared:.2f} Mm³")
    else:
        print(f"  No flaring data available")


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Create comprehensive field data from all sources."""

    print("\n" + "="*70)
    print("ARGENTINA COMPREHENSIVE FIELD DATA CREATION")
    print("Integrating All 10 Data Sources")
    print("="*70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Paths
    base_dir = Path(__file__).parent.parent
    output_dir = base_dir / "output"
    translated_dir = base_dir / "raw" / "translated"

    # Configuration
    year = 2025

    # Input files
    base_production_file = output_dir / "field_production_complete.csv"
    fracture_file = translated_dir / "fracture_completion_data_english.csv"
    geometry_file = translated_dir / "field_shapes_depth_english.csv"
    plant_file = translated_dir / "plant_gas_processing_english.csv"

    # Output file
    output_file = output_dir / "comprehensive_field_data.csv"

    # Check base file exists
    if not base_production_file.exists():
        print(f"\n❌ ERROR: Base production file not found: {base_production_file}")
        print(f"   Run 02_clean_and_merge_translated.py first!")
        return

    try:
        # Step 1: Load base production data
        base_df = load_base_field_data(base_production_file)

        # Step 2: Load fracture data
        fracture_df = load_fracture_data(fracture_file)

        # Step 3: Load geometry data
        geometry_df = load_geometry_data(geometry_file)

        # Step 4: Load flaring data
        # TODO: Plant data is organized by plant, need field-plant mapping
        # flaring_df = load_flaring_data(plant_file, year)
        flaring_df = pd.DataFrame()  # Skip for now

        # Step 5: Merge all sources
        comprehensive_df = merge_comprehensive_data(
            base_df,
            fracture_df,
            geometry_df,
            flaring_df
        )

        # Step 6: Save output
        save_comprehensive_output(comprehensive_df, output_file)

        print(f"\n{'='*70}")
        print(f"✅ COMPREHENSIVE DATA CREATION COMPLETE")
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
