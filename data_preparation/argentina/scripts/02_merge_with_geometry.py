"""
Script 2: Merge Field Production with Geometry Data

Takes field-level production data and merges with field geometry/metadata.

Input:
    - argentina/output/field_monthly_production.csv
    - argentina/raw/AR_field_shape_cleaned.csv

Output:
    - argentina/output/field_production_with_geometry.csv

Processing:
    - Join production data with field shapes on field_id
    - Convert GeoJSON geometry to WKT format
    - Generate H3 centroid index
    - Add spatial metadata
"""

import sys
from pathlib import Path

# Add utils to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
from utils.geometry_utils import geojson_to_wkt, get_centroid_coords
from utils.h3_utils import geojson_to_h3_index, lat_lon_to_h3
import json


def merge_with_geometry(
    production_csv: Path,
    geometry_csv: Path,
    output_csv: Path,
) -> None:
    """
    Merge field production data with geometry data.

    Args:
        production_csv: Path to field aggregated production CSV
        geometry_csv: Path to field geometry CSV
        output_csv: Path for output merged CSV
    """
    print(f"Reading production data from: {production_csv}")
    prod_df = pd.read_csv(production_csv)

    print(f"Reading geometry data from: {geometry_csv}")
    geom_df = pd.read_csv(geometry_csv)

    print(f"\nProduction data shape: {prod_df.shape}")
    print(f"Geometry data shape: {geom_df.shape}")

    # Merge on field_id
    print("\nMerging datasets on field_id...")
    merged = prod_df.merge(
        geom_df[['field_id', 'geometry', 'avg_depth_m', 'operating_company', 'operating_company_id']],
        on='field_id',
        how='left'
    )

    print(f"Merged data shape: {merged.shape}")
    print(f"Fields with geometry: {merged['geometry'].notna().sum()} / {len(merged)}")

    # Convert GeoJSON to WKT
    print("\nConverting GeoJSON to WKT format...")
    merged['geometry_wkt'] = merged['geometry'].apply(
        lambda x: geojson_to_wkt(x) if pd.notna(x) else None
    )

    # Generate H3 index from geometry centroid
    print("Generating H3 indices from geometry centroids...")
    merged['centroid_h3_index'] = merged['geometry'].apply(
        lambda x: geojson_to_h3_index(json.loads(x), resolution=8) if pd.notna(x) else None
    )

    # Extract centroid coordinates
    print("Extracting centroid coordinates...")
    merged['centroid_coords'] = merged['geometry_wkt'].apply(
        lambda x: get_centroid_coords(x) if pd.notna(x) else None
    )

    merged['latitude'] = merged['centroid_coords'].apply(
        lambda x: x[0] if x is not None else None
    )
    merged['longitude'] = merged['centroid_coords'].apply(
        lambda x: x[1] if x is not None else None
    )

    # Drop temporary columns
    merged = merged.drop(columns=['geometry', 'centroid_coords'])

    # Rename geometry_wkt to geometry for Pyxis compatibility
    merged = merged.rename(columns={'geometry_wkt': 'geometry'})

    # Use avg_depth_m from geometry if available, otherwise use aggregated depth_m
    merged['depth_m'] = merged['avg_depth_m'].fillna(merged['depth_m'])
    merged = merged.drop(columns=['avg_depth_m'])

    print(f"\nFinal merged data shape: {merged.shape}")
    print(f"Fields with H3 index: {merged['centroid_h3_index'].notna().sum()}")
    print(f"Fields with coordinates: {merged['latitude'].notna().sum()}")

    # Save output
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(output_csv, index=False, encoding='utf-8')
    print(f"\n✅ Merged data saved to: {output_csv}")


if __name__ == "__main__":
    # Define paths
    base_dir = Path(__file__).parent.parent
    production_file = base_dir / "output" / "field_monthly_production.csv"
    geometry_file = base_dir / "raw" / "AR_field_shape_cleaned.csv"
    output_file = base_dir / "output" / "field_production_with_geometry.csv"

    if not production_file.exists():
        print(f"❌ Error: Production file not found: {production_file}")
        print("Please run 01_aggregate_wells_to_fields.py first")
        sys.exit(1)

    if not geometry_file.exists():
        print(f"❌ Error: Geometry file not found: {geometry_file}")
        print("Please place your field shape CSV in argentina/raw/")
        sys.exit(1)

    merge_with_geometry(production_file, geometry_file, output_file)
