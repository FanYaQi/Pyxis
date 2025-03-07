from typing import Any
from datetime import datetime

from pyxis_app.configs.units import Q_
from pyxis_app.schemas.data_entry_config import Attribute, AttributeType


def convert_value(
    source_value: Any, source_attr: Attribute, target_attr: Attribute
) -> Any:
    """
    Convert a value to the appropriate type for a target attribute.

    Use pint to convert units and handle type conversions.

    Args:
        source_value: Value to convert
        source_attr: Source attribute
        target_attr: Target attribute

    Returns:
        Converted value.
    """
    # Handle None values
    if source_value is None:
        return None

    # First convert to the right type
    typed_value = _convert_to_type(source_value, source_attr.type)

    # If no units involved, just return the type-converted value
    if not source_attr.units or not target_attr.units:
        return _convert_to_type(typed_value, target_attr.type)

    # Handle unit conversion
    try:
        # Create a quantity with the source units
        quantity = Q_(typed_value, source_attr.units)

        # Convert to target units
        converted_quantity = quantity.to(target_attr.units)

        # Get the magnitude (value without units)
        result = converted_quantity.magnitude

        # Convert to the target type if needed
        return _convert_to_type(result, target_attr.type)
    except (ValueError, AttributeError, TypeError) as e:
        # Handle edge cases and unit conversion errors
        raise ValueError(
            f"Cannot convert '{source_value}' from {source_attr.units} to {target_attr.units}: {str(e)}"
        ) from e


def _convert_to_type(value: Any, target_type: "AttributeType") -> Any:
    """
    Convert a value to the specified attribute type.

    Args:
        value: Value to convert
        target_type: Target type to convert to

    Returns:
        Converted value
    """
    try:
        if target_type == AttributeType.string:
            return str(value)
        elif target_type == AttributeType.integer:
            return int(float(value))
        elif target_type == AttributeType.number:
            return float(value)
        elif target_type == AttributeType.boolean:
            if isinstance(value, str):
                return value.lower() in ("true", "yes", "y", "1")
            return bool(value)
        elif target_type == AttributeType.date:
            # Handle date conversion (assuming string input)
            if isinstance(value, str):
                return datetime.strptime(value, "%Y-%m-%d").date()
            return value  # Assume already converted
        elif target_type == AttributeType.datetime:
            # Handle datetime conversion (assuming string input)
            if isinstance(value, str):
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            return value  # Assume already converted
        elif target_type == AttributeType.geometry:
            # TODO: This is a special case and would likely need custom handling
            # For now, just return the value as is
            return value
        else:
            raise ValueError(f"Unsupported attribute type: {target_type}")
    except Exception as e:
        raise ValueError(
            f"Failed to convert '{value}' to {target_type}: {str(e)}"
        ) from e
