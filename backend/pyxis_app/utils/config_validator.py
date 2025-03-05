import json
import os
import jsonschema
from typing import Dict, Any, List, Optional

# Load the JSON schema for validation
SCHEMA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "configs",
    "data_schemas",
    "oil_field_data_config_v0.json",
)


def load_schema():
    """Load the JSON schema for validation"""
    with open(SCHEMA_PATH, "r") as file:
        return json.load(file)


def validate_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate the configuration against the JSON schema

    Args:
        config: Configuration dictionary to validate

    Returns:
        Dictionary with validation result:
        {
            "valid": True/False,
            "errors": [list of error messages]
        }
    """
    schema = load_schema()
    validator = jsonschema.Draft7Validator(schema)

    errors = list(validator.iter_errors(config))
    if errors:
        return {"valid": False, "errors": [str(error) for error in errors]}

    # Additional validation checks could be added here
    # For example, verifying that source attributes mentioned in mappings exist

    return {"valid": True, "errors": []}


def validate_mapping_against_data(
    config: Dict[str, Any], data_sample: Any
) -> Dict[str, Any]:
    """
    Validate that mappings in config exist in the data sample

    Args:
        config: Configuration dictionary containing mappings
        data_sample: Sample of the data to validate mappings against

    Returns:
        Dictionary with validation result
    """
    # This would be implemented based on the data format
    # For CSV, we'd check column names
    # For Shapefiles, we'd check attribute names
    # etc.

    # Placeholder implementation
    return {"valid": True, "errors": []}
