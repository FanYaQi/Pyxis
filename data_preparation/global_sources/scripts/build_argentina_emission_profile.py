#!/usr/bin/env python3
"""
Build Argentina methane emission profile plots.

This script:
1. Loads Carbon Mapper plume data for Argentina
2. Matches plumes to Pyxis fields using spatial join
3. Queries database for field production data (num_prod_wells, oil_prod)
4. Calculates normalized emission rates:
   - Per-well: emission_auto_kg_hr / num_prod_wells
   - Per-barrel: emission_auto_kg_hr / oil_prod (bbl/day)
5. Creates profile plots showing emission vs persistence

Usage:
    python build_argentina_emission_profile.py
    python build_argentina_emission_profile.py --use-csv  # Use CSV instead of database
"""

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from shapely.geometry import Point, shape, box

# SQLAlchemy is optional (only needed for database queries)
try:
    from sqlalchemy import create_engine, text
    HAS_SQLALCHEMY = True
except ImportError:
    HAS_SQLALCHEMY = False
    print("Warning: sqlalchemy not installed. Database queries will not be available.")

# Paths
SCRIPTS_DIR = Path(__file__).parent
DATA_DIR = SCRIPTS_DIR.parent
OUTPUT_DIR = DATA_DIR / "output" / "argentina"
CM_PROCESSED_DIR = DATA_DIR / "methane_CM_processed"
CM_RAW_DIR = DATA_DIR / "methane_raw" / "argentina"
METHANE_RAW_DIR = DATA_DIR / "methane_raw" / "argentina"

# Database connection settings
DB_HOST = os.environ.get("POSTGRES_SERVER", "localhost")
DB_PORT = os.environ.get("POSTGRES_PORT", "5555")
DB_NAME = os.environ.get("POSTGRES_DB", "pyxis")
DB_USER = os.environ.get("POSTGRES_USER", "postgres")
DB_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "postgres")

DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Buffer distance for spatial matching (in degrees, ~5km at Argentina latitude)
BUFFER_DISTANCE_DEG = 0.05


def load_cm_plumes() -> pd.DataFrame:
    """Load Carbon Mapper plume data for Argentina."""
    # Find the most recent processed file
    cm_files = list(CM_PROCESSED_DIR.glob("ch4_argentina_sources_*_processed.csv"))
    if not cm_files:
        raise FileNotFoundError(f"No CM processed files found in {CM_PROCESSED_DIR}")

    # Use the most recent file
    cm_file = max(cm_files, key=lambda f: f.stat().st_mtime)
    print(f"Loading CM plumes from: {cm_file.name}")

    df = pd.read_csv(cm_file)
    print(f"  Loaded {len(df)} plume sources")
    print(f"  Date range: {df['timestamp_min'].min()} to {df['timestamp_max'].max()}")
    print(f"  Mean persistence: {df['persistence'].mean():.2%}")
    print(f"  Mean emission (when detected): {df['emission_auto_kg_hr'].mean():.1f} kg/hr")

    return df


def load_cm_scenes() -> gpd.GeoDataFrame:
    """Load all CM scene data for Argentina from existing CSV files."""
    print("\nLoading CM scene data...")

    scene_files = [
        METHANE_RAW_DIR / "argentina_tanager_all_scenes_summary.csv",
        METHANE_RAW_DIR / "argentina_emit_all_scenes_summary.csv",
        METHANE_RAW_DIR / "argentina_ang_scenes_summary.csv",
    ]

    all_scenes = []
    for f in scene_files:
        if f.exists():
            df = pd.read_csv(f)
            instrument = f.stem.split('_')[1]  # tanager, emit, ang
            df['instrument_source'] = instrument
            all_scenes.append(df)
            print(f"  Loaded {len(df)} scenes from {f.name}")

    if not all_scenes:
        print("  ERROR: No scene files found!")
        return gpd.GeoDataFrame()

    scenes_df = pd.concat(all_scenes, ignore_index=True)
    print(f"  Total scenes: {len(scenes_df)}")

    # Create geometry from bounds
    geometries = []
    for _, row in scenes_df.iterrows():
        try:
            geom = box(
                row['bounds_min_lon'],
                row['bounds_min_lat'],
                row['bounds_max_lon'],
                row['bounds_max_lat']
            )
            geometries.append(geom)
        except (KeyError, TypeError):
            geometries.append(None)

    scenes_gdf = gpd.GeoDataFrame(scenes_df, geometry=geometries, crs="EPSG:4326")
    scenes_gdf = scenes_gdf[scenes_gdf.geometry.notna()]
    print(f"  Scenes with valid geometry: {len(scenes_gdf)}")

    return scenes_gdf


def match_scenes_to_fields(
    scenes_gdf: gpd.GeoDataFrame,
    fields_gdf: gpd.GeoDataFrame,
    production_df: pd.DataFrame = None
) -> Tuple[pd.DataFrame, dict]:
    """
    Match CM scenes to fields to determine coverage.

    Returns:
        - field_coverage_df: DataFrame with field_id, scene_count, total_wells
        - coverage_stats: dict with total_field_scene_obs, total_well_scene_obs
    """
    print("\nMatching scenes to fields...")

    # Ensure field production data is available for well counts
    if production_df is not None and 'field_name_normalized' in production_df.columns:
        fields_with_prod = fields_gdf.copy()
        fields_with_prod['name_normalized'] = fields_with_prod['name'].astype(str).str.upper().str.strip()
        fields_with_prod = fields_with_prod.merge(
            production_df[['field_name_normalized', 'avg_num_prod_wells', 'avg_oil_prod']],
            left_on='name_normalized',
            right_on='field_name_normalized',
            how='left'
        )
    else:
        fields_with_prod = fields_gdf.copy()
        fields_with_prod['avg_num_prod_wells'] = 1  # Default if no production data
        fields_with_prod['avg_oil_prod'] = 1

    # Spatial join: find all fields that intersect with each scene
    print("  Performing spatial join (scenes × fields)...")
    scene_field_matches = gpd.sjoin(
        scenes_gdf[['scene_id', 'name', 'geometry']],
        fields_with_prod[['id', 'name', 'avg_num_prod_wells', 'avg_oil_prod', 'geometry']],
        how='inner',
        predicate='intersects'
    )

    print(f"  Total scene-field intersections: {len(scene_field_matches)}")

    # Aggregate by field
    field_coverage = scene_field_matches.groupby('id').agg({
        'scene_id': 'count',
        'avg_num_prod_wells': 'first',
        'avg_oil_prod': 'first'
    }).reset_index()
    field_coverage.columns = ['field_id', 'scene_count', 'avg_num_prod_wells', 'avg_oil_prod']

    print(f"  Unique fields with CM coverage: {len(field_coverage)}")

    # Calculate totals for denominator
    total_field_scene_obs = len(scene_field_matches)
    total_well_scene_obs = (scene_field_matches['avg_num_prod_wells'].fillna(1) * 1).sum()  # Each scene-field pair
    total_bbl_scene_obs = (scene_field_matches['avg_oil_prod'].fillna(1) * 1).sum()

    # Better calculation: sum wells and production for each scene-field observation
    scene_field_matches['wells_in_obs'] = scene_field_matches['avg_num_prod_wells'].fillna(1)
    scene_field_matches['bbl_in_obs'] = scene_field_matches['avg_oil_prod'].fillna(1)
    total_well_scene_obs = scene_field_matches['wells_in_obs'].sum()
    total_bbl_scene_obs = scene_field_matches['bbl_in_obs'].sum()

    coverage_stats = {
        'total_scenes': len(scenes_gdf),
        'unique_fields_observed': len(field_coverage),
        'total_field_scene_observations': total_field_scene_obs,
        'total_well_scene_observations': total_well_scene_obs,
        'total_bbl_scene_observations': total_bbl_scene_obs,
    }

    print(f"  Coverage stats:")
    print(f"    Total field-scene observations: {total_field_scene_obs}")
    print(f"    Total well-scene observations: {total_well_scene_obs:.0f}")
    print(f"    Total bbl-scene observations: {total_bbl_scene_obs:.0f}")

    return field_coverage, coverage_stats


def load_fields_from_database() -> gpd.GeoDataFrame:
    """Load field geometries from database."""
    if not HAS_SQLALCHEMY:
        print("\nDatabase not available (sqlalchemy not installed)")
        return None

    print(f"\nConnecting to database: {DB_HOST}:{DB_PORT}/{DB_NAME}")

    try:
        engine = create_engine(DATABASE_URL)

        # Query field metadata with geometry
        query = """
            SELECT
                id,
                pyxis_field_code,
                name,
                country,
                functional_unit,
                geometry
            FROM pyxis_field_meta
            WHERE country = 'Argentina'
              AND geometry IS NOT NULL
        """

        fields_gdf = gpd.read_postgis(query, engine, geom_col='geometry')
        print(f"  Loaded {len(fields_gdf)} fields from database")

        return fields_gdf

    except Exception as e:
        print(f"  Database connection failed: {e}")
        return None


def load_fields_from_csv() -> gpd.GeoDataFrame:
    """Load field geometries from CSV file."""
    csv_file = OUTPUT_DIR / "argentina_pyxis_static_fields_cd.csv"
    print(f"\nLoading fields from CSV: {csv_file.name}")

    df = pd.read_csv(csv_file)

    # Parse geometry from JSON string
    geometries = []
    valid_rows = []

    for idx, row in df.iterrows():
        try:
            geom_json = json.loads(row['geometry'])
            geom = shape(geom_json)
            geometries.append(geom)
            valid_rows.append(idx)
        except (json.JSONDecodeError, TypeError, KeyError):
            continue

    df_valid = df.loc[valid_rows].copy()
    gdf = gpd.GeoDataFrame(df_valid, geometry=geometries, crs="EPSG:4326")

    # Rename field_id to id for consistency
    if 'field_id' in gdf.columns and 'id' not in gdf.columns:
        gdf = gdf.rename(columns={'field_id': 'id'})

    print(f"  Loaded {len(gdf)} fields with valid geometries")

    return gdf


def match_plumes_to_fields(
    plumes_df: pd.DataFrame,
    fields_gdf: gpd.GeoDataFrame,
    buffer_distance: float = BUFFER_DISTANCE_DEG
) -> gpd.GeoDataFrame:
    """Match plumes to fields using spatial join."""
    print("\nMatching plumes to fields...")

    # Create GeoDataFrame from plumes with reset index
    plumes_df = plumes_df.reset_index(drop=True)
    plume_points = gpd.GeoDataFrame(
        plumes_df,
        geometry=gpd.points_from_xy(plumes_df['longitude'], plumes_df['latitude']),
        crs="EPSG:4326"
    )
    plume_points['plume_idx'] = plume_points.index  # Track original index

    # Step 1: Exact match (point within polygon)
    fields_for_join = fields_gdf[['id', 'name', 'geometry']].copy().reset_index(drop=True)

    exact_matches = gpd.sjoin(
        plume_points,
        fields_for_join,
        how='left',
        predicate='within'
    )

    # Track which plumes got matched
    matched_plume_indices = exact_matches[exact_matches['id'].notna()]['plume_idx'].unique()
    unmatched_plume_indices = [i for i in plume_points['plume_idx'] if i not in matched_plume_indices]

    # Mark match types
    exact_matches['match_type'] = None
    exact_matches.loc[exact_matches['id'].notna(), 'match_type'] = 'exact'

    # Step 2: Buffer match for unmatched plumes
    if len(unmatched_plume_indices) > 0:
        unmatched_plumes = plume_points[plume_points['plume_idx'].isin(unmatched_plume_indices)].copy()

        # Create buffered field geometries
        fields_buffered = fields_gdf.copy().reset_index(drop=True)
        fields_buffered['geometry'] = fields_buffered['geometry'].buffer(buffer_distance)

        buffer_matches = gpd.sjoin(
            unmatched_plumes,
            fields_buffered[['id', 'name', 'geometry']],
            how='left',
            predicate='within'
        )
        buffer_matches['match_type'] = 'buffer'
        buffer_matches.loc[buffer_matches['id'].isna(), 'match_type'] = 'unmatched'

        # Combine: keep exact matches and add buffer matches for previously unmatched
        exact_only = exact_matches[exact_matches['match_type'] == 'exact'].copy()
        result = pd.concat([exact_only, buffer_matches], ignore_index=True)
    else:
        result = exact_matches.copy()
        result.loc[result['match_type'].isna(), 'match_type'] = 'unmatched'

    # Rename matched field columns
    result = result.rename(columns={'id': 'field_id', 'name': 'field_name'})

    # Drop duplicates - keep first match per plume (in case of multiple overlapping fields)
    result = result.drop_duplicates(subset=['source_id'], keep='first')

    # Print summary
    match_counts = result['match_type'].value_counts()
    print(f"  Match results:")
    for match_type, count in match_counts.items():
        print(f"    {match_type}: {count}")

    return result


def get_field_production_from_database(
    field_ids: list,
    start_date: str = '2023-11-01'
) -> pd.DataFrame:
    """Query database for field production data."""
    if not HAS_SQLALCHEMY:
        print("\nDatabase not available (sqlalchemy not installed)")
        return pd.DataFrame()

    if not field_ids:
        return pd.DataFrame()

    print(f"\nQuerying production data for {len(field_ids)} fields...")

    try:
        engine = create_engine(DATABASE_URL)

        # Query average production over CM observation period
        query = text("""
            SELECT
                pyxis_field_meta_id as field_id,
                AVG(num_prod_wells) as avg_num_prod_wells,
                AVG(oil_prod) as avg_oil_prod,
                COUNT(*) as data_count
            FROM pyxis_field_data
            WHERE pyxis_field_meta_id = ANY(:field_ids)
              AND valid_from >= :start_date
              AND functional_unit = 'oil'
            GROUP BY pyxis_field_meta_id
        """)

        with engine.connect() as conn:
            result = conn.execute(query, {
                'field_ids': field_ids,
                'start_date': start_date
            })
            production_df = pd.DataFrame(result.fetchall(), columns=result.keys())

        print(f"  Retrieved production data for {len(production_df)} fields")
        if len(production_df) > 0:
            print(f"  Avg wells: {production_df['avg_num_prod_wells'].mean():.1f}")
            print(f"  Avg oil prod: {production_df['avg_oil_prod'].mean():.1f} bbl/day")

        return production_df

    except Exception as e:
        print(f"  Database query failed: {e}")
        return pd.DataFrame()


def get_field_production_from_csv(field_ids: list, field_names: list = None) -> pd.DataFrame:
    """Get field production data from CSV files (fallback).

    Note: The well production data uses string field codes (e.g., 'AGA', 'FDRO'),
    while the pyxis static fields use numeric IDs. We match by field_name instead.
    """
    print(f"\nLoading production data from CSV...")

    # Try to find Argentina well production data
    well_prod_files = list((DATA_DIR.parent / "argentina" / "raw" / "translated").glob("well_production_202*_english.csv"))

    if not well_prod_files:
        print("  No well production files found")
        return pd.DataFrame()

    print(f"  Found {len(well_prod_files)} well production files")

    # Load and aggregate 2023-2024 data
    all_data = []
    for f in well_prod_files:
        # Extract year from filename like well_production_2024_english.csv
        try:
            year = int(f.stem.split('_')[2])
            if year >= 2023:
                df = pd.read_csv(f, low_memory=False)
                all_data.append(df)
                print(f"    Loaded {len(df)} records from {f.name}")
        except (ValueError, IndexError):
            continue

    if not all_data:
        print("  No 2023+ data found")
        return pd.DataFrame()

    combined = pd.concat(all_data, ignore_index=True)
    print(f"  Total records: {len(combined)}")

    # Filter for producing wells
    producing = combined[combined['well_status'] == 'producing'].copy()
    print(f"  Producing wells: {len(producing)}")

    if len(producing) == 0:
        return pd.DataFrame()

    # Aggregate by field_name (more reliable than field_id codes)
    # Calculate average monthly stats per field
    field_stats = producing.groupby('field_name').agg({
        'well_id': 'nunique',  # Count unique wells
        'oil_production_m3': 'sum',  # Sum production for the period
        'year': 'count'  # Number of well-months to calculate average
    }).reset_index()

    # Calculate averages
    # avg_oil_prod_m3 = total_production / num_well_months, then multiply by unique wells
    # This gives us the average field production per month
    field_stats['avg_oil_prod_m3_per_month'] = field_stats['oil_production_m3'] / (field_stats['year'] / field_stats['well_id'])

    field_stats.columns = ['field_name', 'avg_num_prod_wells', 'total_oil_m3', 'well_months', 'avg_oil_prod_m3']

    # Convert m3/month to bbl/day (1 m3 = 6.29 bbl, assume 30 days/month)
    field_stats['avg_oil_prod'] = field_stats['avg_oil_prod_m3'] * 6.29 / 30

    # Normalize field names for matching (uppercase, strip whitespace)
    field_stats['field_name_normalized'] = field_stats['field_name'].str.upper().str.strip()

    print(f"  Aggregated stats for {len(field_stats)} fields")

    # If field_names provided, filter to those
    if field_names is not None and len(field_names) > 0:
        field_names_normalized = [str(n).upper().strip() for n in field_names if pd.notna(n)]
        field_stats = field_stats[field_stats['field_name_normalized'].isin(field_names_normalized)]
        print(f"  After filtering to requested fields: {len(field_stats)}")

    return field_stats


def calculate_emission_profiles(matched_df: pd.DataFrame, production_df: pd.DataFrame) -> pd.DataFrame:
    """Calculate per-well and per-barrel emission rates."""
    print("\nCalculating emission profiles...")

    # Normalize field names for matching
    matched_df = matched_df.copy()
    matched_df['field_name_normalized'] = matched_df['field_name'].astype(str).str.upper().str.strip()

    # Merge matched plumes with production data by normalized field name
    if 'field_name_normalized' in production_df.columns:
        merged = matched_df.merge(
            production_df,
            on='field_name_normalized',
            how='left',
            suffixes=('', '_prod')
        )
    else:
        # Fallback to field_id merge (for database queries)
        merged = matched_df.merge(
            production_df,
            on='field_id',
            how='left'
        )

    # Filter to matched plumes with production data and valid emissions
    valid = merged[
        (merged['match_type'].isin(['exact', 'buffer'])) &
        (merged['avg_num_prod_wells'].notna()) &
        (merged['avg_num_prod_wells'] > 0) &
        (merged['emission_auto_kg_hr'].notna()) &
        (merged['avg_oil_prod'].notna()) &
        (merged['avg_oil_prod'] > 0)
    ].copy()

    if len(valid) == 0:
        print("  No valid matches with production data!")
        return pd.DataFrame()

    # Calculate normalized emissions
    valid['emission_per_well'] = valid['emission_auto_kg_hr'] / valid['avg_num_prod_wells']
    valid['emission_per_bbl'] = valid['emission_auto_kg_hr'] / valid['avg_oil_prod']

    # Also calculate persistence-adjusted versions
    if 'persistence_adjusted_emission_kg_hr' in valid.columns:
        valid['pers_adj_emission_per_well'] = valid['persistence_adjusted_emission_kg_hr'] / valid['avg_num_prod_wells']
        valid['pers_adj_emission_per_bbl'] = valid['persistence_adjusted_emission_kg_hr'] / valid['avg_oil_prod']

    print(f"  Valid matches with production: {len(valid)}")
    print(f"  Per-well emission: mean={valid['emission_per_well'].mean():.2f}, median={valid['emission_per_well'].median():.2f} kg/hr")
    print(f"  Per-barrel emission: mean={valid['emission_per_bbl'].mean():.4f}, median={valid['emission_per_bbl'].median():.4f} kg/hr per bbl/day")

    return valid


def create_profile_plots(profile_df: pd.DataFrame, output_dir: Path) -> None:
    """Create emission profile plots."""
    print("\nCreating profile plots...")

    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Set up the figure with 2x2 subplots
    fig, axes = plt.subplots(2, 2, figsize=(14, 12))

    # Color by observation count
    sizes = profile_df['observation_date_count'] * 5  # Scale for visibility
    colors = profile_df['plume_count']

    # Plot 1: Per-Well Emission vs Persistence (scatter)
    ax1 = axes[0, 0]
    scatter1 = ax1.scatter(
        profile_df['emission_per_well'],
        profile_df['persistence'],
        s=sizes,
        c=colors,
        cmap='viridis',
        alpha=0.7,
        edgecolors='black',
        linewidths=0.5
    )
    ax1.set_xlabel('Emission per Well (kg/hr)', fontsize=12)
    ax1.set_ylabel('Persistence (detection probability)', fontsize=12)
    ax1.set_title('Per-Well Emission Profile', fontsize=14)
    ax1.set_xscale('log')
    ax1.grid(True, alpha=0.3)
    plt.colorbar(scatter1, ax=ax1, label='Plume count')

    # Add statistics annotation
    stats_text = (
        f"n={len(profile_df)}\n"
        f"mean={profile_df['emission_per_well'].mean():.1f}\n"
        f"median={profile_df['emission_per_well'].median():.1f}"
    )
    ax1.annotate(stats_text, xy=(0.95, 0.95), xycoords='axes fraction',
                 ha='right', va='top', fontsize=10,
                 bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

    # Plot 2: Per-Barrel Emission vs Persistence (scatter)
    ax2 = axes[0, 1]
    scatter2 = ax2.scatter(
        profile_df['emission_per_bbl'],
        profile_df['persistence'],
        s=sizes,
        c=colors,
        cmap='viridis',
        alpha=0.7,
        edgecolors='black',
        linewidths=0.5
    )
    ax2.set_xlabel('Emission per bbl/day (kg/hr per bbl/day)', fontsize=12)
    ax2.set_ylabel('Persistence (detection probability)', fontsize=12)
    ax2.set_title('Per-Barrel Emission Profile', fontsize=14)
    ax2.set_xscale('log')
    ax2.grid(True, alpha=0.3)
    plt.colorbar(scatter2, ax=ax2, label='Plume count')

    stats_text = (
        f"n={len(profile_df)}\n"
        f"mean={profile_df['emission_per_bbl'].mean():.4f}\n"
        f"median={profile_df['emission_per_bbl'].median():.4f}"
    )
    ax2.annotate(stats_text, xy=(0.95, 0.95), xycoords='axes fraction',
                 ha='right', va='top', fontsize=10,
                 bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

    # Plot 3: Per-Well Emission Distribution (histogram)
    ax3 = axes[1, 0]
    ax3.hist(profile_df['emission_per_well'], bins=20, edgecolor='black', alpha=0.7, color='steelblue')
    ax3.axvline(profile_df['emission_per_well'].mean(), color='red', linestyle='--', label=f"Mean: {profile_df['emission_per_well'].mean():.1f}")
    ax3.axvline(profile_df['emission_per_well'].median(), color='orange', linestyle='--', label=f"Median: {profile_df['emission_per_well'].median():.1f}")
    ax3.set_xlabel('Emission per Well (kg/hr)', fontsize=12)
    ax3.set_ylabel('Count', fontsize=12)
    ax3.set_title('Per-Well Emission Distribution', fontsize=14)
    ax3.legend()
    ax3.grid(True, alpha=0.3)

    # Plot 4: Per-Barrel Emission Distribution (histogram)
    ax4 = axes[1, 1]
    ax4.hist(profile_df['emission_per_bbl'], bins=20, edgecolor='black', alpha=0.7, color='coral')
    ax4.axvline(profile_df['emission_per_bbl'].mean(), color='red', linestyle='--', label=f"Mean: {profile_df['emission_per_bbl'].mean():.4f}")
    ax4.axvline(profile_df['emission_per_bbl'].median(), color='orange', linestyle='--', label=f"Median: {profile_df['emission_per_bbl'].median():.4f}")
    ax4.set_xlabel('Emission per bbl/day (kg/hr per bbl/day)', fontsize=12)
    ax4.set_ylabel('Count', fontsize=12)
    ax4.set_title('Per-Barrel Emission Distribution', fontsize=14)
    ax4.legend()
    ax4.grid(True, alpha=0.3)

    plt.tight_layout()

    # Save plot
    plot_path = output_dir / f"emission_profiles_{timestamp}.png"
    plt.savefig(plot_path, dpi=150, bbox_inches='tight')
    print(f"  Saved plot: {plot_path.name}")

    # Also save as latest
    latest_path = output_dir / "emission_profiles_latest.png"
    plt.savefig(latest_path, dpi=150, bbox_inches='tight')
    print(f"  Saved plot: {latest_path.name}")

    plt.close()


def create_probability_profile_plots(
    profile_df: pd.DataFrame,
    coverage_stats: Dict,
    output_dir: Path
) -> None:
    """
    Create probability-based emission profile plots.

    All plots use the same denominator (total field-scene observations).
    Y-axis = (# plumes in bin) / (total field-scene observations)
    """
    print("\nCreating probability profile plots...")

    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    total_field_scene_obs = coverage_stats['total_field_scene_observations']

    if total_field_scene_obs == 0:
        print("  ERROR: No field-scene observations!")
        return

    # Define log-scale emission bins (more granular)
    raw_emission_bins = [0, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000]
    per_well_bins = [0, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10]
    per_bbl_bins = [0, 0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5]

    # Calculate bin assignments
    profile_df = profile_df.copy()
    profile_df['raw_emission_bin'] = pd.cut(
        profile_df['emission_auto_kg_hr'],
        bins=raw_emission_bins + [np.inf],
        labels=[f"{raw_emission_bins[i]}-{raw_emission_bins[i+1]}" for i in range(len(raw_emission_bins)-1)] + [f"{raw_emission_bins[-1]}+"]
    )
    profile_df['per_well_bin'] = pd.cut(
        profile_df['emission_per_well'],
        bins=per_well_bins + [np.inf],
        labels=[f"{per_well_bins[i]}-{per_well_bins[i+1]}" for i in range(len(per_well_bins)-1)] + [f"{per_well_bins[-1]}+"]
    )
    profile_df['per_bbl_bin'] = pd.cut(
        profile_df['emission_per_bbl'],
        bins=per_bbl_bins + [np.inf],
        labels=[f"{per_bbl_bins[i]}-{per_bbl_bins[i+1]}" for i in range(len(per_bbl_bins)-1)] + [f"{per_bbl_bins[-1]}+"]
    )

    # Count plumes per bin
    raw_counts = profile_df['raw_emission_bin'].value_counts().sort_index()
    per_well_counts = profile_df['per_well_bin'].value_counts().sort_index()
    per_bbl_counts = profile_df['per_bbl_bin'].value_counts().sort_index()

    # Calculate probabilities
    raw_probs = raw_counts / total_field_scene_obs
    per_well_probs = per_well_counts / total_field_scene_obs
    per_bbl_probs = per_bbl_counts / total_field_scene_obs

    # Set up style
    plt.style.use('seaborn-v0_8-whitegrid')

    # Create figure with 3 subplots - more space
    fig, axes = plt.subplots(1, 3, figsize=(20, 7))
    fig.suptitle('Argentina Methane Emission Probability Profiles', fontsize=16, fontweight='bold', y=1.02)

    # Color palette
    colors = ['#3498db', '#e74c3c', '#2ecc71']

    # Helper function for formatting probability labels
    def format_prob(p):
        if p <= 0:
            return ""
        inv = int(1/p)
        if inv >= 1000:
            return f"1/{inv//1000}k"
        return f"1/{inv}"

    # Plot 1: Raw Emission Profile
    ax1 = axes[0]
    x_pos = np.arange(len(raw_probs))
    bars1 = ax1.bar(x_pos, raw_probs.values, color=colors[0], edgecolor='white', alpha=0.85, width=0.7)
    ax1.set_xticks(x_pos)
    ax1.set_xticklabels(raw_probs.index, rotation=45, ha='right', fontsize=9)
    ax1.set_xlabel('Emission (kg/hr)', fontsize=11, fontweight='bold')
    ax1.set_ylabel('Detection Probability', fontsize=11, fontweight='bold')
    ax1.set_title('Raw Emission Profile', fontsize=13, fontweight='bold', pad=10)
    ax1.set_yscale('log')
    ax1.set_ylim(bottom=1e-5)
    ax1.grid(True, alpha=0.3, axis='y', which='both')
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)

    # Add value labels on bars
    for bar, prob in zip(bars1, raw_probs.values):
        if prob > 0:
            label = format_prob(prob)
            ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() * 1.3,
                    label, ha='center', va='bottom', fontsize=8, fontweight='bold', color='#2c3e50')

    # Add stats box
    total_prob = raw_probs.sum()
    stats_text = (
        f"Total plumes: {len(profile_df)}\n"
        f"Field-scene obs: {total_field_scene_obs:,}\n"
        f"Detection rate: {format_prob(total_prob)}"
    )
    ax1.text(0.97, 0.97, stats_text, transform=ax1.transAxes,
             ha='right', va='top', fontsize=9,
             bbox=dict(boxstyle='round,pad=0.5', facecolor='white', edgecolor='#bdc3c7', alpha=0.9))

    # Plot 2: Per-Well Emission Profile
    ax2 = axes[1]
    x_pos = np.arange(len(per_well_probs))
    bars2 = ax2.bar(x_pos, per_well_probs.values, color=colors[1], edgecolor='white', alpha=0.85, width=0.7)
    ax2.set_xticks(x_pos)
    ax2.set_xticklabels(per_well_probs.index, rotation=45, ha='right', fontsize=9)
    ax2.set_xlabel('Emission per Well (kg/hr/well)', fontsize=11, fontweight='bold')
    ax2.set_ylabel('Detection Probability', fontsize=11, fontweight='bold')
    ax2.set_title('Per-Well Normalized Profile', fontsize=13, fontweight='bold', pad=10)
    ax2.set_yscale('log')
    ax2.set_ylim(bottom=1e-5)
    ax2.grid(True, alpha=0.3, axis='y', which='both')
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)

    for bar, prob in zip(bars2, per_well_probs.values):
        if prob > 0:
            label = format_prob(prob)
            ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() * 1.3,
                    label, ha='center', va='bottom', fontsize=8, fontweight='bold', color='#2c3e50')

    # Calculate expected value
    bin_midpoints = [(per_well_bins[i] + per_well_bins[i+1])/2 for i in range(len(per_well_bins)-1)]
    bin_midpoints.append(per_well_bins[-1] * 1.5)
    expected_emission_per_well = sum(p * m for p, m in zip(per_well_probs.values, bin_midpoints))

    ax2.text(0.97, 0.97, f"E[emission/well]\n= {expected_emission_per_well:.4f} kg/hr",
             transform=ax2.transAxes, ha='right', va='top', fontsize=10, fontweight='bold',
             bbox=dict(boxstyle='round,pad=0.5', facecolor='white', edgecolor='#bdc3c7', alpha=0.9))

    # Plot 3: Per-Barrel Emission Profile
    ax3 = axes[2]
    x_pos = np.arange(len(per_bbl_probs))
    bars3 = ax3.bar(x_pos, per_bbl_probs.values, color=colors[2], edgecolor='white', alpha=0.85, width=0.7)
    ax3.set_xticks(x_pos)
    ax3.set_xticklabels(per_bbl_probs.index, rotation=45, ha='right', fontsize=9)
    ax3.set_xlabel('Emission per bbl/day (kg/hr/(bbl/day))', fontsize=11, fontweight='bold')
    ax3.set_ylabel('Detection Probability', fontsize=11, fontweight='bold')
    ax3.set_title('Per-Barrel Normalized Profile', fontsize=13, fontweight='bold', pad=10)
    ax3.set_yscale('log')
    ax3.set_ylim(bottom=1e-5)
    ax3.grid(True, alpha=0.3, axis='y', which='both')
    ax3.spines['top'].set_visible(False)
    ax3.spines['right'].set_visible(False)

    for bar, prob in zip(bars3, per_bbl_probs.values):
        if prob > 0:
            label = format_prob(prob)
            ax3.text(bar.get_x() + bar.get_width()/2, bar.get_height() * 1.3,
                    label, ha='center', va='bottom', fontsize=8, fontweight='bold', color='#2c3e50')

    # Calculate expected value for CI
    bbl_bin_midpoints = [(per_bbl_bins[i] + per_bbl_bins[i+1])/2 for i in range(len(per_bbl_bins)-1)]
    bbl_bin_midpoints.append(per_bbl_bins[-1] * 1.5)
    expected_emission_per_bbl = sum(p * m for p, m in zip(per_bbl_probs.values, bbl_bin_midpoints))

    ax3.text(0.97, 0.97, f"E[emission/bbl]\n= {expected_emission_per_bbl:.6f}\nkg/hr/(bbl/day)\n(CI intensity)",
             transform=ax3.transAxes, ha='right', va='top', fontsize=10, fontweight='bold',
             bbox=dict(boxstyle='round,pad=0.5', facecolor='white', edgecolor='#bdc3c7', alpha=0.9))

    plt.tight_layout()
    plt.subplots_adjust(top=0.92, wspace=0.25)

    # Save plot
    plot_path = output_dir / f"emission_probability_profiles_{timestamp}.png"
    plt.savefig(plot_path, dpi=200, bbox_inches='tight', facecolor='white')
    print(f"  Saved plot: {plot_path.name}")

    latest_path = output_dir / "emission_probability_profiles_latest.png"
    plt.savefig(latest_path, dpi=200, bbox_inches='tight', facecolor='white')
    print(f"  Saved plot: {latest_path.name}")

    plt.close()

    # Reset style
    plt.style.use('default')

    # Return summary for saving
    return {
        'raw_emission_probs': raw_probs.to_dict(),
        'per_well_probs': per_well_probs.to_dict(),
        'per_bbl_probs': per_bbl_probs.to_dict(),
        'expected_emission_per_well': expected_emission_per_well,
        'expected_emission_per_bbl': expected_emission_per_bbl,
        'total_detection_rate': total_prob,
    }


def save_outputs(matched_df: pd.DataFrame, profile_df: pd.DataFrame, output_dir: Path) -> None:
    """Save output CSV files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save plume-field matches
    if len(matched_df) > 0:
        # Drop geometry column for CSV output
        matches_csv = matched_df.drop(columns=['geometry'], errors='ignore')
        matches_path = output_dir / f"plume_field_matches_{timestamp}.csv"
        matches_csv.to_csv(matches_path, index=False)
        print(f"  Saved: {matches_path.name}")

    # Save emission profile
    if len(profile_df) > 0:
        profile_csv = profile_df.drop(columns=['geometry'], errors='ignore')
        profile_path = output_dir / f"emission_profile_{timestamp}.csv"
        profile_csv.to_csv(profile_path, index=False)
        print(f"  Saved: {profile_path.name}")

        # Save summary statistics
        summary = {
            'timestamp': timestamp,
            'total_plumes': len(matched_df),
            'matched_plumes': len(profile_df),
            'per_well_emission_mean': profile_df['emission_per_well'].mean(),
            'per_well_emission_median': profile_df['emission_per_well'].median(),
            'per_well_emission_std': profile_df['emission_per_well'].std(),
            'per_bbl_emission_mean': profile_df['emission_per_bbl'].mean(),
            'per_bbl_emission_median': profile_df['emission_per_bbl'].median(),
            'per_bbl_emission_std': profile_df['emission_per_bbl'].std(),
            'persistence_mean': profile_df['persistence'].mean(),
            'avg_wells_per_field': profile_df['avg_num_prod_wells'].mean(),
            'avg_oil_prod_per_field': profile_df['avg_oil_prod'].mean(),
        }
        summary_path = output_dir / f"emission_profile_summary_{timestamp}.json"
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)
        print(f"  Saved: {summary_path.name}")


def main():
    parser = argparse.ArgumentParser(description="Build Argentina methane emission profiles")
    parser.add_argument('--use-csv', action='store_true', help="Use CSV files instead of database")
    args = parser.parse_args()

    print("=" * 60)
    print("ARGENTINA METHANE EMISSION PROFILE BUILDER")
    print("=" * 60)

    # Step 1: Load CM plumes
    cm_plumes = load_cm_plumes()

    # Step 2: Load field geometries
    if args.use_csv:
        fields_gdf = load_fields_from_csv()
    else:
        fields_gdf = load_fields_from_database()
        if fields_gdf is None or len(fields_gdf) == 0:
            print("Falling back to CSV...")
            fields_gdf = load_fields_from_csv()

    if fields_gdf is None or len(fields_gdf) == 0:
        print("ERROR: No field data available!")
        return

    # Step 3: Match plumes to fields
    matched_df = match_plumes_to_fields(cm_plumes, fields_gdf)

    # Step 4: Get production data
    matched_fields = matched_df[matched_df['match_type'].isin(['exact', 'buffer'])].copy()
    matched_field_ids = matched_fields['field_id'].dropna().unique().tolist()
    matched_field_names = matched_fields['field_name'].dropna().unique().tolist()

    # Convert field_ids to int if needed
    matched_field_ids = [int(fid) for fid in matched_field_ids if pd.notna(fid)]

    print(f"\nMatched field IDs: {len(matched_field_ids)}")
    print(f"Matched field names: {len(matched_field_names)}")

    if args.use_csv:
        production_df = get_field_production_from_csv(matched_field_ids, matched_field_names)
    else:
        production_df = get_field_production_from_database(matched_field_ids)
        if len(production_df) == 0:
            print("Falling back to CSV for production data...")
            production_df = get_field_production_from_csv(matched_field_ids, matched_field_names)

    if len(production_df) == 0:
        print("ERROR: No production data available!")
        return

    # Step 5: Calculate emission profiles
    profile_df = calculate_emission_profiles(matched_df, production_df)

    if len(profile_df) == 0:
        print("ERROR: No valid emission profiles calculated!")
        return

    # Step 6: Load CM scenes and calculate coverage
    scenes_gdf = load_cm_scenes()

    if len(scenes_gdf) > 0:
        # Match scenes to fields for coverage statistics
        field_coverage, coverage_stats = match_scenes_to_fields(
            scenes_gdf, fields_gdf, production_df
        )

        # Step 7: Create probability profile plots (new)
        prob_summary = create_probability_profile_plots(profile_df, coverage_stats, OUTPUT_DIR)
    else:
        print("WARNING: No scene data available, skipping probability plots")
        coverage_stats = {}
        prob_summary = {}

    # Step 8: Create original scatter plots (for reference)
    create_profile_plots(profile_df, OUTPUT_DIR)

    # Step 9: Save outputs
    print("\nSaving outputs...")
    save_outputs(matched_df, profile_df, OUTPUT_DIR)

    # Save probability summary
    if prob_summary:
        prob_summary_path = OUTPUT_DIR / f"probability_profile_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        # Convert any non-serializable values
        prob_summary_serializable = {}
        for k, v in prob_summary.items():
            if isinstance(v, dict):
                prob_summary_serializable[k] = {str(kk): float(vv) for kk, vv in v.items()}
            else:
                prob_summary_serializable[k] = float(v) if isinstance(v, (np.floating, np.integer)) else v

        # Add coverage stats
        prob_summary_serializable['coverage_stats'] = {
            k: float(v) if isinstance(v, (np.floating, np.integer)) else v
            for k, v in coverage_stats.items()
        }

        with open(prob_summary_path, 'w') as f:
            json.dump(prob_summary_serializable, f, indent=2)
        print(f"  Saved: {prob_summary_path.name}")

    print("\n" + "=" * 60)
    print("DONE!")
    print("=" * 60)


if __name__ == "__main__":
    main()
