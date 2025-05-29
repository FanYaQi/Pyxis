import io
import json
import logging
import hashlib
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple

import logfire
import pandas as pd
from fuzzywuzzy import fuzz
import h3
from fastapi import BackgroundTasks, UploadFile
from pydantic import ValidationError
from sqlalchemy.orm import Session
from geoalchemy2.shape import to_shape

from app.postgres.models.pyxis_field import PyxisFieldMeta, PyxisFieldData, PyxisFieldH3
from app.postgres.models.data_entry import (
    DataEntry,
    ProcessingStatus,
    FileExtension,
    DataGranularity,
)
from app.validators.config_validator import validate_config
from app.validators.data_validator import validate_data
from app.validators.opgee_validator import validate_opgee_mappings
from app.schemas.data_entry_config import DataEntryConfiguration
from app.utils.data_type_utils import convert_value
from app.utils.merge_utils import merge_specific_attributes


logger = logging.getLogger(__name__)

# Matching threshold score - fields with score >= this will be considered matches
MATCH_SCORE_THRESHOLD = 60
# Weights for name and location in match score calculation [name_weight, geo_weight]
MATCH_WEIGHTS = [0.7, 0.3]


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


def update_field_h3_indices(db: Session, field_meta, resolution: int = 9):
    """
    Update H3 indices for a field when its geometry changes.
    """
    logger.info(f"Updating H3 indices for field {field_meta.id}")
    
    # Check if geometry exists
    if not field_meta.geometry:
        return
    
    try:
        # Convert to Shapely geometry
        shapely_geom = to_shape(field_meta.geometry)
        geom_type = type(shapely_geom).__name__
        
        # Collect all H3 indices from all polygons
        all_h3_indices = set()
        
        if geom_type == 'Polygon':
            geojson = {
                "type": "Polygon",
                "coordinates": [list(shapely_geom.exterior.coords)]
            }
            h3_indices = h3.polyfill(geojson, resolution)
            all_h3_indices.update(h3_indices)
            
        elif geom_type == 'MultiPolygon':
            # Process each polygon in the MultiPolygon
            for polygon in shapely_geom.geoms:
                geojson = {
                    "type": "Polygon",
                    "coordinates": [list(polygon.exterior.coords)]
                }
                h3_indices = h3.polyfill(geojson, resolution)
                all_h3_indices.update(h3_indices)
        else:
            logger.error(f"Field {field_meta.id} unsupported geometry type: {geom_type}")
            return
        
        if not all_h3_indices:
            return
        
        # Update database: remove old indices and add new ones
        db.query(PyxisFieldH3).filter(
            PyxisFieldH3.pyxis_field_meta_id == field_meta.id
        ).delete()
        
        # Bulk insert new H3 indices
        h3_records = [
            PyxisFieldH3(pyxis_field_meta_id=field_meta.id, h3_index=h3_index)
            for h3_index in all_h3_indices
        ]
        db.add_all(h3_records)
        logger.info(f"Added {len(h3_records)} H3 indices for field {field_meta.id}")
        
    except Exception as e:
        logger.error(f"Failed to update H3 indices for field {field_meta.id}: {str(e)}")


def calculate_match_score(
    name1: Optional[str],
    name2: Optional[str],
    index1: Optional[str],
    index2: Optional[str],
    weights: List[float] = MATCH_WEIGHTS,
) -> float:
    """
    Calculate match score based on name similarity and H3 distance.

    Args:
        name1: Name of the first field
        name2: Name of the second field
        index1: H3 index of the first field
        index2: H3 index of the second field
        weights: Weights for name score and geo score [name_weight, geo_weight]

    Returns:
        float: Match score between 0 and 100
    """
    # Calculate name similarity score
    if name1 is not None and name2 is not None:
        name_score = fuzz.ratio(str(name1).lower(), str(name2).lower())
    else:
        name_score = 0

    # Calculate geographical distance score
    if index1 is not None and index2 is not None:
        try:
            grid_distance = h3.h3_distance(index1, index2)
            if grid_distance < 50:
                # Normalize distance to a score using Gaussian distribution
                import numpy as np
                geo_score = 100 * np.exp(-0.5 * np.power(grid_distance * 0.1, 2))
            else:
                geo_score = -40
        except ValueError:
            # Handle cases where distance cannot be computed (too far away)
            geo_score = -40
    else:
        geo_score = 0

    # Combine scores using weights
    return weights[0] * name_score + weights[1] * geo_score


def find_matching_field(
    field_name: Optional[str],
    field_country: Optional[str],
    centroid_h3_index: Optional[str],
    db: Session,
) -> Tuple[Optional[PyxisFieldMeta], float]:
    """
    Find a matching PyxisFieldMeta based on name and location.

    Args:
        field_name: Name of the field to match
        field_country: Country of the field
        centroid_h3_index: H3 index of the field
        db: Database session

    Returns:
        Tuple of (matching_field, match_score) or (None, 0) if no match found
    """
    if not field_name:
        return None, 0

    # Query for potential matches - filter by country if available to reduce candidates
    query = db.query(PyxisFieldMeta)
    if field_country:
        query = query.filter(PyxisFieldMeta.country == field_country)

    potential_matches = query.all()

    best_match = None
    best_score = 0

    # Calculate match scores for each potential match
    for field in potential_matches:
        score = calculate_match_score(
            field_name, field.name, centroid_h3_index, field.centroid_h3_index
        )

        if score > best_score:
            best_score = score
            best_match = field

    # Return the best match if it meets the threshold
    if best_match and best_score >= MATCH_SCORE_THRESHOLD:
        return best_match, best_score

    return None, best_score


@logfire.instrument("Background data processing task for data entry {data_entry=}")
def process_data_entry_background(data_entry: DataEntry, db: Session) -> None:
    """
    Process a data entry in the background.

    Args:
        data_entry: The data entry to process
        db: Database session
    """
    db.add(data_entry)
    try:
        logger.info("Starting background processing for data entry %s", data_entry.id)

        # Process data based on file type
        with logfire.span(f"Process data for type {data_entry.file_extension}"):
            if data_entry.file_extension == FileExtension.CSV:
                process_csv_data(data_entry, db)
            else:
                # Set error for unsupported file types
                data_entry.status = ProcessingStatus.FAILED
                data_entry.error_message = (
                    f"Unsupported file extension: {data_entry.file_extension}"
                )
                logger.error(
                    "Unsupported file extension: %s", data_entry.file_extension
                )
                return

        # Update status to COMPLETED
        data_entry.status = ProcessingStatus.COMPLETED
        logger.info("Completed processing for data entry %s", data_entry.id)
    except Exception as e:
        # Handle processing errors
        data_entry.status = ProcessingStatus.FAILED
        data_entry.error_message = f"Processing error: {str(e)}"
        logger.exception("Error processing data entry %s: %s", data_entry.id, str(e))
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

    # Track field metas that need to be merged
    field_metas_to_merge = set()

    # Process each row in the CSV
    for _, row in df.iterrows():
        # Extract mapped data from the row
        field_attrs = extract_field_attributes(row, config_model)

        # Find or create a PyxisFieldMeta record (without H3 update)
        field_meta, is_new = get_or_create_field_meta(field_attrs, db)

        # Create a PyxisFieldData record
        field_data = create_field_data(field_meta, field_attrs, data_entry)
        db.add(field_data)

        # Track this field meta for merging
        field_metas_to_merge.add(field_meta.id)

    # Flush to assign IDs to field data
    db.flush()

    # Now merge and update H3 indices for all affected field metas
    for field_meta_id in field_metas_to_merge:
        update_pyxis_field_meta_merge(field_meta_id, db)

    # Commit all changes
    db.commit()


def extract_field_attributes(
    row: pd.Series, config: DataEntryConfiguration
) -> Dict[str, Any]:
    """
    Extract field attributes from a CSV row based on mappings.

    Args:
        row: Pandas Series row from CSV
        config: DataEntryConfiguration with mappings

    Returns:
        Dictionary of field attributes with target attribute names as keys
    """
    field_attrs = {}

    # Process each mapping
    for mapping in config.mappings:
        source_attr = mapping.source_attribute
        target_attr = mapping.target_attribute

        # Map source attribute to target attribute if value exists
        if source_attr in row and pd.notna(row[source_attr]):
            source_attr_info = config.get_source_attribute_map().get(source_attr)

            if source_attr_info:
                try:
                    # Get attribute info for proper type conversion
                    target_attr_info = PyxisFieldData.get_attribute_info_by_name(
                        target_attr
                    )
                    field_attrs[target_attr] = convert_value(
                        row[source_attr], source_attr_info, target_attr_info
                    )
                except (ValueError, KeyError) as e:
                    logger.warning(
                        f"Error converting {source_attr} to {target_attr}: {str(e)}"
                    )
                    # Store raw value if conversion fails
                    field_attrs[target_attr] = row[source_attr]

    # Generate H3 index if we have lat/lon but no H3 index
    if (
        "centroid_h3_index" not in field_attrs
        and "latitude" in field_attrs
        and "longitude" in field_attrs
    ):
        try:
            field_attrs["centroid_h3_index"] = h3.geo_to_h3(
                field_attrs["latitude"], field_attrs["longitude"], resolution=9
            )
        except Exception as e:
            logger.warning(f"Failed to generate H3 index: {str(e)}")

    return field_attrs


def get_or_create_field_meta(
    field_attrs: Dict[str, Any], db: Session
) -> Tuple[PyxisFieldMeta, bool]:
    """
    Find or create a PyxisFieldMeta record based on field attributes.
    Does NOT update H3 indices - that's done later in the merge step.

    Args:
        field_attrs: Dictionary of field attributes
        db: Database session

    Returns:
        Tuple of (PyxisFieldMeta object, is_new flag)
    """
    # Extract key identification attributes
    field_name = field_attrs.get("name")
    field_country = field_attrs.get("country")
    centroid_h3_index = field_attrs.get("centroid_h3_index")

    # Try to find a matching field
    matching_field, match_score = find_matching_field(
        field_name, field_country, centroid_h3_index, db
    )

    if matching_field:
        logger.info(
            f"Found matching field '{matching_field.name}' with score {match_score}"
        )
        return matching_field, False

    # Create new field meta if no match found
    logger.info(f"Creating new field '{field_name}' (no match found)")
    new_field = PyxisFieldMeta(
        pyxis_field_code=str(uuid.uuid4()),
        name=field_attrs.get('name'),
        country=field_attrs.get('country'),
        centroid_h3_index=field_attrs.get('centroid_h3_index'),
        geometry=field_attrs.get('geometry')  # This might be None, which is fine
    )
    db.add(new_field)
    db.flush()  # Get ID assigned by database
    
    return new_field, True


def update_pyxis_field_meta_merge(field_meta_id: int, db: Session) -> None:
    """
    Update PyxisFieldMeta with merged name, country, and geometry from all associated field data.
    Calculate centroid H3 from merged geometry.
    This is where H3 indices are updated - only once per field during merge.

    Args:
        field_meta_id: ID of the PyxisFieldMeta to update
        db: Database session
    """
    # Get the field meta record
    field_meta = db.get(PyxisFieldMeta, field_meta_id)
    if not field_meta:
        logger.error(f"Field meta with ID {field_meta_id} not found")
        return

    # Get all field data records for this field meta
    field_data_records = (
        db.query(PyxisFieldData)
        .filter(PyxisFieldData.pyxis_field_meta_id == field_meta_id)
        .all()
    )

    if not field_data_records:
        return

    # Merge only name, country, and geometry using merge utilities
    merged_values = merge_specific_attributes(
        field_data_records, 
        ['name', 'country', 'geometry']
    )

    # Update field meta with merged values
    updates_made = False
    for attr, value in merged_values.items():
        if hasattr(field_meta, attr):
            current_value = getattr(field_meta, attr)
            # Don't overwrite with None and only update if value changed
            if value is not None and value != current_value:
                setattr(field_meta, attr, value)
                updates_made = True

    # Update H3 indices if anything was updated (especially geometry)
    if updates_made:
        logger.info(f"Merging data for field {field_meta_id}")
        field_meta.updated_at = datetime.now()
        db.add(field_meta)
        # This is the ONLY place where H3 indices are updated
        update_field_h3_indices(db, field_meta)


def create_field_data(
    field_meta: PyxisFieldMeta,
    field_attrs: Dict[str, Any],
    data_entry: DataEntry,
) -> PyxisFieldData:
    """
    Create a PyxisFieldData record for a field.

    Args:
        field_meta: PyxisFieldMeta object
        field_attrs: Dictionary of field attributes
        data_entry: Data entry object

    Returns:
        PyxisFieldData object
    """
    # Base field data attributes with validity dates from data entry
    data_dict = {
        "pyxis_field_meta_id": field_meta.id,
        "data_entry_id": data_entry.id,
    }

    # Add all mapped field attributes
    data_dict.update(field_attrs)

    # Create and return the field data object
    return PyxisFieldData(**data_dict)


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


def update_field_h3_indices(db: Session, field_meta, resolution: int = 9):
    """
    Update H3 indices for a field when its geometry changes.
    """
    logger.info(f"Updating H3 indices for field {field_meta.id}")
    
    # Check if geometry exists and is the correct type
    if not field_meta.geometry:
        return
    
    try:
        # Convert to Shapely geometry
        shapely_geom = to_shape(field_meta.geometry)
        geom_type = type(shapely_geom).__name__
        
        # Collect all H3 indices from all polygons
        all_h3_indices = set()
        
        if geom_type == 'Polygon':
            geojson = {
                "type": "Polygon",
                "coordinates": [list(shapely_geom.exterior.coords)]
            }
            h3_indices = h3.polyfill(geojson, resolution)
            all_h3_indices.update(h3_indices)
            
        elif geom_type == 'MultiPolygon':
            # Process each polygon in the MultiPolygon
            for polygon in shapely_geom.geoms:
                geojson = {
                    "type": "Polygon",
                    "coordinates": [list(polygon.exterior.coords)]
                }
                h3_indices = h3.polyfill(geojson, resolution)
                all_h3_indices.update(h3_indices)
        else:
            logger.error(f"Field {field_meta.id} unsupported geometry type: {geom_type}")
            return
        
        if not all_h3_indices:
            return
        
        # Update database: remove old indices and add new ones
        db.query(PyxisFieldH3).filter(
            PyxisFieldH3.pyxis_field_meta_id == field_meta.id
        ).delete()
        
        # Bulk insert new H3 indices
        h3_records = [
            PyxisFieldH3(pyxis_field_meta_id=field_meta.id, h3_index=h3_index)
            for h3_index in all_h3_indices
        ]
        db.add_all(h3_records)
        logger.info(f"Added {len(h3_records)} H3 indices for field {field_meta.id}")
        
    except Exception as e:
        logger.error(f"Failed to update H3 indices for field {field_meta.id}: {str(e)}")


def calculate_match_score(
    name1: Optional[str],
    name2: Optional[str],
    index1: Optional[str],
    index2: Optional[str],
    weights: List[float] = MATCH_WEIGHTS,
) -> float:
    """
    Calculate match score based on name similarity and H3 distance.

    Args:
        name1: Name of the first field
        name2: Name of the second field
        index1: H3 index of the first field
        index2: H3 index of the second field
        weights: Weights for name score and geo score [name_weight, geo_weight]

    Returns:
        float: Match score between 0 and 100
    """
    # Calculate name similarity score
    if name1 is not None and name2 is not None:
        name_score = fuzz.ratio(str(name1).lower(), str(name2).lower())
    else:
        name_score = 0

    # Calculate geographical distance score
    if index1 is not None and index2 is not None:
        try:
            grid_distance = h3.h3_distance(index1, index2)
            if grid_distance < 50:
                # Normalize distance to a score using Gaussian distribution
                import numpy as np
                geo_score = 100 * np.exp(-0.5 * np.power(grid_distance * 0.1, 2))
            else:
                geo_score = -40
        except ValueError:
            # Handle cases where distance cannot be computed (too far away)
            geo_score = -40
    else:
        geo_score = 0

    # Combine scores using weights
    return weights[0] * name_score + weights[1] * geo_score


def find_matching_field(
    field_name: Optional[str],
    field_country: Optional[str],
    centroid_h3_index: Optional[str],
    db: Session,
) -> Tuple[Optional[PyxisFieldMeta], float]:
    """
    Find a matching PyxisFieldMeta based on name and location.

    Args:
        field_name: Name of the field to match
        field_country: Country of the field
        centroid_h3_index: H3 index of the field
        db: Database session

    Returns:
        Tuple of (matching_field, match_score) or (None, 0) if no match found
    """
    if not field_name:
        return None, 0

    # Query for potential matches - filter by country if available to reduce candidates
    query = db.query(PyxisFieldMeta)
    if field_country:
        query = query.filter(PyxisFieldMeta.country == field_country)

    potential_matches = query.all()

    best_match = None
    best_score = 0

    # Calculate match scores for each potential match
    for field in potential_matches:
        score = calculate_match_score(
            field_name, field.name, centroid_h3_index, field.centroid_h3_index
        )

        if score > best_score:
            best_score = score
            best_match = field

    # Return the best match if it meets the threshold
    if best_match and best_score >= MATCH_SCORE_THRESHOLD:
        return best_match, best_score

    return None, best_score


@logfire.instrument("Background data processing task for data entry {data_entry=}")
def process_data_entry_background(data_entry: DataEntry, db: Session) -> None:
    """
    Process a data entry in the background.

    Args:
        data_entry: The data entry to process
        db: Database session
    """
    db.add(data_entry)
    try:
        logger.info("Starting background processing for data entry %s", data_entry.id)

        # Process data based on file type
        with logfire.span(f"Process data for type {data_entry.file_extension}"):
            if data_entry.file_extension == FileExtension.CSV:
                process_csv_data(data_entry, db)
            else:
                # Set error for unsupported file types
                data_entry.status = ProcessingStatus.FAILED
                data_entry.error_message = (
                    f"Unsupported file extension: {data_entry.file_extension}"
                )
                logger.error(
                    "Unsupported file extension: %s", data_entry.file_extension
                )
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

    # Track field metas that need to be merged and updated
    field_metas_to_merge = {}  # field_meta_id -> field_attrs

    # Process each row in the CSV
    for _, row in df.iterrows():
        # Extract mapped data from the row
        field_attrs = extract_field_attributes(row, config_model)

        # Find or create a PyxisFieldMeta record (without H3 update)
        field_meta, is_new = get_or_create_field_meta(field_attrs, db)

        # Create a PyxisFieldData record
        field_data = create_field_data(field_meta, field_attrs, data_entry)
        db.add(field_data)

        # Track this field meta for merging
        field_metas_to_merge[field_meta.id] = field_attrs

    # Flush to assign IDs to field data
    db.flush()

    # Now merge and update H3 indices for all affected field metas
    for field_meta_id, field_attrs in field_metas_to_merge.items():
        update_pyxis_field_meta_merge(field_meta_id, field_attrs, db)

    # Commit all changes
    db.commit()


def extract_field_attributes(
    row: pd.Series, config: DataEntryConfiguration
) -> Dict[str, Any]:
    """
    Extract field attributes from a CSV row based on mappings.

    Args:
        row: Pandas Series row from CSV
        config: DataEntryConfiguration with mappings

    Returns:
        Dictionary of field attributes with target attribute names as keys
    """
    field_attrs = {}

    # Process each mapping
    for mapping in config.mappings:
        source_attr = mapping.source_attribute
        target_attr = mapping.target_attribute

        # Map source attribute to target attribute if value exists
        if source_attr in row and pd.notna(row[source_attr]):
            source_attr_info = config.get_source_attribute_map().get(source_attr)

            if source_attr_info:
                try:
                    # Get attribute info for proper type conversion
                    target_attr_info = PyxisFieldData.get_attribute_info_by_name(
                        target_attr
                    )
                    field_attrs[target_attr] = convert_value(
                        row[source_attr], source_attr_info, target_attr_info
                    )
                except (ValueError, KeyError) as e:
                    logger.warning(
                        f"Error converting {source_attr} to {target_attr}: {str(e)}"
                    )
                    # Store raw value if conversion fails
                    field_attrs[target_attr] = row[source_attr]

    # Generate H3 index if we have lat/lon but no H3 index
    if (
        "centroid_h3_index" not in field_attrs
        and "latitude" in field_attrs
        and "longitude" in field_attrs
    ):
        try:
            field_attrs["centroid_h3_index"] = h3.geo_to_h3(
                field_attrs["latitude"], field_attrs["longitude"], resolution=9
            )
        except Exception as e:
            logger.warning(f"Failed to generate H3 index: {str(e)}")

    return field_attrs


def get_or_create_field_meta(
    field_attrs: Dict[str, Any], db: Session
) -> Tuple[PyxisFieldMeta, bool]:
    """
    Find or create a PyxisFieldMeta record based on field attributes.
    Does NOT update H3 indices - that's done later in the merge step.

    Args:
        field_attrs: Dictionary of field attributes
        db: Database session

    Returns:
        Tuple of (PyxisFieldMeta object, is_new flag)
    """
    # Extract key identification attributes
    field_name = field_attrs.get("name")
    field_country = field_attrs.get("country")
    centroid_h3_index = field_attrs.get("centroid_h3_index")

    # Try to find a matching field
    matching_field, match_score = find_matching_field(
        field_name, field_country, centroid_h3_index, db
    )

    if matching_field:
        logger.info(
            f"Found matching field '{matching_field.name}' with score {match_score}"
        )
        return matching_field, False

    # Create new field meta if no match found
    logger.info(f"Creating new field '{field_name}' (no match found)")
    new_field = PyxisFieldMeta(
        pyxis_field_code=str(uuid.uuid4()),
        name=field_attrs.get('name'),
        country=field_attrs.get('country'),
        centroid_h3_index=field_attrs.get('centroid_h3_index'),
        geometry=field_attrs.get('geometry')  # This might be None, which is fine
    )
    db.add(new_field)
    db.flush()  # Get ID assigned by database
    
    return new_field, True


def update_pyxis_field_meta_merge(
    field_meta_id: int, field_attrs: Dict[str, Any], db: Session
) -> None:
    """
    Update PyxisFieldMeta with merged name, country, and geometry from all associated field data.
    This is where H3 indices are updated - only once per field during merge.

    Args:
        field_meta_id: ID of the PyxisFieldMeta to update
        field_attrs: Dictionary of field attributes from current row (not used in merge)
        db: Database session
    """
    # Get the field meta record
    field_meta = db.get(PyxisFieldMeta, field_meta_id)
    if not field_meta:
        logger.error(f"Field meta with ID {field_meta_id} not found")
        return

    # Get all field data records for this field meta
    field_data_records = (
        db.query(PyxisFieldData)
        .filter(PyxisFieldData.pyxis_field_meta_id == field_meta_id)
        .all()
    )

    if not field_data_records:
        return

    # Merge only name, country, and geometry using merge utilities
    merged_values = merge_specific_attributes(
        field_data_records, 
        ['name', 'country', 'geometry']
    )

    # Update field meta with merged values
    updates_made = False
    for attr, value in merged_values.items():
        if hasattr(field_meta, attr):
            current_value = getattr(field_meta, attr)
            # Don't overwrite with None and only update if value changed
            if value is not None and value != current_value:
                setattr(field_meta, attr, value)
                updates_made = True

    # Update H3 indices if anything was updated (especially geometry)
    if updates_made:
        logger.info(f"Merging data for field {field_meta_id}")
        field_meta.updated_at = datetime.now()
        db.add(field_meta)
        # This is the ONLY place where H3 indices are updated
        update_field_h3_indices(db, field_meta)


def create_field_data(
    field_meta: PyxisFieldMeta,
    field_attrs: Dict[str, Any],
    data_entry: DataEntry,
) -> PyxisFieldData:
    """
    Create a PyxisFieldData record for a field.

    Args:
        field_meta: PyxisFieldMeta object
        field_attrs: Dictionary of field attributes
        data_entry: Data entry object

    Returns:
        PyxisFieldData object
    """
    # Base field data attributes with validity dates from data entry
    data_dict = {
        "pyxis_field_meta_id": field_meta.id,
        "data_entry_id": data_entry.id,
    }

    # Add all mapped field attributes
    data_dict.update(field_attrs)

    # Create and return the field data object
    return PyxisFieldData(**data_dict)


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