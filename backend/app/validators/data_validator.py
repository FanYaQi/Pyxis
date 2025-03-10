import io
from typing import Dict, Any

import pandas as pd

from app.postgres.models.data_entry import FileExtension
from app.schemas.data_entry_config import DataEntryConfiguration


async def validate_data(
    data_content: bytes, file_extension: FileExtension, config: DataEntryConfiguration
) -> Dict[str, Any]:
    """
    Validate data content against config specifications.

    Args:
        data_content: Raw data file content
        file_extension: Type of data file
        config: Configuration dictionary

    Returns:
        Dict with validation result:
        {
            "valid": True/False,
            "errors": [list of error messages],
            "metadata": {additional metadata}
        }
    """
    if file_extension == FileExtension.CSV:
        return validate_csv_data(data_content, config)
    else:
        return {
            "valid": False,
            "errors": [f"Unsupported file extension: {file_extension}"],
        }


def validate_csv_data(
    data_content: bytes, config: DataEntryConfiguration
) -> Dict[str, Any]:
    """
    Validate CSV data against config.

    Args:
        data_content: Raw CSV content
        config: Configuration dictionary

    Returns:
        Dict with validation result
    """
    errors = []
    metadata = {}

    try:
        # Get CSV specific config
        if not (config.file_specific and config.file_specific.csv):
            raise ValueError("CSV specific config is required")

        csv_config = config.file_specific.csv
        delimiter = csv_config.delimiter
        encoding = csv_config.encoding
        header_row = csv_config.header_row

        # Read CSV into pandas DataFrame
        df = pd.read_csv(
            io.BytesIO(data_content),
            delimiter=delimiter,
            encoding=encoding,
            header=header_row,
        )

        # Get mappings
        mappings = config.mappings
        source_attrs = [m.source_attribute for m in mappings]

        # Check if all mapped attributes exist in the data
        missing_attrs = [attr for attr in source_attrs if attr not in df.columns]
        if missing_attrs:
            errors.append(
                f"Missing source attributes in data: {', '.join(missing_attrs)}"
            )

        # Add metadata about the dataset
        metadata["row_count"] = len(df)
        metadata["column_count"] = len(df.columns)

    except Exception as e:
        errors.append(f"Error processing CSV: {str(e)}")

    return {"valid": len(errors) == 0, "errors": errors, "metadata": metadata}
