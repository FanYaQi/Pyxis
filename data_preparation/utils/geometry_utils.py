"""
Geometry conversion utilities for transforming between GeoJSON, WKT, and other formats.
"""

import json
from shapely.geometry import shape
from typing import Optional


def geojson_to_wkt(geojson_str: str) -> Optional[str]:
    """
    Convert a GeoJSON string to WKT format.

    Args:
        geojson_str: GeoJSON geometry as string (from CSV)

    Returns:
        WKT string, or None if conversion fails
    """
    try:
        geojson_dict = json.loads(geojson_str)
        geom = shape(geojson_dict)
        return geom.wkt
    except Exception as e:
        print(f"Error converting GeoJSON to WKT: {e}")
        return None


def validate_geometry(wkt_str: str) -> bool:
    """
    Validate a WKT geometry string.

    Args:
        wkt_str: WKT geometry string

    Returns:
        True if valid, False otherwise
    """
    try:
        from shapely import wkt
        geom = wkt.loads(wkt_str)
        return geom.is_valid
    except Exception:
        return False


def get_centroid_coords(wkt_str: str) -> Optional[tuple[float, float]]:
    """
    Get centroid coordinates (lat, lon) from a WKT geometry.

    Args:
        wkt_str: WKT geometry string

    Returns:
        Tuple of (latitude, longitude), or None if conversion fails
    """
    try:
        from shapely import wkt
        geom = wkt.loads(wkt_str)
        centroid = geom.centroid
        return (centroid.y, centroid.x)
    except Exception as e:
        print(f"Error getting centroid: {e}")
        return None
