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
    
    # H3 resolution edge lengths in kilometers
    H3_EDGE_LENGTHS_KM = {
        0: 1281.256011,
        1: 483.0568391,
        2: 182.5129565,
        3: 68.97922179,
        4: 26.07175968,
        5: 9.854090990,
        6: 3.724532667,
        7: 1.406475763,
        8: 0.531414010,
        9: 0.200786148,
        10: 0.075863783,
        11: 0.028663897,
        12: 0.010830188,
        13: 0.004092010,
        14: 0.001546100,
        15: 0.000584169
    }

    @staticmethod
    def select_optimal_coarse_resolution(proximity_distance_km: float) -> int:
        """
        Select optimal coarse resolution for parent-cell H3 approach.
        
        The coarse resolution should be smaller than proximity_distance_km but not too small.
        We want the k-ring to be small (2-4 steps) for efficiency.
        
        Args:
            proximity_distance_km: Proximity distance in kilometers
            
        Returns:
            Optimal H3 resolution for parent cells
        """
        # Target: edge_length should be proximity_distance / 3 to 5
        # This gives us a k-ring of 2-4 which is efficient
        target_edge_length = proximity_distance_km / 4
        
        # Find the resolution with edge length closest to target
        best_resolution = 3  # Default fallback
        best_diff = float('inf')
        
        for resolution, edge_length in FlareUtils.H3_EDGE_LENGTHS_KM.items():
            if resolution > 8:  # Don't go too fine for parent cells
                break
                
            diff = abs(edge_length - target_edge_length)
            if diff < best_diff and edge_length <= proximity_distance_km:
                best_diff = diff
                best_resolution = resolution
        
        logger.debug(f"Proximity {proximity_distance_km}km -> coarse resolution {best_resolution} "
                    f"(edge: {FlareUtils.H3_EDGE_LENGTHS_KM[best_resolution]:.2f}km)")
        
        return best_resolution

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
    def get_h3_indices_hierarchical(
        center_h3: str, 
        distance_km: float, 
        target_resolution: int = 9,
        coarse_resolution: int = 5
    ) -> List[str]:
        """
        OPTIMIZED: Get H3 indices within distance using hierarchical approach.
        
        This method dramatically reduces the number of H3 indices by:
        1. Using a coarser resolution for the k-ring calculation
        2. Getting children of coarse hexagons at the target resolution
        3. Avoiding massive k-rings at fine resolutions
        
        Args:
            center_h3: Center H3 index at target resolution
            distance_km: Distance in kilometers
            target_resolution: Final resolution for returned indices (default: 9)
            coarse_resolution: Coarse resolution for k-ring calculation (default: 6)
            
        Returns:
            List of H3 indices at target_resolution within the distance
        """
        try:
            # Convert center to coarse resolution
            coarse_center = h3.h3_to_parent(center_h3, coarse_resolution)
            
            # Calculate k-ring at coarse resolution (much smaller k value)
            coarse_edge_length_km = h3.edge_length(coarse_resolution, unit='km')
            k_coarse = max(1, int(math.ceil(distance_km / coarse_edge_length_km)))
            
            logger.debug(f"Hierarchical H3: coarse_resolution={coarse_resolution}, k={k_coarse}, edge_length={coarse_edge_length_km:.2f}km")
            
            # Get k-ring at coarse resolution
            coarse_indices = h3.k_ring(coarse_center, k_coarse)
            
            logger.debug(f"Hierarchical H3: {len(coarse_indices)} coarse hexagons")
            
            # Get all children at target resolution
            fine_indices = []
            for coarse_h3 in coarse_indices:
                children = h3.h3_to_children(coarse_h3, target_resolution)
                fine_indices.extend(children)
            
            logger.debug(f"Hierarchical H3: {len(fine_indices)} fine hexagons at resolution {target_resolution}")
            
            return fine_indices
            
        except Exception as e:
            logger.error(f"Error in hierarchical H3 calculation for {center_h3}: {str(e)}")
            # Fallback to original method with reasonable limits
            return FlareUtils.get_h3_k_ring_for_distance(center_h3, min(distance_km, 50.0), target_resolution)

    @staticmethod
    def get_parent_cells_for_proximity(
        center_h3: str, 
        proximity_distance_km: float,
        target_resolution: int = 9
    ) -> List[str]:
        """
        ULTRA-OPTIMIZED: Get parent H3 cells for proximity search.
        
        This method:
        1. Selects optimal coarse resolution dynamically
        2. Returns only parent cells (not children)
        3. Designed for database querying with minimal indices
        
        Args:
            center_h3: Center H3 index at target resolution
            proximity_distance_km: Proximity distance in kilometers
            target_resolution: Original resolution of center_h3 (for parent conversion)
            
        Returns:
            List of parent H3 cells at coarse resolution
        """
        try:
            # Step 1: Select optimal coarse resolution
            coarse_resolution = FlareUtils.select_optimal_coarse_resolution(proximity_distance_km)
            
            # Step 2: Convert center to coarse resolution
            coarse_center = h3.h3_to_parent(center_h3, coarse_resolution)
            
            # Step 3: Calculate k-ring at coarse resolution
            coarse_edge_length_km = FlareUtils.H3_EDGE_LENGTHS_KM[coarse_resolution]
            k_coarse = max(1, int(math.ceil(proximity_distance_km / coarse_edge_length_km)))
            
            # Add small buffer to ensure coverage
            k_coarse += 1
            
            # Step 4: Get k-ring at coarse resolution
            parent_cells = list(h3.k_ring(coarse_center, k_coarse))
            
            logger.debug(f"Parent-cell approach: proximity={proximity_distance_km}km, "
                        f"coarse_res={coarse_resolution}, k={k_coarse}, "
                        f"parent_cells={len(parent_cells)}")
            
            return parent_cells
            
        except Exception as e:
            logger.error(f"Error in parent-cell H3 calculation for {center_h3}: {str(e)}")
            # Fallback: return small k-ring at resolution 3
            try:
                fallback_center = h3.h3_to_parent(center_h3, 3)
                return list(h3.k_ring(fallback_center, 3))
            except:
                return [h3.h3_to_parent(center_h3, 3)]

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
            if not shapely_geom.is_valid or shapely_geom.is_empty:
                return False

            # Check if coordinates are in valid WGS84 range
            # If not, it's likely projected coordinates with wrong SRID
            bounds = shapely_geom.bounds  # (minx, miny, maxx, maxy)
            min_lon, min_lat, max_lon, max_lat = bounds

            # Valid WGS84 ranges: lon [-180, 180], lat [-90, 90]
            if not (-180 <= min_lon <= 180 and -180 <= max_lon <= 180 and
                    -90 <= min_lat <= 90 and -90 <= max_lat <= 90):
                logger.warning(f"Geometry has invalid WGS84 coordinates: bounds={bounds}. "
                             f"Likely projected coordinates stored with wrong SRID.")
                return False

            return True

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