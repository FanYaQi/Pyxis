"""
Fix Argentina field geometries with projected coordinates.

This script identifies geometries with coordinates outside valid WGS84 ranges
and converts them from projected coordinates (meters) to proper WGS84 lat/lon.

For Argentina fields, the likely projection is UTM Zone 20S or 21S.
"""

import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from geoalchemy2.shape import to_shape, from_shape
from shapely.ops import transform
import pyproj
from app.configs.settings import settings

def get_utm_zone_for_argentina_bounds(bounds):
    """
    Determine the most likely UTM zone for Argentina field based on bounds.

    Argentina spans approximately:
    - Longitude: -73.5° to -53.6° (spans zones 19, 20, 21)
    - Latitude: -55° to -21.8° (all southern hemisphere)

    Args:
        bounds: Tuple of (minx, miny, maxx, maxy) in projected coordinates

    Returns:
        EPSG code for the UTM zone
    """
    # Argentina is primarily in UTM zones 19S, 20S, and 21S
    # Zone 20S (EPSG:32720) covers -66° to -60°
    # Zone 21S (EPSG:32721) covers -60° to -54°

    # For projected coordinates in meters, we need to guess the zone
    # based on typical Argentina field locations

    # Most Argentina oil/gas fields are in:
    # - Neuquén Basin: ~-70° to -68° (Zone 19S)
    # - Austral Basin: ~-69° to -66° (Zone 19S/20S)
    # - Noroeste Basin: ~-65° to -63° (Zone 20S)

    # Use the x-coordinate (easting) to estimate zone
    minx, miny, maxx, maxy = bounds
    avg_x = (minx + maxx) / 2

    # UTM zones have eastings around 200,000 to 800,000
    # If values are in the hundreds of thousands to millions, likely UTM

    if avg_x < 0:
        # Negative values suggest these might actually be in a different projection
        # Default to zone 20S which covers central Argentina
        return 32720
    elif avg_x < 500000:
        # Low easting values suggest western zone (19S)
        return 32719
    elif avg_x < 700000:
        # Medium easting values suggest central zone (20S)
        return 32720
    else:
        # High easting values suggest eastern zone (21S)
        return 32721

def convert_projected_to_wgs84(geometry_wkb, source_epsg):
    """
    Convert a geometry from projected coordinates to WGS84.

    Args:
        geometry_wkb: WKBElement geometry
        source_epsg: Source EPSG code (e.g., 32720 for UTM 20S)

    Returns:
        WKT string in WGS84, or None if conversion fails
    """
    try:
        # Convert to Shapely geometry
        shapely_geom = to_shape(geometry_wkb)

        # Set up projection transformation
        source_crs = pyproj.CRS(f'EPSG:{source_epsg}')
        target_crs = pyproj.CRS('EPSG:4326')

        transformer = pyproj.Transformer.from_crs(source_crs, target_crs, always_xy=True)

        # Transform geometry
        transformed_geom = transform(transformer.transform, shapely_geom)

        # Verify result is in valid WGS84 range
        bounds = transformed_geom.bounds
        min_lon, min_lat, max_lon, max_lat = bounds

        if not (-180 <= min_lon <= 180 and -180 <= max_lon <= 180 and
                -90 <= min_lat <= 90 and -90 <= max_lat <= 90):
            print(f"    Warning: Converted geometry still outside WGS84 range: {bounds}")
            return None

        return transformed_geom.wkt

    except Exception as e:
        print(f"    Error converting geometry: {str(e)}")
        return None

def fix_argentina_geometries():
    """Fix all Argentina geometries with projected coordinates."""

    # Create database engine
    engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))

    with Session(engine) as session:
        # Find all Argentina fields with invalid geometries
        query = text("""
            SELECT
                id,
                name,
                ST_AsEWKB(geometry) as geometry_wkb,
                ST_SRID(geometry) as srid,
                ST_XMin(geometry) as min_x,
                ST_YMin(geometry) as min_y,
                ST_XMax(geometry) as max_x,
                ST_YMax(geometry) as max_y
            FROM pyxis_field_meta
            WHERE country = 'Argentina'
              AND geometry IS NOT NULL
              AND (
                  ST_XMin(geometry) < -180 OR ST_XMax(geometry) > 180 OR
                  ST_YMin(geometry) < -90 OR ST_YMax(geometry) > 90
              )
        """)

        result = session.execute(query)
        invalid_fields = result.fetchall()

        print(f"\nFound {len(invalid_fields)} Argentina fields with invalid geometries")

        if not invalid_fields:
            print("No fields to fix!")
            return

        # Group by estimated UTM zone
        zone_counts = {}
        conversions = []

        for field in invalid_fields:
            field_id = field.id
            name = field.name
            bounds = (field.min_x, field.min_y, field.max_x, field.max_y)

            # Estimate UTM zone
            utm_epsg = get_utm_zone_for_argentina_bounds(bounds)
            zone_counts[utm_epsg] = zone_counts.get(utm_epsg, 0) + 1

            # Convert geometry
            print(f"\nField {field_id}: {name}")
            print(f"  Original bounds: {bounds}")
            print(f"  Estimated UTM zone: EPSG:{utm_epsg}")

            converted_wkt = convert_projected_to_wgs84(field.geometry_wkb, utm_epsg)

            if converted_wkt:
                conversions.append((field_id, converted_wkt))
                print(f"  ✓ Converted successfully")
            else:
                print(f"  ✗ Conversion failed")

        print(f"\n\nSummary:")
        print(f"  Total invalid fields: {len(invalid_fields)}")
        print(f"  Successfully converted: {len(conversions)}")
        print(f"\n  UTM zone distribution:")
        for epsg, count in sorted(zone_counts.items()):
            zone_name = {32719: "19S", 32720: "20S", 32721: "21S"}.get(epsg, str(epsg))
            print(f"    Zone {zone_name} (EPSG:{epsg}): {count} fields")

        if not conversions:
            print("\nNo fields to update!")
            return

        # Ask for confirmation
        response = input(f"\n\nUpdate {len(conversions)} fields in the database? (yes/no): ")
        if response.lower() != 'yes':
            print("Aborted.")
            return

        # Update geometries
        print("\nUpdating geometries...")
        for field_id, wkt in conversions:
            update_query = text("""
                UPDATE pyxis_field_meta
                SET geometry = ST_SetSRID(ST_GeomFromText(:wkt), 4326)
                WHERE id = :field_id
            """)
            session.execute(update_query, {"wkt": wkt, "field_id": field_id})

        session.commit()
        print(f"✓ Updated {len(conversions)} fields successfully!")

        # Verify results
        verify_query = text("""
            SELECT COUNT(*) as remaining_invalid
            FROM pyxis_field_meta
            WHERE country = 'Argentina'
              AND geometry IS NOT NULL
              AND (
                  ST_XMin(geometry) < -180 OR ST_XMax(geometry) > 180 OR
                  ST_YMin(geometry) < -90 OR ST_YMax(geometry) > 90
              )
        """)
        result = session.execute(verify_query)
        remaining = result.fetchone().remaining_invalid

        print(f"\nVerification: {remaining} invalid geometries remaining")

if __name__ == "__main__":
    print("=" * 70)
    print("Argentina Geometry Fix Script")
    print("=" * 70)
    fix_argentina_geometries()
    print("\n" + "=" * 70)
    print("Done!")
    print("=" * 70)
