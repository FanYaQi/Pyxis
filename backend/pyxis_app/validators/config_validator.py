"""
Validate the configuration file for a data entry
"""
from typing import Dict, Any
import logging

from pydantic import ValidationError

from pyxis_app.schemas.data_entry_config import DataEntryConfiguration


logger = logging.getLogger(__name__)


def validate_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate the configuration using Pydantic model

    Args:
        config: Configuration dictionary to validate

    Returns:
        Dictionary with validation result:
        {
            "valid": True/False,
            "errors": [list of error messages]
        }
    """
    errors = []

    try:
        # Use the Pydantic model for validation
        DataEntryConfiguration(**config)

        # If we get here, validation passed
        return {"valid": True, "errors": []}

    except ValidationError as e:
        # Convert Pydantic validation errors to a list of error messages
        for error in e.errors():
            loc = " -> ".join(str(x) for x in error["loc"])
            msg = error["msg"]
            errors.append(f"{loc}: {msg}")

    except Exception as e:
        errors.append(f"Unexpected error validating config: {str(e)}")

    return {"valid": False, "errors": errors}
