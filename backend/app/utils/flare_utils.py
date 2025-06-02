"""
Utility functions for flare spatial operations and H3 calculations.
"""

import logging
from typing import List, Set, Dict, Tuple, Optional
import math

import h3
from shapely.geometry import Point, Polygon
from shapely.ops import transform
from shapely import wkt
from geoalchemy2.types import WKBElement
from geoalchemy2.shape import to_shape
from geoalchemy2 import WKTElement
import pyproj
from functools import partial


logger = logging.getLogger(__name__)


class FlareUtils:
    """Utility class for flare-related spatial operations"""

    @staticmethod
    def get_h3_k_ring_for_distance(
        center_h3: str, 
        distance_km: float, 
        resolution: int = 9
    ) -> List[str]:
        """
        Get H3 indices within a given distance using k-ring approximation.
        
        Args:
            center_h3: Center H3 index
            distance_km: Distance in kilometers
            resolution: H3 resolution level
            
        Returns:
            List of H3 indices within the distance
        """
        try:
            # Calculate approximate k value for the distance
            # Use H3's average edge length for the resolution
            h3_edge_length_km = h3.edge_length(resolution, unit='km')
            k = max(1, int(math.ceil(distance_km / h3_edge_length_km)))
            
            # Get k-ring (all hexagons within k steps)
            k_ring_indices = h3.k_ring(center_h3, k)
            
            return list(k_ring_indices)
            
        except Exception as e:
            logger.error(f"Error calculating H3 k-ring for {center_h3}: {str(e)}")
            return [center_h3]  # Return at least the center if calculation fails

    @staticmethod
    def point_in_geometry(lat: float, lon: float, geometry: WKBElement) -> bool:
        """
        Check if a point (lat, lon) is within a geometry.
        
        Args:
            lat: Latitude of the point
            lon: Longitude of the point
            geometry: PostGIS geometry (WKBElement)
            
        Returns:
            True if point is within geometry, False otherwise
        """
        try:
            # Convert WKBElement to Shapely geometry
            shapely_geom = to_shape(geometry)
            point = Point(lon, lat)  # Note: Shapely uses (x, y) = (lon, lat)
            
            return shapely_geom.contains(point)
            
        except Exception as e:
            logger.error(f"Error checking point ({lat}, {lon}) in geometry: {str(e)}")
            return False

    @staticmethod
    def create_buffer_geometry(geometry: WKBElement, buffer_km: float) -> Optional[WKTElement]:
        """
        Create a buffer around a geometry.
        
        Args:
            geometry: Original PostGIS geometry
            buffer_km: Buffer distance in kilometers
            
        Returns:
            Buffered geometry as WKTElement, or None if error
        """
        try:
            # Convert to Shapely geometry
            shapely_geom = to_shape(geometry)
            
            # Get a representative point for projection
            centroid = shapely_geom.centroid
            center_lat, center_lon = centroid.y, centroid.x
            
            # Create UTM projection for accurate distance-based buffering
            utm_crs = FlareUtils._get_utm_crs(center_lat, center_lon)
            
            # Set up transformations
            wgs84 = pyproj.CRS('EPSG:4326')
            utm = pyproj.CRS(utm_crs)
            
            project_to_utm = pyproj.Transformer.from_crs(wgs84, utm, always_xy=True).transform
            project_to_wgs84 = pyproj.Transformer.from_crs(utm, wgs84, always_xy=True).transform
            
            # Transform to UTM, buffer, then transform back
            utm_geom = transform(project_to_utm, shapely_geom)
            buffered_utm = utm_geom.buffer(buffer_km * 1000)  # Convert km to meters
            buffered_wgs84 = transform(project_to_wgs84, buffered_utm)
            
            # Convert back to WKTElement
            return WKTElement(buffered_wgs84.wkt, srid=4326)
            
        except Exception as e:
            logger.error(f"Error creating buffer geometry: {str(e)}")
            return None

    @staticmethod
    def point_in_buffer_geometry(lat: float, lon: float, buffered_geometry: WKTElement) -> bool:
        """
        Check if a point is within a buffered geometry.
        
        Args:
            lat: Latitude of the point
            lon: Longitude of the point
            buffered_geometry: Buffered geometry as WKTElement
            
        Returns:
            True if point is within buffered geometry, False otherwise
        """
        try:
            # Convert WKTElement to Shapely geometry
            geom_wkt = str(buffered_geometry)
            shapely_geom = wkt.loads(geom_wkt)
            point = Point(lon, lat)  # Shapely uses (x, y) = (lon, lat)
            
            return shapely_geom.contains(point)
            
        except Exception as e:
            logger.error(f"Error checking point ({lat}, {lon}) in buffer geometry: {str(e)}")
            return False

    @staticmethod
    def _get_utm_crs(lat: float, lon: float) -> str:
        """
        Get the appropriate UTM CRS for a given latitude/longitude.
        
        Args:
            lat: Latitude
            lon: Longitude
            
        Returns:
            UTM CRS string (e.g., 'EPSG:32633')
        """
        # Calculate UTM zone
        utm_zone = int((lon + 180) / 6) + 1
        
        # Determine hemisphere
        if lat >= 0:
            # Northern hemisphere
            epsg_code = 32600 + utm_zone
        else:
            # Southern hemisphere
            epsg_code = 32700 + utm_zone
        
        return f'EPSG:{epsg_code}'

    @staticmethod
    def calculate_flare_overlaps(flares: List) -> Dict[str, Set[str]]:
        """
        Calculate overlapping flares based on proximity.
        
        Args:
            flares: List of Flare objects
            
        Returns:
            Dict mapping flare_id to set of overlapping flare_ids
        """
        overlaps = {}
        overlap_threshold_km = 1.0  # 1km threshold for considering flares as overlapping
        
        for i, flare1 in enumerate(flares):
            overlapping_flares = set()
            
            for j, flare2 in enumerate(flares):
                if i != j:  # Don't compare flare with itself
                    distance = FlareUtils.haversine_distance(
                        flare1.latitude, flare1.longitude,
                        flare2.latitude, flare2.longitude
                    )
                    
                    if distance <= overlap_threshold_km:
                        overlapping_flares.add(flare2.flare_id)
            
            overlaps[flare1.flare_id] = overlapping_flares
        
        return overlaps

    @staticmethod
    def resolve_volume_allocation(
        overlapping_flares: Dict[str, Set[str]], 
        field_production_weights: Dict[int, float] = None
    ) -> Dict[str, Dict[int, float]]:
        """
        Resolve volume allocation for overlapping flares between multiple fields.
        
        Args:
            overlapping_flares: Dict of flare_id -> set of overlapping flare_ids
            field_production_weights: Optional dict of field_id -> production weight
            
        Returns:
            Dict mapping flare_id -> {field_id: allocation_fraction}
        """
        allocation_results = {}
        
        # For now, implement simple equal allocation
        # Can be enhanced with distance-based or production-based weighting
        for flare_id, overlapping_ids in overlapping_flares.items():
            if overlapping_ids:
                # If there are overlaps, split equally
                num_overlaps = len(overlapping_ids) + 1  # +1 for the flare itself
                allocation_fraction = 1.0 / num_overlaps
                allocation_results[flare_id] = {'default_field': allocation_fraction}
            else:
                # No overlaps, full allocation
                allocation_results[flare_id] = {'default_field': 1.0}
        
        return allocation_results

    @staticmethod
    def validate_geometry(geometry: WKBElement) -> bool:
        """
        Validate that a geometry is valid and usable.
        
        Args:
            geometry: PostGIS geometry to validate
            
        Returns:
            True if geometry is valid, False otherwise
        """
        try:
            if not geometry:
                return False
                
            # Convert to Shapely and check validity
            shapely_geom = to_shape(geometry)
            return shapely_geom.is_valid and not shapely_geom.is_empty
            
        except Exception as e:
            logger.error(f"Error validating geometry: {str(e)}")
            return False

    @staticmethod
    def get_geometry_centroid(geometry: WKBElement) -> Optional[Tuple[float, float]]:
        """
        Get the centroid of a geometry.
        
        Args:
            geometry: PostGIS geometry
            
        Returns:
            Tuple of (latitude, longitude) or None if error
        """
        try:
            shapely_geom = to_shape(geometry)
            centroid = shapely_geom.centroid
            return (centroid.y, centroid.x)  # (lat, lon)
            
        except Exception as e:
            logger.error(f"Error getting geometry centroid: {str(e)}")
            return None

    @staticmethod
    def geometry_area_km2(geometry: WKBElement) -> Optional[float]:
        """
        Calculate the area of a geometry in square kilometers.
        
        Args:
            geometry: PostGIS geometry
            
        Returns:
            Area in square kilometers, or None if error
        """
        try:
            shapely_geom = to_shape(geometry)
            
            # Get centroid for UTM projection
            centroid = shapely_geom.centroid
            center_lat, center_lon = centroid.y, centroid.x
            
            # Project to UTM for accurate area calculation
            utm_crs = FlareUtils._get_utm_crs(center_lat, center_lon)
            wgs84 = pyproj.CRS('EPSG:4326')
            utm = pyproj.CRS(utm_crs)
            
            project_to_utm = pyproj.Transformer.from_crs(wgs84, utm, always_xy=True).transform
            utm_geom = transform(project_to_utm, shapely_geom)
            
            # Calculate area in square meters, convert to square kilometers
            area_m2 = utm_geom.area
            area_km2 = area_m2 / 1_000_000
            
            return area_km2
            
        except Exception as e:
            logger.error(f"Error calculating geometry area: {str(e)}")
            return None