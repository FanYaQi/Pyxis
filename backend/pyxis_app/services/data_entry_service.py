# backend/pyxis_app/services/data_entry_service.py
import hashlib
import json
from typing import Dict, Any, Optional
from fastapi import UploadFile
from sqlalchemy.orm import Session

from pyxis_app.postgres.models.data_entry import (
    DataEntry,
    ProcessingStatus,
    FileExtension,
    DataGranularity,
)
from pyxis_app.validators.config_validator import validate_config
from pyxis_app.validators.data_validator import validate_data
from pyxis_app.validators.opgee_validator import validate_opgee_mappings


async def process_data_entry(
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
    config_validation = validate_config(config_dict)
    if not config_validation["valid"]:
        error_messages = ", ".join(config_validation["errors"])
        raise ValueError(f"Config validation failed: {error_messages}")

    # Validate OPGEE mappings
    opgee_validation = validate_opgee_mappings(config_dict.get("mappings", []))
    if not opgee_validation["valid"]:
        error_messages = ", ".join(opgee_validation["errors"])
        raise ValueError(f"OPGEE mapping validation failed: {error_messages}")

    # Validate data against config
    data_validation = await validate_data(data_content, file_extension, config_dict)
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
