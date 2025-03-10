"""
Validate the configuration file for a data entry
"""

from typing import Dict, Any
import logging

from pydantic import ValidationError

from app.schemas.data_entry_config import DataEntryConfiguration


logger = logging.getLogger(__name__)


def validate_config(config: Dict[str, Any]) -> DataEntryConfiguration:
    """
    Validate the configuration using Pydantic model

    Args:
        config: Configuration dictionary to validate

    Returns:
        Pydantic model of the configuration
    """
    errors = []

    try:
        # Use the Pydantic model for validation
        config_model = DataEntryConfiguration(**config)

        # If we get here, validation passed
        return config_model

    except ValidationError as e:
        # Convert Pydantic validation errors to a list of error messages
        for error in e.errors():
            loc = " -> ".join(str(x) for x in error["loc"])
            msg = error["msg"]
            errors.append(f"{loc}: {msg}")
        raise ValidationError(f"Invalid config file: {errors}") from e
    except Exception as e:
        raise ValueError(f"Unexpected error validating config: {str(e)}") from e
