"""
This module contains the validator for the OPGEE schema.
"""
import logging
from typing import Dict, List, Any

from pyxis_app.postgres.models.pyxis_field import PyxisFieldMeta, PyxisFieldData


logger = logging.getLogger(__name__)


def validate_opgee_mappings(mappings: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Validate that target attributes in mappings exist in OPGEE schema.

    Args:
        mappings: List of mapping dictionaries with source_attribute and target_attribute

    Returns:
        Dict with validation result:
        {
            "valid": True/False,
            "errors": [list of error messages]
        }
    """
    errors = []

    try:
        # Get all valid OPGEE attributes
        valid_attrs = get_opgee_attributes()

        # Check each mapping
        for mapping in mappings:
            target_attr = mapping.get("target_attribute")
            if target_attr and target_attr not in valid_attrs:
                errors.append(
                    f"Target attribute '{target_attr}' is not a valid OPGEE attribute"
                )

    except Exception as e:
        errors.append(f"Error validating OPGEE mappings: {str(e)}")

    return {"valid": len(errors) == 0, "errors": errors}


def get_opgee_attributes() -> List[str]:
    """
    Get all OPCEE attributes by combining PyxisFieldMeta and PyxisFieldData attributes

    Returns:
        List of OPCEE attribute names
    """
    # Get attributes from both models
    meta_attrs = PyxisFieldMeta.get_pyxis_field_meta_attributes()
    data_attrs = PyxisFieldData.get_field_attributes()

    return meta_attrs + data_attrs
