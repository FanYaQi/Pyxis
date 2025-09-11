"""
Merge utilities for combining field data from multiple sources.
"""

import os
import json
import logging
from datetime import datetime, date
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


# Time-weighted merge functions
def calculate_time_overlap_days(record_start: Optional[date], record_end: Optional[date], 
                               query_start: date, query_end: date) -> int:
    """
    Calculate overlap in days between record validity and query period.
    
    Args:
        record_start: Start date of record validity (None means eternal start)
        record_end: End date of record validity (None means eternal end)
        query_start: Start date of query period
        query_end: End date of query period
        
    Returns:
        Number of overlapping days (0 if no overlap)
    """
    # Handle None dates (eternal validity)
    effective_start = record_start if record_start is not None else query_start
    effective_end = record_end if record_end is not None else query_end
    
    # Calculate overlap
    overlap_start = max(effective_start, query_start)
    overlap_end = min(effective_end, query_end)
    
    if overlap_start <= overlap_end:
        return (overlap_end - overlap_start).days + 1  # +1 to include both end dates
    else:
        return 0


def extract_values_with_time_weights(field_data_records, attr_name: str, 
                                   query_start: date, query_end: date, 
                                   is_dynamic: bool) -> List[Tuple[Any, float]]:
    """
    Extract values with time weights for dynamic attributes, or just values for static.
    
    Args:
        field_data_records: List of PyxisFieldData records
        attr_name: Name of the attribute to extract
        query_start: Start date of query period
        query_end: End date of query period
        is_dynamic: Whether the attribute is dynamic (time-sensitive)
        
    Returns:
        List of (value, weight) tuples
    """
    value_weight_pairs = []
    total_query_days = (query_end - query_start).days + 1
    
    for record in field_data_records:
        if not hasattr(record, attr_name):
            continue
            
        value = getattr(record, attr_name)
        if value is None:
            continue
        
        if is_dynamic:
            # For dynamic attributes, calculate time-based weight
            record_start = getattr(record, 'valid_from', None)
            record_end = getattr(record, 'valid_to', None)
            
            # Convert datetime to date if needed
            if isinstance(record_start, datetime):
                record_start = record_start.date()
            if isinstance(record_end, datetime):
                record_end = record_end.date()
            
            overlap_days = calculate_time_overlap_days(record_start, record_end, query_start, query_end)
            
            if overlap_days > 0:
                weight = overlap_days / total_query_days
                value_weight_pairs.append((value, weight))
        else:
            # For static attributes, all records have equal weight
            value_weight_pairs.append((value, 1.0))
    
    return value_weight_pairs


def time_weighted_average(value_weight_pairs: List[Tuple[float, float]]) -> Optional[float]:
    """
    Calculate time-weighted average: sum(value * weight) / sum(weights).
    
    Args:
        value_weight_pairs: List of (value, weight) tuples
        
    Returns:
        Time-weighted average or None if no valid values
    """
    if not value_weight_pairs:
        return None
    
    # Filter out None values and convert to numbers
    valid_pairs = []
    for value, weight in value_weight_pairs:
        if value is not None and weight > 0:
            try:
                valid_pairs.append((float(value), float(weight)))
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


def merge_time_weighted_average(value_weight_pairs: List[Tuple[Any, float]]) -> Optional[float]:
    """Calculate time-weighted average from value-weight pairs."""
    return time_weighted_average(value_weight_pairs)


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


def merge_avg_age(values: List[Any], query_year: int) -> Optional[int]:
    """
    Calculate average age using query_year - average(years).
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
    return int(query_year - avg_year)


# Function mapping
MERGE_FUNCTIONS = {
    "average": merge_average,
    "time_weighted_average": merge_time_weighted_average,
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


def extract_values_for_attribute(field_data_records, attr_name: str,
                                query_start: Optional[date] = None,
                                query_end: Optional[date] = None,
                                is_dynamic: bool = False) -> List[Any]:
    """
    Extract values for a specific attribute from field data records.
    
    Args:
        field_data_records: List of PyxisFieldData records
        attr_name: Name of the attribute to extract
        query_start: Start date for time filtering (for dynamic attributes)
        query_end: End date for time filtering (for dynamic attributes)
        is_dynamic: Whether to apply time filtering
    
    Returns:
        List of values for the attribute
    """
    if is_dynamic and query_start is not None and query_end is not None:
        # Use time-weighted extraction for dynamic attributes
        value_weight_pairs = extract_values_with_time_weights(
            field_data_records, attr_name, query_start, query_end, is_dynamic
        )
        return [value for value, weight in value_weight_pairs]
    else:
        # Use simple extraction for static attributes
        values = []
        for record in field_data_records:
            if hasattr(record, attr_name):
                value = getattr(record, attr_name)
                if value is not None:
                    values.append(value)
        return values


def process_attribute(field_data_records, attr_name: str, rule: Dict,
                     query_start: Optional[date] = None,
                     query_end: Optional[date] = None) -> Any:
    """
    Process a single attribute using the specified rule.
    
    Args:
        field_data_records: List of PyxisFieldData records
        attr_name: Name of the attribute to process
        rule: Rule dictionary from JSON
        query_start: Start date for time filtering
        query_end: End date for time filtering
    
    Returns:
        Merged value for the attribute
    """
    # Get method, special function, and attribute type from rule
    method = rule.get("method")
    special_function = rule.get("function")
    round_type = rule.get("round")
    attribute_type = rule.get("attribute_type", "static")  # Default to static
    is_dynamic = attribute_type == "dynamic"
    
    # Process based on method first, then special function
    if method == "average":
        if is_dynamic and query_start is not None and query_end is not None:
            # Use time-weighted average for dynamic attributes
            value_weight_pairs = extract_values_with_time_weights(
                field_data_records, attr_name, query_start, query_end, is_dynamic
            )
            result = time_weighted_average(value_weight_pairs)
        else:
            # Use regular average for static attributes
            values = extract_values_for_attribute(field_data_records, attr_name)
            result = merge_average(values)
            
    elif method == "most_frequent":
        # Most frequent doesn't need time weighting
        values = extract_values_for_attribute(field_data_records, attr_name)
        result = merge_most_frequent(values)
        
    else:
        logger.warning(f"Unknown merge method: {method} for attribute {attr_name}")
        values = extract_values_for_attribute(field_data_records, attr_name)
        result = values[0] if values else None
    
    # Apply special functions after basic processing
    if special_function == "volume_weighted":
        # First get time-weighted oil_prod values
        oil_prod_pairs = extract_values_with_time_weights(
            field_data_records, "oil_prod", query_start or date.today(), 
            query_end or date.today(), True
        ) if query_start and query_end else []
        
        if oil_prod_pairs:
            # Get time-weighted oil_prod values as weights
            oil_prod_weights = [weight for _, weight in oil_prod_pairs]
            oil_prod_values = [value for value, _ in oil_prod_pairs]
            
            # Get corresponding attribute values
            attr_pairs = extract_values_with_time_weights(
                field_data_records, attr_name, query_start, query_end, is_dynamic
            )
            attr_values = [value for value, _ in attr_pairs]
            
            if len(attr_values) == len(oil_prod_values):
                result = merge_volume_weighted_average(attr_values, oil_prod_values)
            else:
                logger.debug(f"Mismatched lengths for volume weighted average: {attr_name} "
                           f"(attr_values={len(attr_values)}, oil_prod_values={len(oil_prod_values)}), "
                           f"falling back to time-weighted average")
                result = time_weighted_average(attr_pairs) if attr_pairs else None
        else:
            # Fallback to regular average if no oil_prod data
            logger.debug(f"No oil_prod data for volume weighting {attr_name}, using regular average")
            values = extract_values_for_attribute(field_data_records, attr_name)
            result = merge_average(values)
            
    elif special_function == "avg_age":
        values = extract_values_for_attribute(field_data_records, attr_name)
        query_year = query_end.year if query_end else datetime.now().year
        result = merge_avg_age(values, query_year)
    
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
    attributes: List[str],
    query_start: Optional[date] = None,
    query_end: Optional[date] = None
) -> Dict[str, Any]:
    """
    Merge only the specified attributes from field data records using rules from JSON config.
    
    Args:
        field_data_records: List of PyxisFieldData records
        attributes: List of attribute names to merge (e.g., ['name', 'country', 'geometry'])
        query_start: Start date for time filtering
        query_end: End date for time filtering
    
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
                merged_value = process_attribute(field_data_records, attr, rule, query_start, query_end)
                if merged_value is not None:
                    merged_values[attr] = merged_value
            else:
                logger.warning(f"No merge rule found for attribute: {attr}")
                # Fallback to most frequent
                values = extract_values_for_attribute(field_data_records, attr)
                if values:
                    merged_values[attr] = merge_most_frequent(values)
    
    return merged_values


def merge_all_attributes(field_data_records,
                        query_start: Optional[date] = None,
                        query_end: Optional[date] = None) -> Dict[str, Any]:
    """
    Merge all attributes defined in OPGEE_cols_merge_rules.json.
    
    Args:
        field_data_records: List of PyxisFieldData records
        query_start: Start date for time filtering
        query_end: End date for time filtering
        
    Returns:
        Dict with merged values for all defined attributes
    """
    merged_values = {}
    merge_rules = load_merge_rules()
    
    # Process all attributes from the rules
    for attr_name, rule in merge_rules.items():
        merged_value = process_attribute(field_data_records, attr_name, rule, query_start, query_end)
        if merged_value is not None:
            merged_values[attr_name] = merged_value
    
    return merged_values