import io
import json
import logging
import hashlib
import uuid
import time
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

from app.postgres.models.pyxis_field import PyxisFieldMeta, PyxisFieldData
from app.postgres.models.data_source import DataSourceMeta
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
from app.schemas.data_entry import (
    BatchProcessRequest,
    BatchProcessResponse,
    BatchEntryResult,
    MatchSequence,
)
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
    prevent_self_matching: bool = False,
    match_by_source_id: bool = False,
) -> Dict[str, Any]:
    """
    Trigger data processing for a data entry.

    Args:
        data_entry: Data entry object
        background_tasks: FastAPI background tasks
        db: Database session
        prevent_self_matching: Prevent matching to fields from the same processing session
        match_by_source_id: Match by source field identifier instead of fuzzy name/geo matching

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

    # Add background task with matching parameters
    background_tasks.add_task(
        process_data_entry_background,
        data_entry,
        db,
        prevent_self_matching,
        match_by_source_id,
    )

    return {
        "success": True,
        "message": f"Processing started for data entry with ID {data_entry.id} (prevent_self_matching: {prevent_self_matching}, match_by_source_id: {match_by_source_id})",
        "data_entry_id": data_entry.id,
        "status": ProcessingStatus.PROCESSING,
    }

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
    exclude_field_meta_ids: Optional[set] = None,
) -> Tuple[Optional[PyxisFieldMeta], float]:
    """
    Find a matching PyxisFieldMeta based on name and location.

    Args:
        field_name: Name of the field to match
        field_country: Country of the field
        centroid_h3_index: H3 index of the field
        db: Database session
        exclude_field_meta_ids: Set of field meta IDs to exclude from matching

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

    # Exclude fields from current processing session if specified
    if exclude_field_meta_ids:
        potential_matches = [
            field for field in potential_matches 
            if field.id not in exclude_field_meta_ids
        ]

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
def process_data_entry_background(
    data_entry: DataEntry,
    db: Session,
    prevent_self_matching: bool = False,
    match_by_source_id: bool = False,
) -> Dict[str, int]:
    """
    Process a data entry in the background.

    Args:
        data_entry: The data entry to process
        db: Database session
        prevent_self_matching: Prevent matching to fields from the same processing session
        match_by_source_id: Match by source field identifier instead of fuzzy name/geo matching

    Returns:
        Dict with processing stats: {"records_created", "fields_matched", "fields_created"}
    """
    db.add(data_entry)
    stats = {"records_created": 0, "fields_matched": 0, "fields_created": 0}
    try:
        logger.info(
            "Starting background processing for data entry %s (prevent_self_matching: %s, match_by_source_id: %s)",
            data_entry.id,
            prevent_self_matching,
            match_by_source_id
        )

        # Process data based on file type
        with logfire.span(f"Process data for type {data_entry.file_extension}"):
            if data_entry.file_extension == FileExtension.CSV:
                stats = process_csv_data(data_entry, db, prevent_self_matching, match_by_source_id)
            else:
                # Set error for unsupported file types
                data_entry.status = ProcessingStatus.FAILED
                data_entry.error_message = (
                    f"Unsupported file extension: {data_entry.file_extension}"
                )
                logger.error(
                    "Unsupported file extension: %s", data_entry.file_extension
                )
                return stats

        # Update status to COMPLETED
        data_entry.status = ProcessingStatus.COMPLETED
        logger.info("Completed processing for data entry %s", data_entry.id)
    except Exception as e:
        # Handle processing errors
        data_entry.status = ProcessingStatus.FAILED
        data_entry.error_message = f"Processing error: {str(e)}"
        logger.exception("Error processing data entry %s: %s", data_entry.id, str(e))
        raise e
    finally:
        db.commit()

    return stats


def process_csv_data(
    data_entry: DataEntry,
    db: Session,
    prevent_self_matching: bool = False,
    match_by_source_id: bool = False,
) -> Dict[str, int]:
    """
    Process CSV data and create Pyxis field data entries.

    Args:
        data_entry: Data entry object
        db: Database session
        prevent_self_matching: Prevent matching to fields from the same processing session
        match_by_source_id: Match by source field identifier instead of fuzzy name/geo matching

    Returns:
        Dict with stats: {"records_created", "fields_matched", "fields_created"}
    """
    try:
        # Parse the config JSON to a Pydantic model
        config_model = DataEntryConfiguration.model_validate(data_entry.config_file)
    except ValidationError as e:
        raise ValueError(f"Failed to parse configuration: {str(e)}") from e

    mappings = config_model.mappings
    if not mappings:
        raise ValueError("No mappings found in config file")

    logger.info(f"Self-matching prevention: {'ENABLED' if prevent_self_matching else 'DISABLED'}")
    logger.info(f"Match by source ID: {'ENABLED' if match_by_source_id else 'DISABLED'}")

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

    # Track ONLY newly created field meta IDs (not matched ones)
    newly_created_field_meta_ids = set()

    # Stats tracking
    records_created = 0
    fields_matched = 0
    fields_created = 0

    # Process each row in the CSV
    for row_index, row in df.iterrows():
        # Extract mapped data from the row
        field_attrs = extract_field_attributes(row, config_model)

        # Exclude only newly created fields from this session
        exclude_ids = newly_created_field_meta_ids if prevent_self_matching else None

        # Find or create a PyxisFieldMeta record
        field_meta, is_new = get_or_create_field_meta(
            field_attrs, db, exclude_ids, match_by_source_id, data_entry.source_id
        )

        # Only track newly created fields for exclusion (not matched existing fields)
        if is_new:
            newly_created_field_meta_ids.add(field_meta.id)
            fields_created += 1
        else:
            fields_matched += 1

        # Create a PyxisFieldData record
        field_data = create_field_data(field_meta, field_attrs, data_entry)
        db.add(field_data)
        records_created += 1

        # Track this field meta for merging
        field_metas_to_merge.add(field_meta.id)

    # Flush to assign IDs to field data
    db.flush()

    # Now merge for all affected field metas
    for field_meta_id in field_metas_to_merge:
        update_pyxis_field_meta_merge(field_meta_id, db)

    # Commit all changes
    db.commit()

    logger.info(f"Processed {len(df)} rows with {len(field_metas_to_merge)} total fields")
    logger.info(f"Created {fields_created} new fields")
    logger.info(f"Matched to {fields_matched} existing fields")

    if prevent_self_matching:
        logger.info(f"Self-matching prevention excluded {len(newly_created_field_meta_ids)} newly created field IDs from matching")

    return {
        "records_created": records_created,
        "fields_matched": fields_matched,
        "fields_created": fields_created
    }


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
    field_attrs: Dict[str, Any],
    db: Session,
    exclude_field_meta_ids: Optional[set] = None,
    match_by_source_id: bool = False,
    source_id: Optional[int] = None,
) -> Tuple[PyxisFieldMeta, bool]:
    """
    Find or create a PyxisFieldMeta record based on field attributes.

    Args:
        field_attrs: Dictionary of field attributes
        db: Database session
        exclude_field_meta_ids: Set of field meta IDs to exclude from matching
        match_by_source_id: If True, match by source field identifier instead of fuzzy matching
        source_id: Source ID for source-based matching (required if match_by_source_id=True)

    Returns:
        Tuple of (PyxisFieldMeta object, is_new flag)
    """
    # Extract key identification attributes
    field_name = field_attrs.get("name")
    field_country = field_attrs.get("country")
    centroid_h3_index = field_attrs.get("centroid_h3_index")
    source_field_id = field_attrs.get("field_id")  # Source's original field identifier

    # If match_by_source_id is enabled, try to find by source field ID first
    if match_by_source_id and source_field_id:
        matching_field = find_field_by_source_id(source_field_id, source_id, field_country, db)
        if matching_field:
            logger.debug(
                f"Found field by source ID '{source_field_id}' -> '{matching_field.name}' (ID: {matching_field.id})"
            )
            return matching_field, False
        else:
            # If no match found by source ID, fall through to create new or fuzzy match
            logger.warning(
                f"No field found for source_field_id='{source_field_id}', source_id={source_id}. "
                f"Will create new field."
            )

    # Standard fuzzy matching by name and location
    if not match_by_source_id:
        matching_field, match_score = find_matching_field(
            field_name, field_country, centroid_h3_index, db, exclude_field_meta_ids
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


def find_field_by_source_id(
    source_field_id: str,
    source_id: Optional[int],
    country: Optional[str],
    db: Session
) -> Optional[PyxisFieldMeta]:
    """
    Find a PyxisFieldMeta by looking up existing PyxisFieldData records
    that came from the same source and have the same source field identifier.

    This enables matching monthly data to static data from the same government source
    without requiring expensive fuzzy name/geo matching.

    Args:
        source_field_id: The field identifier from the source (e.g., government field code)
        source_id: The data source ID to search within
        country: Country filter to narrow down matches
        db: Database session

    Returns:
        PyxisFieldMeta if found, None otherwise
    """
    # Build query to find existing field data with matching source field ID
    query = (
        db.query(PyxisFieldData)
        .join(DataEntry, PyxisFieldData.data_entry_id == DataEntry.id)
        .filter(PyxisFieldData.field_id == source_field_id)
    )

    # Filter by source if provided
    if source_id:
        query = query.filter(DataEntry.source_id == source_id)

    # Filter by country if provided
    if country:
        query = query.filter(PyxisFieldData.country == country)

    # Get the first matching field data
    existing_field_data = query.first()

    if existing_field_data and existing_field_data.pyxis_field_meta_id:
        return db.get(PyxisFieldMeta, existing_field_data.pyxis_field_meta_id)

    return None

def update_pyxis_field_meta_merge(field_meta_id: int, db: Session) -> None:
    """
    Update PyxisFieldMeta with merged name, country, functional_unit, and geometry from all associated field data.
    Calculate centroid H3 from merged geometry.

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

    # Merge only name, country, functional_unit, and geometry using merge utilities
    merged_values = merge_specific_attributes(
        field_data_records,
        ['name', 'country', 'functional_unit', 'geometry']
    )

    # Update field meta with merged values
    for attr, value in merged_values.items():
        if hasattr(field_meta, attr):
            current_value = getattr(field_meta, attr)
            # Don't overwrite with None and only update if value changed
            if value is not None and value != current_value:
                setattr(field_meta, attr, value)



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


def batch_process_entries(
    request: BatchProcessRequest,
    db: Session
) -> BatchProcessResponse:
    """
    Process multiple data entries in a controlled sequence.

    The entries are processed synchronously in sequence based on the specified
    match_sequence strategy. This allows higher quality sources to create base
    fields that lower quality sources can match against.

    Args:
        request: BatchProcessRequest with entries and match_sequence
        db: Database session

    Returns:
        BatchProcessResponse with results for each entry
    """
    start_time = time.time()
    results: List[BatchEntryResult] = []
    processing_order: List[int] = []

    # Build entry config map
    entry_configs = {e.entry_id: e for e in request.entries}
    entry_ids = list(entry_configs.keys())

    # Fetch all entries
    entries = db.query(DataEntry).filter(DataEntry.id.in_(entry_ids)).all()
    entry_map = {e.id: e for e in entries}

    # Determine processing order based on match_sequence
    if request.match_sequence == MatchSequence.SOURCE_SCORE:
        # Sort by data source pyxis_score (highest first)
        # Fetch source scores
        source_ids = {e.source_id for e in entries}
        sources = db.query(DataSourceMeta).filter(DataSourceMeta.id.in_(source_ids)).all()
        source_scores = {s.id: s.pyxis_score or 0.0 for s in sources}

        # Sort entries by source score (descending)
        sorted_entries = sorted(
            entries,
            key=lambda e: source_scores.get(e.source_id, 0.0),
            reverse=True
        )
        processing_order = [e.id for e in sorted_entries]

    elif request.match_sequence == MatchSequence.TIME_RECENCY:
        # Sort by valid_from date (newest first, None values last)
        sorted_entries = sorted(
            entries,
            key=lambda e: (e.valid_from is None, e.valid_from),
            reverse=True
        )
        processing_order = [e.id for e in sorted_entries]

    else:  # ENTRY_ORDER
        # Keep the order specified in the request
        processing_order = entry_ids

    logger.info(f"Batch processing {len(processing_order)} entries in order: {processing_order}")
    logger.info(f"Match sequence strategy: {request.match_sequence.value}")

    completed = 0
    failed = 0

    # Process each entry in order
    for entry_id in processing_order:
        entry = entry_map.get(entry_id)
        config = entry_configs.get(entry_id)

        if not entry or not config:
            results.append(BatchEntryResult(
                entry_id=entry_id,
                alias="Unknown",
                status=ProcessingStatus.FAILED,
                error_message=f"Entry {entry_id} not found"
            ))
            failed += 1
            continue

        entry_start_time = time.time()

        # Check if entry is in processable state
        if entry.status not in [ProcessingStatus.PENDING, ProcessingStatus.FAILED]:
            results.append(BatchEntryResult(
                entry_id=entry_id,
                alias=entry.alias,
                status=entry.status,
                error_message=f"Entry not in PENDING/FAILED state (current: {entry.status})"
            ))
            failed += 1
            continue

        # Set to PROCESSING
        entry.status = ProcessingStatus.PROCESSING
        db.add(entry)
        db.commit()

        try:
            # Process synchronously with the configured options
            stats = process_csv_data(
                entry, db,
                prevent_self_matching=config.prevent_self_matching,
                match_by_source_id=config.match_by_source_id
            )

            # Mark as completed
            entry.status = ProcessingStatus.COMPLETED
            entry.error_message = None
            db.commit()

            entry_time = time.time() - entry_start_time
            results.append(BatchEntryResult(
                entry_id=entry_id,
                alias=entry.alias,
                status=ProcessingStatus.COMPLETED,
                records_created=stats.get("records_created", 0),
                fields_matched=stats.get("fields_matched", 0),
                fields_created=stats.get("fields_created", 0),
                processing_time_seconds=round(entry_time, 2)
            ))
            completed += 1

            logger.info(
                f"Entry {entry_id} ({entry.alias}) completed: "
                f"{stats.get('records_created', 0)} records, "
                f"{stats.get('fields_created', 0)} new fields, "
                f"{stats.get('fields_matched', 0)} matched"
            )

        except Exception as e:
            entry.status = ProcessingStatus.FAILED
            entry.error_message = str(e)[:500]
            db.commit()

            entry_time = time.time() - entry_start_time
            results.append(BatchEntryResult(
                entry_id=entry_id,
                alias=entry.alias,
                status=ProcessingStatus.FAILED,
                error_message=str(e)[:500],
                processing_time_seconds=round(entry_time, 2)
            ))
            failed += 1

            logger.error(f"Entry {entry_id} ({entry.alias}) failed: {str(e)}")

    total_time = time.time() - start_time

    return BatchProcessResponse(
        success=failed == 0,
        total_entries=len(processing_order),
        completed=completed,
        failed=failed,
        results=results,
        processing_order=processing_order,
        total_processing_time_seconds=round(total_time, 2)
    )