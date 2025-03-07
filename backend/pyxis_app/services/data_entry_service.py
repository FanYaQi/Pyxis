# backend/pyxis_app/services/data_entry_service.py
import io
import json
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Optional

import hashlib
import pandas as pd
from fastapi import BackgroundTasks, UploadFile
from pydantic import ValidationError
from sqlalchemy.orm import Session

from pyxis_app.postgres.models.pyxis_field import PyxisFieldMeta, PyxisFieldData
from pyxis_app.postgres.models.data_entry import (
    DataEntry,
    ProcessingStatus,
    FileExtension,
    DataGranularity,
)
from pyxis_app.validators.config_validator import validate_config
from pyxis_app.validators.data_validator import validate_data
from pyxis_app.validators.opgee_validator import validate_opgee_mappings
from pyxis_app.schemas.data_entry_config import DataEntryConfiguration
from pyxis_app.utils.data_type_utils import convert_value


logger = logging.getLogger(__name__)


async def validate_data_entry(
    db: Session,
    source_id: int,
    record_id: str,
    version: str,
    alias: str,
    granularity: DataGranularity,
    file_extension: FileExtension,
    data_file: UploadFile,
    config_file: UploadFile,
    additional_metadata: Optional[Dict[str, Any]] = None,
) -> DataEntry:
    """
    Process a data entry upload, validate files, and store in database.

    Args:
        db: Database session
        source_id: ID of the data source
        record_id: Unique identifier for the record
        version: Version of the data
        alias: Human-readable name for the data entry
        granularity: Level of data granularity
        file_extension: Type of data file
        data_file: The uploaded data file
        config_file: The uploaded config file
        additional_metadata: Additional metadata to store

    Returns:
        DataEntry: The created data entry

    Raises:
        ValueError: If validation fails
    """
    # Read files
    config_content = await config_file.read()
    data_content = await data_file.read()

    # Parse config
    try:
        config_dict = json.loads(config_content.decode("utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON config file: {str(e)}") from e

    # Validate config against schema
    config_model = validate_config(config_dict)

    # Validate OPGEE mappings
    opgee_validation = validate_opgee_mappings(config_model.mappings)
    if not opgee_validation["valid"]:
        error_messages = ", ".join(opgee_validation["errors"])
        raise ValueError(f"OPGEE mapping validation failed: {error_messages}")

    # Validate data against config
    data_validation = await validate_data(data_content, file_extension, config_model)
    if not data_validation["valid"]:
        error_messages = ", ".join(data_validation["errors"])
        raise ValueError(f"Data validation failed: {error_messages}")

    # Calculate MD5 hashes
    data_md5 = hashlib.md5(data_content).hexdigest()
    config_md5 = hashlib.md5(config_content).hexdigest()

    # Create new data entry
    data_entry = DataEntry(
        source_id=source_id,
        record_id=record_id,
        version=version,
        alias=alias,
        file_extension=file_extension,
        granularity=granularity,
        raw_data=data_content,
        raw_data_md5=data_md5,
        file_name=data_file.filename,
        file_size=len(data_content),
        config_file=config_dict,
        config_file_md5=config_md5,
        status=ProcessingStatus.PENDING,  # Set to PENDING by default
        additional_metadata=additional_metadata,
    )

    # Save to database
    db.add(data_entry)
    db.commit()
    db.refresh(data_entry)

    return data_entry


async def get_data_entry_status(data_entry_id: int, db: Session) -> Dict[str, Any]:
    """
    Get the status of a data entry.

    Args:
        data_entry_id: ID of the data entry
        db: Database session

    Returns:
        Dict with status:
        {
            "success": True/False,
            "data_entry_id": int,
            "status": ProcessingStatus,
            "error_message": Optional[str]
        }
    """
    data_entry = db.query(DataEntry).filter(DataEntry.id == data_entry_id).first()
    if not data_entry:
        return {
            "success": False,
            "message": f"Data entry with ID {data_entry_id} not found",
            "data_entry_id": data_entry_id,
            "status": None,
            "error_message": None,
        }

    return {
        "success": True,
        "data_entry_id": data_entry_id,
        "status": data_entry.status,
        "error_message": data_entry.error_message,
        "processed_fields_count": get_processed_fields_count(data_entry_id, db),
    }


async def trigger_data_processing(
    data_entry: DataEntry,
    background_tasks: BackgroundTasks,
    db: Session,
) -> Dict[str, Any]:
    """
    Trigger data processing for a data entry.

    Args:
        data_entry: Data entry object
        background_tasks: FastAPI background tasks
        db: Database session

    Returns:
        Dict with result:
        {
            "success": True/False,
            "message": str,
            "data_entry_id": int,
            "status": ProcessingStatus
        }
    """
    # Check if data entry is in PENDING state
    if (
        data_entry.status != ProcessingStatus.PENDING
        and data_entry.status != ProcessingStatus.FAILED
    ):
        return {
            "success": False,
            "message": f"Data entry with ID {data_entry.id} is not in PENDING state. Current state: {data_entry.status}",
            "data_entry_id": data_entry.id,
            "status": data_entry.status,
        }

    # Update status to PROCESSING
    data_entry.status = ProcessingStatus.PROCESSING
    db.add(data_entry)
    db.commit()

    # Add background task
    background_tasks.add_task(
        process_data_entry_background,
        data_entry,
        db,
    )

    return {
        "success": True,
        "message": f"Processing started for data entry with ID {data_entry.id}",
        "data_entry_id": data_entry.id,
        "status": ProcessingStatus.PROCESSING,
    }


# TODO: Integrate with logfire for monitoring background tasks
# TODO: Add monitoring for data entry processing
def process_data_entry_background(data_entry: DataEntry, db: Session) -> None:
    """
    Process a data entry in the background.

    Args:
        data_entry_id: ID of the data entry to process
    """
    db.add(data_entry)
    try:
        logger.info("Starting background processing for data entry %s", data_entry.id)

        # Process data based on file type
        if data_entry.file_extension == FileExtension.CSV:
            process_csv_data(data_entry, db)
        else:
            # Set error for unsupported file types
            data_entry.status = ProcessingStatus.FAILED
            data_entry.error_message = (
                f"Unsupported file extension: {data_entry.file_extension}"
            )
            logger.error("Unsupported file extension: %s", data_entry.file_extension)
            return

        # Update status to COMPLETED
        data_entry.status = ProcessingStatus.COMPLETED
        logger.info("Completed processing for data entry %s", data_entry.id)
    except Exception as e:
        # Handle processing errors
        data_entry.status = ProcessingStatus.FAILED
        data_entry.error_message = f"Processing error: {str(e)}"
        logger.exception("Error processing data entry %s: %s", data_entry.id, str(e))
        logger.exception("Unexpected error in background task: %s", str(e))
    finally:
        db.commit()


def process_csv_data(data_entry: DataEntry, db: Session) -> None:
    """
    Process CSV data and create Pyxis field data entries.

    Args:
        data_entry: Data entry object
        db: Database session
    """
    try:
        # Parse the config JSON to a Pydantic model
        config_model = DataEntryConfiguration.model_validate(data_entry.config_file)
    except ValidationError as e:
        raise ValueError(f"Failed to parse configuration: {str(e)}") from e

    mappings = config_model.mappings
    if not mappings:
        raise ValueError("No mappings found in config file")

    # Parse CSV data using configuration
    # TODO: Refactor this, default value should not be defined twice.
    csv_config = (
        config_model.file_specific.csv
        if config_model.file_specific and config_model.file_specific.csv
        else None
    )
    delimiter = csv_config.delimiter if csv_config and csv_config.delimiter else ","
    encoding = csv_config.encoding if csv_config and csv_config.encoding else "utf-8"
    header_row = (
        csv_config.header_row if csv_config and csv_config.header_row is not None else 0
    )

    # Read CSV into pandas DataFrame
    df = pd.read_csv(
        io.BytesIO(data_entry.raw_data),
        delimiter=delimiter,
        encoding=encoding,
        header=header_row,
    )

    # Process each row
    for _, row in df.iterrows():
        # Find or create PyxisFieldMeta
        field_meta = get_or_create_field_meta(row, config_model, db)
        # Create PyxisFieldData
        field_data = create_field_data(field_meta, row, config_model, data_entry)

        # TODO: think about the logic here.
        # field_data.pyxis_field_meta_id = field_meta.id
        field_data.data_entry_id = data_entry.id

        db.add_all([field_meta, field_data])
        db.flush()


def get_or_create_field_meta(
    row: pd.Series, config: DataEntryConfiguration, db: Session
) -> PyxisFieldMeta:
    """
    Find or create a PyxisFieldMeta record based on row data and
    add the field meta to the session. This method does not commit the session.

    Args:
        row: Pandas Series containing the row data
        config: Configuration Pydantic model
        db: Database session

    Returns:
        PyxisFieldMeta object
    """
    # Get spatial configuration
    # spatial_config = config.get("spatial_configuration", {})

    # Extract field name and country from the row if available
    field_name = None
    country = None

    # Find field name and country in mappings
    for mapping in config.mappings:
        source_attr = mapping.source_attribute
        target_attr = mapping.target_attribute

        # For each attribute in PyxisFieldMeta, check if the source attribute is present.
        # If it is, set the PyxisFieldMeta attribute to the value of the source attribute.
        if target_attr == "name" and source_attr in row:
            field_name = str(row[source_attr])
        elif target_attr == "country" and source_attr in row:
            country = str(row[source_attr])

    # Check if field already exists by name and country
    existing_field = None
    if field_name and country:
        existing_field = (
            db.query(PyxisFieldMeta)
            .filter(
                PyxisFieldMeta.name == field_name,
                PyxisFieldMeta.country == country,
            )
            .first()
        )

    if existing_field:
        return existing_field

    # Create new field meta
    # TODO: Add geometry if available
    # TODO: Calculate centroid_h3_index if available
    new_field = PyxisFieldMeta(
        pyxis_field_code=str(uuid.uuid4()),
        name=field_name,
        country=country,
        # Handle geometry if available
        # This is a simplification - actual geometry processing would be more complex
        centroid_h3_index=None,  # Would need to calculate this from geometry
    )

    return new_field

# TODO: Add match algorithm
def create_field_data(
    field_meta: PyxisFieldMeta,
    row: pd.Series,
    config: DataEntryConfiguration,
    data_entry: DataEntry,
) -> PyxisFieldData:
    """
    Create a PyxisFieldData record for a field.
    Add the field data to the session. This method does not commit the session.

    Args:
        field_meta: PyxisFieldMeta object
        row: Pandas Series containing the row data
        config: DataEntryConfiguration object
        data_entry: Data entry object

    Returns:
        PyxisFieldData object
    """
    # Create data dictionary with mapped attributes
    field_data_dict = {
        "pyxis_field_meta_id": field_meta.id,
        "data_entry_id": data_entry.id,
        "effective_start_date": datetime.now(),
    }

    # Process each mapped attribute
    source_attr_map = config.get_source_attribute_map()
    name_mapping = config.get_attribute_mapping()
    for source_attr_name, target_attr_name in name_mapping.items():
        if source_attr_name in row:
            # Get raw value from the row
            value = row[source_attr_name]

            # Skip if NA/None
            if pd.isna(value):
                continue

            # Convert value based on attribute type
            # This is a basic conversion - would need more sophisticated conversion
            # based on the attribute type and units
            source_attr_info = source_attr_map[source_attr_name]
            target_attr_info = PyxisFieldData.get_attribute_info_by_name(
                target_attr_name
            )
            field_data_dict[target_attr_name] = convert_value(
                value, source_attr_info, target_attr_info
            )

    # Create field data object
    field_data = PyxisFieldData(**field_data_dict)
    return field_data


def get_processed_fields_count(data_entry_id: int, db: Session) -> int:
    """
    Get the count of processed fields for a data entry.

    Args:
        data_entry_id: ID of the data entry
        db: Database session

    Returns:
        Number of processed fields
    """
    return (
        db.query(PyxisFieldData)
        .filter(PyxisFieldData.data_entry_id == data_entry_id)
        .count()
    )
