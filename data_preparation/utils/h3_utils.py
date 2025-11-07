"""
H3 spatial indexing utilities for generating H3 indices from geometries.
"""

import h3
from shapely.geometry import shape, Point
from typing import Optional


def geojson_to_h3_index(geojson_geometry: dict, resolution: int = 8) -> Optional[str]:
    """
    Convert a GeoJSON geometry to an H3 index at the centroid.

    Args:
        geojson_geometry: GeoJSON geometry dict (Point, Polygon, MultiPolygon, etc.)
        resolution: H3 resolution level (default: 8, ~0.46 km² hexagons)

    Returns:
        H3 index as hex string, or None if conversion fails
    """
    try:
        geom = shape(geojson_geometry)
        centroid = geom.centroid
        return lat_lon_to_h3(centroid.y, centroid.x, resolution)
    except Exception as e:
        print(f"Error converting GeoJSON to H3: {e}")
        return None


def lat_lon_to_h3(lat: float, lon: float, resolution: int = 8) -> str:
    """
    Convert latitude/longitude to H3 index.

    Args:
        lat: Latitude in decimal degrees
        lon: Longitude in decimal degrees
        resolution: H3 resolution level (default: 8)

    Returns:
        H3 index as hex string
    """
    return h3.geo_to_h3(lat, lon, resolution)


def wkt_to_h3_index(wkt_geometry: str, resolution: int = 8) -> Optional[str]:
    """
    Convert a WKT geometry string to an H3 index at the centroid.

    Args:
        wkt_geometry: WKT geometry string
        resolution: H3 resolution level (default: 8)

    Returns:
        H3 index as hex string, or None if conversion fails
    """
    try:
        from shapely import wkt
        geom = wkt.loads(wkt_geometry)
        centroid = geom.centroid
        return lat_lon_to_h3(centroid.y, centroid.x, resolution)
    except Exception as e:
        print(f"Error converting WKT to H3: {e}")
        return None
