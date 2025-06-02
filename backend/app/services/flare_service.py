"""
Flare service for processing flare data from CSV files and field assignment.
"""

import io
import csv
import os
import logging
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Tuple, Optional, Set

import pandas as pd
import h3
from fastapi import UploadFile
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session
from geoalchemy2 import WKTElement

from app.postgres.models.flare import Flare
from app.postgres.models.pyxis_field import PyxisFieldMeta, PyxisFieldData
from app.schemas.flare import FlareCreate, FlareFilter
from app.utils.path_util import get_data_path
from app.utils.flare_utils import FlareUtils


logger = logging.getLogger(__name__)

flare_res = 9


class FlareService:
    """Service for handling flare data operations"""

    @staticmethod
    def excel_serial_to_date(serial: float) -> date:
        """
        Convert Excel serial date to Python date.
        
        Args:
            serial: Excel serial date number
            
        Returns:
            Python date object
        """
        # Excel dates start from 1899-12-30 (accounting for Excel's leap year bug)
        excel_epoch = datetime(1899, 12, 30)
        python_date = excel_epoch + timedelta(days=serial)
        return python_date.date()

    @staticmethod
    def get_month_period(date_obj: date) -> Tuple[date, date]:
        """
        Get the first and last day of the month for a given date.
        
        Args:
            date_obj: Date object
            
        Returns:
            Tuple of (first_day, last_day) of the month
        """
        first_day = date_obj.replace(day=1)
        # Get last day of month by going to first day of next month and subtracting 1 day
        if first_day.month == 12:
            last_day = first_day.replace(year=first_day.year + 1, month=1) - timedelta(days=1)
        else:
            last_day = first_day.replace(month=first_day.month + 1) - timedelta(days=1)
        
        return first_day, last_day

    @staticmethod
    async def process_csv_file(
        file: UploadFile, 
        db: Session,
        update_existing: bool = True
    ) -> Dict[str, Any]:
        """
        Process flare data from CSV file and store in database.
        
        Args:
            file: Uploaded CSV file
            db: Database session
            update_existing: Whether to update existing records
            
        Returns:
            Dict with processing results
        """
        try:
            # Read CSV file
            content = await file.read()
            df = pd.read_csv(io.BytesIO(content))
            
            logger.info(f"Processing CSV file with {len(df)} rows")
            
            # Validate required columns
            required_columns = ['lat', 'lon', 'month', 'id', 'BCM']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                raise ValueError(f"Missing required columns: {missing_columns}")
            
            # Process records
            created_count = 0
            updated_count = 0
            skipped_count = 0
            errors = []
            
            for index, row in df.iterrows():
                try:
                    # Extract and validate data
                    original_id = str(row['id'])
                    latitude = float(row['lat'])
                    longitude = float(row['lon'])
                    volume = float(row['BCM'])
                    month_serial = row['month']
                    
                    # Convert Excel serial date to Python date
                    if isinstance(month_serial, (int, float)):
                        month_date = FlareService.excel_serial_to_date(month_serial)
                    else:
                        # Try to parse as date string if not numeric
                        month_date = pd.to_datetime(month_serial).date()
                    
                    # Get month period
                    valid_from, valid_to = FlareService.get_month_period(month_date)
                    
                    # Calculate H3 index
                    h3_index = h3.geo_to_h3(latitude, longitude, resolution=flare_res)
                    
                    # Create geometry (PostGIS POINT)
                    geometry = WKTElement(f'POINT({longitude} {latitude})', srid=4326)
                    
                    # Check if record exists
                    existing_flare = db.query(Flare).filter(
                        and_(
                            Flare.original_id == original_id,
                            Flare.valid_from == valid_from
                        )
                    ).first()
                    
                    if existing_flare:
                        if update_existing:
                            # Update existing record
                            existing_flare.latitude = latitude
                            existing_flare.longitude = longitude
                            existing_flare.volume = volume
                            existing_flare.valid_to = valid_to
                            existing_flare.h3_index = h3_index
                            existing_flare.geometry = geometry
                            updated_count += 1
                        else:
                            skipped_count += 1
                    else:
                        # Create new record
                        new_flare = Flare(
                            original_id=original_id,
                            latitude=latitude,
                            longitude=longitude,
                            volume=volume,
                            valid_from=valid_from,
                            valid_to=valid_to,
                            h3_index=h3_index,
                            geometry=geometry
                        )
                        db.add(new_flare)
                        created_count += 1
                        
                except Exception as e:
                    error_msg = f"Row {index + 1}: {str(e)}"
                    errors.append(error_msg)
                    logger.warning(error_msg)
                    continue
            
            # Commit all changes
            db.commit()
            
            logger.info(f"Processing complete: {created_count} created, {updated_count} updated, {skipped_count} skipped")
            
            return {
                "processed_records": len(df),
                "created_records": created_count,
                "updated_records": updated_count, 
                "skipped_records": skipped_count,
                "errors": errors
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error processing CSV file: {str(e)}")
            raise

    @staticmethod
    def get_flares(
        db: Session,
        filters: FlareFilter = None,
        skip: int = 0,
        limit: int = 100
    ) -> Tuple[List[Flare], int]:
        """
        Get flares with optional filtering.
        
        Args:
            db: Database session
            filters: Optional filters to apply
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            Tuple of (flares list, total count)
        """
        query = db.query(Flare)
        
        # Apply filters if provided
        if filters:
            if filters.original_id:
                query = query.filter(Flare.original_id == filters.original_id)
            
            if filters.min_volume is not None:
                query = query.filter(Flare.volume >= filters.min_volume)
            
            if filters.max_volume is not None:
                query = query.filter(Flare.volume <= filters.max_volume)
            
            if filters.min_lat is not None:
                query = query.filter(Flare.latitude >= filters.min_lat)
            
            if filters.max_lat is not None:
                query = query.filter(Flare.latitude <= filters.max_lat)
            
            if filters.min_lon is not None:
                query = query.filter(Flare.longitude >= filters.min_lon)
            
            if filters.max_lon is not None:
                query = query.filter(Flare.longitude <= filters.max_lon)
            
            if filters.valid_date:
                query = query.filter(
                    and_(
                        Flare.valid_from <= filters.valid_date,
                        Flare.valid_to >= filters.valid_date
                    )
                )
            
            if filters.h3_index:
                query = query.filter(Flare.h3_index == filters.h3_index)
        
        # Get total count before applying pagination
        total = query.count()
        
        # Apply pagination and get results
        flares = query.offset(skip).limit(limit).all()
        
        return flares, total

    @staticmethod
    def get_flare_by_id(db: Session, flare_id: str) -> Flare:
        """
        Get a flare by its ID.
        
        Args:
            db: Database session
            flare_id: Flare ID
            
        Returns:
            Flare object or None
        """
        return db.query(Flare).filter(Flare.flare_id == flare_id).first()

    @staticmethod
    def delete_flares_by_criteria(
        db: Session,
        original_ids: List[str] = None,
        date_range: Tuple[date, date] = None
    ) -> int:
        """
        Delete flares by criteria (useful for re-importing data).
        
        Args:
            db: Database session
            original_ids: List of original IDs to delete
            date_range: Tuple of (start_date, end_date) for validity period
            
        Returns:
            Number of deleted records
        """
        query = db.query(Flare)
        
        if original_ids:
            query = query.filter(Flare.original_id.in_(original_ids))
        
        if date_range:
            start_date, end_date = date_range
            query = query.filter(
                and_(
                    Flare.valid_from <= end_date,
                    Flare.valid_to >= start_date
                )
            )
        
        deleted_count = query.count()
        query.delete(synchronize_session=False)
        db.commit()
        
        logger.info(f"Deleted {deleted_count} flare records")
        return deleted_count

    # New methods for flare assignment
    @staticmethod
    def assign_flares_to_fields(
        start_date: date,
        end_date: date,
        db: Session,
        field_ids: Optional[List[int]] = None,
        country: Optional[str] = None,
        proximity_distance_km: float = 100.0,
        buffer_distance_km: float = 5.0
    ) -> Tuple[Dict[str, Any], str]:
        """
        Assign flares to fields based on spatial and temporal criteria.
        
        Args:
            start_date: Start date for time range filter
            end_date: End date for time range filter
            db: Database session
            field_ids: Optional list of specific field IDs
            country: Optional country filter for fields
            proximity_distance_km: Distance for H3 k-ring proximity filtering
            buffer_distance_km: Buffer distance for buffer matching
            
        Returns:
            Tuple of (assignment_statistics, csv_file_path)
        """
        start_time = datetime.now()
        
        # Validate inputs
        if start_date > end_date:
            raise ValueError("start_date must be before or equal to end_date")
        
        # Step 1: Get target fields
        fields = FlareService._get_target_fields(db, field_ids, country)
        if not fields:
            raise ValueError("No fields found matching the criteria")
        
        logger.info(f"Processing {len(fields)} fields for flare assignment")
        
        # Step 2: Filter candidate flares
        candidate_flares = FlareService._filter_candidate_flares(
            fields, start_date, end_date, proximity_distance_km, db
        )
        
        logger.info(f"Found {len(candidate_flares)} candidate flares")
        
        # Step 3: Perform field-by-field matching
        field_assignments = {}
        assigned_flare_ids = set()
        
        for field in fields:
            assignment = FlareService._assign_flares_to_single_field(
                field, candidate_flares, assigned_flare_ids, buffer_distance_km
            )
            field_assignments[field.id] = assignment
            
            # Track assigned flares to avoid double assignment
            assigned_flare_ids.update(assignment['exact_match_flare_ids'])
            assigned_flare_ids.update(assignment['buffer_match_flare_ids'])
        
        # Step 4: Generate statistics
        statistics = FlareService._calculate_assignment_statistics(
            fields, candidate_flares, field_assignments, assigned_flare_ids
        )
        
        # Step 5: Generate CSV file
        csv_file_path = FlareService._generate_assignment_csv(
            field_assignments, fields, candidate_flares, start_date, end_date
        )
        
        processing_time = (datetime.now() - start_time).total_seconds()
        statistics['processing_time_seconds'] = processing_time
        
        logger.info(f"Flare assignment completed in {processing_time:.2f} seconds")
        
        return statistics, csv_file_path

    @staticmethod
    def _get_target_fields(
        db: Session,
        field_ids: Optional[List[int]] = None,
        country: Optional[str] = None
    ) -> List[PyxisFieldMeta]:
        """
        Get target fields based on field_ids or country.
        
        Args:
            db: Database session
            field_ids: Optional list of field IDs
            country: Optional country filter
            
        Returns:
            List of PyxisFieldMeta objects
        """
        if field_ids:
            fields = db.query(PyxisFieldMeta).filter(
                PyxisFieldMeta.id.in_(field_ids)
            ).all()
            if len(fields) != len(field_ids):
                found_ids = [f.id for f in fields]
                missing_ids = [fid for fid in field_ids if fid not in found_ids]
                logger.warning(f"Some field IDs not found: {missing_ids}")
            return fields
        elif country:
            return db.query(PyxisFieldMeta).filter(
                PyxisFieldMeta.country == country
            ).all()
        else:
            raise ValueError("Must provide either field_ids or country")

    @staticmethod
    def _filter_candidate_flares(
        fields: List[PyxisFieldMeta],
        start_date: date,
        end_date: date,
        proximity_distance_km: float,
        db: Session
    ) -> List[Flare]:
        """
        Filter candidate flares based on H3 proximity and time range.
        
        Args:
            fields: List of target fields
            start_date: Start date for time filter
            end_date: End date for time filter
            proximity_distance_km: Distance for H3 k-ring filtering
            db: Database session
            
        Returns:
            List of candidate flares
        """
        
        # Collect all H3 indices within proximity of any field
        all_h3_indices = set()
        
        for field in fields:
            if field.centroid_h3_index:
                nearby_h3_indices = FlareUtils.get_h3_k_ring_for_distance(
                    field.centroid_h3_index, proximity_distance_km, flare_res
                )
                all_h3_indices.update(nearby_h3_indices)
                logger.debug(f"Field {field.id}: found {len(nearby_h3_indices)} nearby H3 indices")
        
        if not all_h3_indices:
            logger.warning("No H3 indices found for fields")
            return []
        
        logger.info(f"Searching in {len(all_h3_indices)} H3 indices")
        
        # Query flares within H3 proximity and time range
        candidate_flares = db.query(Flare).filter(
            and_(
                Flare.h3_index.in_(all_h3_indices),
                or_(
                    # Flare period overlaps with query period
                    and_(Flare.valid_from <= end_date, Flare.valid_to >= start_date),
                    # Handle NULL dates (eternal validity)
                    and_(Flare.valid_from.is_(None), Flare.valid_to.is_(None)),
                    and_(Flare.valid_from <= end_date, Flare.valid_to.is_(None)),
                    and_(Flare.valid_from.is_(None), Flare.valid_to >= start_date)
                )
            )
        ).all()
        
        return candidate_flares

    @staticmethod
    def _assign_flares_to_single_field(
        field: PyxisFieldMeta,
        candidate_flares: List[Flare],
        already_assigned: Set[str],
        buffer_distance_km: float
    ) -> Dict[str, Any]:
        """
        Assign flares to a single field using exact then buffer matching.
        
        Args:
            field: Target field
            candidate_flares: List of candidate flares
            already_assigned: Set of already assigned flare IDs
            buffer_distance_km: Buffer distance for buffer matching
            
        Returns:
            Dict with assignment results for the field
        """
        from app.utils.flare_utils import FlareUtils
        
        available_flares = [f for f in candidate_flares if f.flare_id not in already_assigned]
        
        # Validate field has geometry
        if not field.geometry or not FlareUtils.validate_geometry(field.geometry):
            logger.warning(f"Field {field.id} has no valid geometry, skipping")
            return {
                'field_id': field.id,
                'field_name': field.name,
                'exact_match_flares': [],
                'buffer_match_flares': [],
                'exact_match_flare_ids': [],
                'buffer_match_flare_ids': [],
                'exact_volume': 0.0,
                'buffer_volume': 0.0,
                'total_volume': 0.0,
                'match_type': 'none'
            }
        
        # Step 1: Try exact matching
        exact_matches = []
        for flare in available_flares:
            if FlareUtils.point_in_geometry(flare.latitude, flare.longitude, field.geometry):
                exact_matches.append(flare)
        
        # Step 2: If no exact matches, try buffer matching
        buffer_matches = []
        if not exact_matches:
            buffered_geometry = FlareUtils.create_buffer_geometry(field.geometry, buffer_distance_km)
            if buffered_geometry:
                for flare in available_flares:
                    if FlareUtils.point_in_buffer_geometry(flare.latitude, flare.longitude, buffered_geometry):
                        buffer_matches.append(flare)
        
        # Calculate volumes
        exact_volume = sum(f.volume for f in exact_matches)
        buffer_volume = sum(f.volume for f in buffer_matches)
        
        return {
            'field_id': field.id,
            'field_name': field.name,
            'exact_match_flares': exact_matches,
            'buffer_match_flares': buffer_matches,
            'exact_match_flare_ids': [f.flare_id for f in exact_matches],
            'buffer_match_flare_ids': [f.flare_id for f in buffer_matches],
            'exact_volume': exact_volume,
            'buffer_volume': buffer_volume,
            'total_volume': exact_volume + buffer_volume,
            'match_type': 'exact' if exact_matches else ('buffer' if buffer_matches else 'none')
        }

    @staticmethod
    def _calculate_assignment_statistics(
        fields: List[PyxisFieldMeta],
        candidate_flares: List[Flare],
        field_assignments: Dict[int, Dict],
        assigned_flare_ids: Set[str]
    ) -> Dict[str, Any]:
        """
        Calculate assignment statistics.
        
        Args:
            fields: List of target fields
            candidate_flares: List of candidate flares
            field_assignments: Field assignment results
            assigned_flare_ids: Set of assigned flare IDs
            
        Returns:
            Dict with assignment statistics
        """
        fields_with_exact = sum(1 for a in field_assignments.values() if a['match_type'] == 'exact')
        fields_with_buffer = sum(1 for a in field_assignments.values() if a['match_type'] == 'buffer')
        fields_with_no_matches = sum(1 for a in field_assignments.values() if a['match_type'] == 'none')
        
        total_volume_assigned = sum(a['total_volume'] for a in field_assignments.values())
        
        return {
            'total_fields_processed': len(fields),
            'fields_with_exact_matches': fields_with_exact,
            'fields_with_buffer_matches': fields_with_buffer,
            'fields_with_no_matches': fields_with_no_matches,
            'total_flares_processed': len(candidate_flares),
            'total_flares_assigned': len(assigned_flare_ids),
            'total_volume_assigned': total_volume_assigned,
            'unassigned_flares': len(candidate_flares) - len(assigned_flare_ids)
        }

    @staticmethod
    def _generate_assignment_csv(
        field_assignments: Dict[int, Dict],
        fields: List[PyxisFieldMeta],
        candidate_flares: List[Flare],
        start_date: date,
        end_date: date
    ) -> str:
        """
        Generate CSV file with detailed assignment results.
        
        Args:
            field_assignments: Field assignment results
            fields: List of target fields
            candidate_flares: List of candidate flares
            start_date: Query start date
            end_date: Query end date
            
        Returns:
            Path to generated CSV file
        """
        # Create flare lookup for efficiency
        flare_lookup = {f.flare_id: f for f in candidate_flares}
        
        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"flare_assignment_{timestamp}.csv"
        csv_path = get_data_path("assignments", filename)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        
        # Write CSV
        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'field_id', 'field_name', 'field_country', 'field_h3_index',
                'flare_id', 'flare_original_id', 'flare_lat', 'flare_lon', 
                'flare_h3_index', 'flare_volume', 'flare_valid_from', 'flare_valid_to',
                'match_type', 'query_start_date', 'query_end_date'
            ]
            
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            # Write assignment data
            for field_id, assignment in field_assignments.items():
                field = next(f for f in fields if f.id == field_id)
                
                # Write exact matches
                for flare_id in assignment['exact_match_flare_ids']:
                    flare = flare_lookup[flare_id]
                    writer.writerow({
                        'field_id': field.id,
                        'field_name': field.name,
                        'field_country': field.country,
                        'field_h3_index': field.centroid_h3_index,
                        'flare_id': flare.flare_id,
                        'flare_original_id': flare.original_id,
                        'flare_lat': flare.latitude,
                        'flare_lon': flare.longitude,
                        'flare_h3_index': flare.h3_index,
                        'flare_volume': flare.volume,
                        'flare_valid_from': flare.valid_from,
                        'flare_valid_to': flare.valid_to,
                        'match_type': 'exact',
                        'query_start_date': start_date,
                        'query_end_date': end_date
                    })
                
                # Write buffer matches
                for flare_id in assignment['buffer_match_flare_ids']:
                    flare = flare_lookup[flare_id]
                    writer.writerow({
                        'field_id': field.id,
                        'field_name': field.name,
                        'field_country': field.country,
                        'field_h3_index': field.centroid_h3_index,
                        'flare_id': flare.flare_id,
                        'flare_original_id': flare.original_id,
                        'flare_lat': flare.latitude,
                        'flare_lon': flare.longitude,
                        'flare_h3_index': flare.h3_index,
                        'flare_volume': flare.volume,
                        'flare_valid_from': flare.valid_from,
                        'flare_valid_to': flare.valid_to,
                        'match_type': 'buffer',
                        'query_start_date': start_date,
                        'query_end_date': end_date
                    })
        
        logger.info(f"Generated assignment CSV: {csv_path}")
        return csv_path

    @staticmethod
    def _calculate_assignment_statistics(
        fields: List[PyxisFieldMeta],
        candidate_flares: List[Flare],
        field_assignments: Dict[int, Dict],
        assigned_flare_ids: Set[str]
    ) -> Dict[str, Any]:
        """
        Calculate assignment statistics.
        
        Args:
            fields: List of target fields
            candidate_flares: List of candidate flares
            field_assignments: Field assignment results
            assigned_flare_ids: Set of assigned flare IDs
            
        Returns:
            Dict with assignment statistics
        """
        fields_with_exact = sum(1 for a in field_assignments.values() if a['match_type'] == 'exact')
        fields_with_buffer = sum(1 for a in field_assignments.values() if a['match_type'] == 'buffer')
        fields_with_no_matches = sum(1 for a in field_assignments.values() if a['match_type'] == 'none')
        
        total_volume_assigned = sum(a['total_volume'] for a in field_assignments.values())
        
        return {
            'total_fields_processed': len(fields),
            'fields_with_exact_matches': fields_with_exact,
            'fields_with_buffer_matches': fields_with_buffer,
            'fields_with_no_matches': fields_with_no_matches,
            'total_flares_processed': len(candidate_flares),
            'total_flares_assigned': len(assigned_flare_ids),
            'total_volume_assigned': total_volume_assigned,
            'unassigned_flares': len(candidate_flares) - len(assigned_flare_ids)
        }

    @staticmethod
    def _generate_assignment_csv(
        field_assignments: Dict[int, Dict],
        fields: List[PyxisFieldMeta],
        candidate_flares: List[Flare],
        start_date: date,
        end_date: date
    ) -> str:
        """
        Generate CSV file with detailed assignment results.
        
        Args:
            field_assignments: Field assignment results
            fields: List of target fields
            candidate_flares: List of candidate flares
            start_date: Query start date
            end_date: Query end date
            
        Returns:
            Path to generated CSV file
        """
        # Create flare lookup for efficiency
        flare_lookup = {f.flare_id: f for f in candidate_flares}
        
        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"flare_assignment_{timestamp}.csv"
        csv_path = get_data_path("assignments", filename)
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        
        # Write CSV
        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'field_id', 'field_name', 'field_country', 'field_h3_index',
                'flare_id', 'flare_original_id', 'flare_lat', 'flare_lon', 
                'flare_h3_index', 'flare_volume', 'flare_valid_from', 'flare_valid_to',
                'match_type', 'query_start_date', 'query_end_date'
            ]
            
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            # Write assignment data
            for field_id, assignment in field_assignments.items():
                field = next(f for f in fields if f.id == field_id)
                
                # Write exact matches
                for flare_id in assignment['exact_match_flare_ids']:
                    flare = flare_lookup[flare_id]
                    writer.writerow({
                        'field_id': field.id,
                        'field_name': field.name,
                        'field_country': field.country,
                        'field_h3_index': field.centroid_h3_index,
                        'flare_id': flare.flare_id,
                        'flare_original_id': flare.original_id,
                        'flare_lat': flare.latitude,
                        'flare_lon': flare.longitude,
                        'flare_h3_index': flare.h3_index,
                        'flare_volume': flare.volume,
                        'flare_valid_from': flare.valid_from,
                        'flare_valid_to': flare.valid_to,
                        'match_type': 'exact',
                        'query_start_date': start_date,
                        'query_end_date': end_date
                    })
                
                # Write buffer matches
                for flare_id in assignment['buffer_match_flare_ids']:
                    flare = flare_lookup[flare_id]
                    writer.writerow({
                        'field_id': field.id,
                        'field_name': field.name,
                        'field_country': field.country,
                        'field_h3_index': field.centroid_h3_index,
                        'flare_id': flare.flare_id,
                        'flare_original_id': flare.original_id,
                        'flare_lat': flare.latitude,
                        'flare_lon': flare.longitude,
                        'flare_h3_index': flare.h3_index,
                        'flare_volume': flare.volume,
                        'flare_valid_from': flare.valid_from,
                        'flare_valid_to': flare.valid_to,
                        'match_type': 'buffer',
                        'query_start_date': start_date,
                        'query_end_date': end_date
                    })
        
        logger.info(f"Generated assignment CSV: {csv_path}")
        return csv_path