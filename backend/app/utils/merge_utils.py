"""
Merge utilities for combining field data from multiple sources.
"""

import os
import json
import logging
from datetime import datetime
from typing import List, Any, Optional, Tuple, Dict, Callable

import numpy as np
import h3
from shapely import wkt
from shapely.geometry import shape
from shapely.ops import unary_union
from geoalchemy2.shape import from_shape, to_shape

from app.utils.path_util import get_data_path


logger = logging.getLogger(__name__)

# Path to merge rules file
MERGE_RULES_PATH = get_data_path("../../backend/app/configs/data_schemas/OPGEE_cols_merge_rules.json")


# Core merge functions
def merge_average(values: List[Any]) -> Optional[float]:
    """Calculate average of numeric values."""
    if not values:
        return None
    
    # Filter out None values and convert to numbers
    numeric_values = []
    for v in values:
        if v is not None:
            try:
                numeric_values.append(float(v))
            except (ValueError, TypeError):
                continue
    
    if not numeric_values:
        return None
    
    return np.average(numeric_values)


def merge_most_frequent(values: List[Any]) -> Any:
    """Get the most frequently occurring value."""
    if not values:
        return None
    
    # Filter out None values
    non_null_values = [v for v in values if v is not None]
    if not non_null_values:
        return None
    
    # Return most frequent value
    return max(set(non_null_values), key=non_null_values.count)


def merge_volume_weighted_average(values: List[Any], weights: List[Any]) -> Optional[float]:
    """
    Calculate volume-weighted average using oil_prod as weights.
    weighted_avg = sum(value * weight) / sum(weights)
    """
    if not values or not weights or len(values) != len(weights):
        return None
    
    # Filter out None values and convert to numbers
    valid_pairs = []
    for v, w in zip(values, weights):
        if v is not None and w is not None:
            try:
                valid_pairs.append((float(v), float(w)))
            except (ValueError, TypeError):
                continue
    
    if not valid_pairs:
        return None
    
    # Calculate weighted average
    weighted_sum = sum(value * weight for value, weight in valid_pairs)
    total_weight = sum(weight for _, weight in valid_pairs)
    
    if total_weight == 0:
        return None
    
    return weighted_sum / total_weight


def merge_avg_age(values: List[Any]) -> Optional[int]:
    """
    Calculate average age using current year - average(years).
    """
    if not values:
        return None
    
    # Filter out None values and convert to numbers
    numeric_values = []
    for v in values:
        if v is not None:
            try:
                numeric_values.append(float(v))
            except (ValueError, TypeError):
                continue
    
    if not numeric_values:
        return None
    
    avg_year = np.average(numeric_values)
    current_year = datetime.now().year
    return int(current_year - avg_year)


# Function mapping
MERGE_FUNCTIONS = {
    "average": merge_average,
    "most_frequent": merge_most_frequent,
}

SPECIAL_FUNCTIONS = {
    "volume_weighted": merge_volume_weighted_average,
    "avg_age": merge_avg_age,
}


def load_merge_rules() -> Dict[str, Dict[str, Any]]:
    """
    Load merge rules from JSON file.
    
    Returns:
        Dict with rules structure from JSON
    """
    try:
        if os.path.exists(MERGE_RULES_PATH):
            with open(MERGE_RULES_PATH, "r") as f:
                data = json.load(f)
                return data.get("rules", {})
        else:
            logger.warning(f"Merge rules file not found: {MERGE_RULES_PATH}")
            return {}
    except Exception as e:
        logger.error(f"Error loading merge rules: {str(e)}")
        return {}


def apply_rounding(value: float, round_type: str) -> Any:
    """
    Apply rounding based on round_type.
    
    Args:
        value: Numeric value to round
        round_type: Type of rounding ("int", "integer", or None)
    
    Returns:
        Rounded value
    """
    if round_type in ["int", "integer"]:
        return int(value)
    return value


def extract_values_for_attribute(field_data_records, attr_name: str) -> List[Any]:
    """
    Extract values for a specific attribute from field data records.
    
    Args:
        field_data_records: List of PyxisFieldData records
        attr_name: Name of the attribute to extract
    
    Returns:
        List of values for the attribute
    """
    values = []
    for record in field_data_records:
        if hasattr(record, attr_name):
            value = getattr(record, attr_name)
            if value is not None:
                values.append(value)
    return values


def process_attribute(field_data_records, attr_name: str, rule: Dict) -> Any:
    """
    Process a single attribute using the specified rule.
    
    Args:
        field_data_records: List of PyxisFieldData records
        attr_name: Name of the attribute to process
        rule: Rule dictionary from JSON
    
    Returns:
        Merged value for the attribute
    """
    # Extract values for the attribute
    values = extract_values_for_attribute(field_data_records, attr_name)
    
    if not values:
        return None
    
    # Get method and special function from rule
    method = rule.get("method")
    special_function = rule.get("function")
    round_type = rule.get("round")
    
    # Process based on special function or method
    if special_function == "volume_weighted":
        # Extract oil_prod values as weights
        weights = extract_values_for_attribute(field_data_records, "oil_prod")
        if not weights or len(weights) != len(values):
            logger.warning(f"Cannot calculate volume weighted average for {attr_name}: missing or mismatched oil_prod values")
            # Fallback to regular average
            result = merge_average(values)
        else:
            result = merge_volume_weighted_average(values, weights)
    elif special_function == "avg_age":
        result = merge_avg_age(values)
    else:
        # Use standard merge function
        merge_func = MERGE_FUNCTIONS.get(method)
        if merge_func:
            result = merge_func(values)
        else:
            logger.warning(f"Unknown merge method: {method} for attribute {attr_name}")
            result = values[0] if values else None
    
    # Apply rounding if specified and result is numeric
    if result is not None and round_type and isinstance(result, (int, float)):
        result = apply_rounding(result, round_type)
    
    return result


def merge_geometry(geometries: List[Any]) -> Tuple[Optional[Any], Optional[str]]:
    """
    Merge geometries using union operation and calculate centroid H3 index.
    
    Args:
        geometries: List of geometry objects (WKT strings, WKBElement, or Shapely)
    
    Returns:
        Tuple of (merged_geometry, centroid_h3_index)
    """
    if not geometries:
        return None, None
    
    valid_geometries = []

    for geom in geometries:
        try:
            # Handle various geometry input types
            if geom is None:
                continue

            if isinstance(geom, str):
                if geom == "None" or not geom.strip():
                    continue
                shapely_geom = wkt.loads(geom)
            elif hasattr(geom, "__geo_interface__"):
                # Handle shapely or other geo-interface compatible objects
                shapely_geom = shape(geom.__geo_interface__)
            else:
                # Try to convert from other formats
                shapely_geom = to_shape(geom)

            valid_geometries.append(shapely_geom)
        except Exception as e:
            logger.warning(f"Error loading geometry: {str(e)}")

    if valid_geometries:
        try:
            # Union all geometries
            if len(valid_geometries) == 1:
                merged_geometry = valid_geometries[0]
            else:
                merged_geometry = unary_union(valid_geometries)
            
            # Calculate centroid and convert to H3
            centroid = merged_geometry.centroid
            centroid_h3_index = h3.geo_to_h3(centroid.y, centroid.x, resolution=9)
            
            # Convert back to WKBElement for database storage
            merged_wkb = from_shape(merged_geometry, srid=4326)
            
            return merged_wkb, centroid_h3_index
        except Exception as e:
            logger.error(f"Error merging geometries: {str(e)}")

    return None, None


def merge_specific_attributes(
    field_data_records, 
    attributes: List[str]
) -> Dict[str, Any]:
    """
    Merge only the specified attributes from field data records using rules from JSON config.
    
    Args:
        field_data_records: List of PyxisFieldData records
        attributes: List of attribute names to merge (e.g., ['name', 'country', 'geometry'])
    
    Returns:
        Dict with merged values for requested attributes only
    """
    merged_values = {}
    merge_rules = load_merge_rules()
    
    for attr in attributes:
        if attr == 'geometry':
            # Special handling for geometry
            geometries = extract_values_for_attribute(field_data_records, 'geometry')
            geometry, centroid_h3 = merge_geometry(geometries)
            if geometry is not None:
                merged_values['geometry'] = geometry
            if centroid_h3 is not None:
                merged_values['centroid_h3_index'] = centroid_h3
        else:
            # Use rules from JSON config
            rule = merge_rules.get(attr)
            if rule:
                merged_value = process_attribute(field_data_records, attr, rule)
                if merged_value is not None:
                    merged_values[attr] = merged_value
            else:
                logger.warning(f"No merge rule found for attribute: {attr}")
                # Fallback to most frequent
                values = extract_values_for_attribute(field_data_records, attr)
                if values:
                    merged_values[attr] = merge_most_frequent(values)
    
    return merged_values


def merge_all_attributes(field_data_records) -> Dict[str, Any]:
    """
    Merge all attributes defined in OPGEE_cols_merge_rules.json.
    
    Args:
        field_data_records: List of PyxisFieldData records
        
    Returns:
        Dict with merged values for all defined attributes
    """
    merged_values = {}
    merge_rules = load_merge_rules()
    
    # Process all attributes from the rules
    for attr_name, rule in merge_rules.items():
        merged_value = process_attribute(field_data_records, attr_name, rule)
        if merged_value is not None:
            merged_values[attr_name] = merged_value
    
    return merged_values