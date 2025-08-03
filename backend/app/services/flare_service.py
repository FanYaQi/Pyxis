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

    @staticmethod
    def assign_flares_to_fields(
        start_date: date,
        end_date: date,
        db: Session,
        field_ids: Optional[List[int]] = None,
        country: Optional[str] = None,
        proximity_distance_km: float = 100.0,
        buffer_distance_km: float = 5.0,
        csv_output_path: Optional[str] = None,
        allocation_strategy: str = "production_weighted"
    ) -> Tuple[Dict[str, Any], Dict[int, Dict[str, Any]], Optional[str]]:
        """
        Assign flares to fields using field-centric approach with flexible allocation strategies.
        """
        from app.schemas.flare import FlareAllocationStrategy
        from app.utils.merge_utils import merge_specific_attributes
        
        start_time = datetime.now()
        
        # Validate inputs
        if start_date > end_date:
            raise ValueError("start_date must be before or equal to end_date")
        
        # Convert string to enum
        try:
            allocation_strategy_enum = FlareAllocationStrategy(allocation_strategy)
        except ValueError:
            allocation_strategy_enum = FlareAllocationStrategy.PRODUCTION_WEIGHTED
        
        # Step 1: Get target fields
        fields = FlareService._get_target_fields(db, field_ids, country)
        if not fields:
            raise ValueError("No fields found matching the criteria")
        
        logger.info(f"Processing {len(fields)} fields for flare assignment using {allocation_strategy_enum.value} strategy")
        
        # Step 2: Get production data if needed for production-weighted allocation
        field_production_data = {}
        if allocation_strategy_enum == FlareAllocationStrategy.PRODUCTION_WEIGHTED:
            field_production_data = FlareService._get_field_production_data(
                fields, start_date, end_date, db
            )
            logger.info(f"Retrieved production data for {len(field_production_data)} fields")
        
        # Step 3: For each field, find its candidate flares and matches
        field_flare_matches = {}
        total_candidate_flares = 0
        
        for field in fields:
            # Get candidate flares for THIS field only
            field_candidates = FlareService._get_candidate_flares_for_field(
                field, start_date, end_date, proximity_distance_km, db
            )
            
            total_candidate_flares += len(field_candidates)
            
            # Check matches for this field
            exact_flares = []
            buffer_flares = []
            
            for flare in field_candidates:
                if field.geometry and FlareUtils.validate_geometry(field.geometry):
                    if FlareUtils.point_in_geometry(flare.latitude, flare.longitude, field.geometry):
                        exact_flares.append(flare)
                    else:
                        # Check buffer match only if no exact match
                        buffered_geometry = FlareUtils.create_buffer_geometry(field.geometry, buffer_distance_km)
                        if buffered_geometry and FlareUtils.point_in_buffer_geometry(flare.latitude, flare.longitude, buffered_geometry):
                            buffer_flares.append(flare)
            
            field_flare_matches[field.id] = {
                'exact': exact_flares,
                'buffer': buffer_flares
            }
            
            logger.debug(f"Field {field.id}: {len(exact_flares)} exact, {len(buffer_flares)} buffer matches")
        
        logger.info(f"Found {total_candidate_flares} total candidate flares across all fields")
        
        # Step 4: Build flare competition map (flare_id -> competing_fields_info)
        flare_competition = FlareService._build_flare_competition_map(field_flare_matches)
        logger.info(f"Built competition map for {len(flare_competition)} flares")
        
        # Step 5: Apply allocation strategy
        field_assignments, stats = FlareService._allocate_by_competition(
            flare_competition, allocation_strategy_enum, field_production_data, fields
        )
        
        # Step 6: Finalize statistics
        processing_time = (datetime.now() - start_time).total_seconds()
        stats['processing_time_seconds'] = processing_time
        
        logger.info(f"Flare assignment completed in {processing_time:.2f} seconds")
        
        # Step 7: Generate CSV if requested
        csv_file_path = None
        if csv_output_path:
            csv_file_path = FlareService._generate_assignment_csv(
                field_assignments, fields, start_date, end_date, csv_output_path
            )
        
        return stats, field_assignments, csv_file_path

    @staticmethod
    def _get_candidate_flares_for_field(
        field: PyxisFieldMeta,
        start_date: date,
        end_date: date,
        proximity_distance_km: float,
        db: Session
    ) -> List[Flare]:
        """
        Get candidate flares for a specific field using H3 proximity and time range.
        """
        if not field.centroid_h3_index:
            logger.debug(f"Field {field.id} has no H3 index, skipping")
            return []
        
        # Get H3 indices around this field only
        h3_indices = FlareUtils.get_h3_k_ring_for_distance(
            field.centroid_h3_index, proximity_distance_km, flare_res
        )
        
        if not h3_indices:
            return []
        
        logger.debug(f"Field {field.id}: searching {len(h3_indices)} H3 indices")
        
        # Query flares for this field's H3 indices
        candidate_flares = db.query(Flare).filter(
            and_(
                Flare.h3_index.in_(h3_indices),
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
    def _get_field_production_data(
        fields: List[PyxisFieldMeta],
        start_date: date,
        end_date: date,
        db: Session
    ) -> Dict[int, float]:
        """
        Get oil production data for fields using merge utilities.
        """
        from app.utils.merge_utils import merge_specific_attributes
        
        field_production_data = {}
        
        for field in fields:
            # Get all PyxisFieldData records for this field
            field_data_records = db.query(PyxisFieldData).filter(
                PyxisFieldData.pyxis_field_meta_id == field.id
            ).all()
            
            if field_data_records:
                # Merge oil_prod attribute for time range
                merged_attributes = merge_specific_attributes(
                    field_data_records=field_data_records,
                    attributes=['oil_prod'],
                    query_start=start_date,
                    query_end=end_date
                )
                
                oil_prod = merged_attributes.get('oil_prod')
                if oil_prod is not None and oil_prod > 0:
                    field_production_data[field.id] = float(oil_prod)
                else:
                    field_production_data[field.id] = 1.0  # Default value
                    logger.debug(f"Field {field.id}: Using default oil_prod=1.0")
            else:
                field_production_data[field.id] = 1.0  # Default value
                logger.debug(f"Field {field.id}: No data records, using default oil_prod=1.0")
        
        return field_production_data

    @staticmethod
    def _build_flare_competition_map(
        field_flare_matches: Dict[int, Dict[str, List[Flare]]]
    ) -> Dict[str, Dict]:
        """
        Build a map of flare_id -> competing fields info.
        """
        flare_competition = {}
        
        # Build flare_id -> {exact_fields: [], buffer_fields: [], flare_object: flare}
        for field_id, matches in field_flare_matches.items():
            # Process exact matches
            for flare in matches['exact']:
                if flare.flare_id not in flare_competition:
                    flare_competition[flare.flare_id] = {
                        'exact_fields': [],
                        'buffer_fields': [],
                        'flare_object': flare
                    }
                flare_competition[flare.flare_id]['exact_fields'].append(field_id)
            
            # Process buffer matches
            for flare in matches['buffer']:
                if flare.flare_id not in flare_competition:
                    flare_competition[flare.flare_id] = {
                        'exact_fields': [],
                        'buffer_fields': [],
                        'flare_object': flare
                    }
                flare_competition[flare.flare_id]['buffer_fields'].append(field_id)
        
        return flare_competition

    @staticmethod 
    def _allocate_by_competition(
        flare_competition: Dict[str, Dict],
        allocation_strategy: 'FlareAllocationStrategy',
        field_production_data: Dict[int, float],
        fields: List[PyxisFieldMeta]
    ) -> Tuple[Dict[int, Dict[str, Any]], Dict[str, Any]]:
        """
        Allocate flares based on competition rules and allocation strategy.
        """
        from app.schemas.flare import FlareAllocationStrategy
        
        # Initialize field assignments
        field_assignments = {}
        for field in fields:
            field_assignments[field.id] = {
                'field_id': field.id,
                'field_name': field.name,
                'exact_match_flare_ids': [],
                'buffer_match_flare_ids': [],
                'exact_volume': 0.0,
                'buffer_volume': 0.0,
                'total_volume': 0.0,
                'match_type': 'none'
            }
        
        # Initialize statistics
        stats = {
            'total_fields_processed': len(fields),
            'fields_with_exact_matches': 0,
            'fields_with_buffer_matches': 0,
            'fields_with_no_matches': 0,
            'total_flare_volume_assigned': 0.0,
            'total_flares_assigned': 0
        }
        
        # Process each flare
        for flare_id, competition_info in flare_competition.items():
            flare = competition_info['flare_object']
            exact_fields = competition_info['exact_fields']
            buffer_fields = competition_info['buffer_fields']
            
            # Apply competition rules: exact takes priority
            if exact_fields:
                competing_field_ids = exact_fields
                match_type = 'exact'
            elif buffer_fields:
                competing_field_ids = buffer_fields
                match_type = 'buffer'
            else:
                continue  # No matches
            
            # Apply allocation strategy
            if len(competing_field_ids) == 1:
                # No competition, assign entire flare
                allocated_volumes = {competing_field_ids[0]: flare.volume}
            else:
                # Competition exists, apply strategy
                if allocation_strategy == FlareAllocationStrategy.PRODUCTION_WEIGHTED:
                    allocated_volumes = FlareService._allocate_by_production(
                        flare.volume, competing_field_ids, field_production_data
                    )
                else:  # EQUAL_SPLIT
                    allocated_volumes = FlareService._allocate_equally(
                        flare.volume, competing_field_ids
                    )
            
            # Update field assignments
            for field_id, allocated_volume in allocated_volumes.items():
                if match_type == 'exact':
                    field_assignments[field_id]['exact_match_flare_ids'].append(flare_id)
                    field_assignments[field_id]['exact_volume'] += allocated_volume
                else:  # buffer
                    field_assignments[field_id]['buffer_match_flare_ids'].append(flare_id)
                    field_assignments[field_id]['buffer_volume'] += allocated_volume
                
                field_assignments[field_id]['total_volume'] += allocated_volume
                stats['total_flare_volume_assigned'] += allocated_volume
        
        # Update field match types and statistics
        for field_id, assignment in field_assignments.items():
            if assignment['exact_volume'] > 0:
                assignment['match_type'] = 'exact'
                stats['fields_with_exact_matches'] += 1
            elif assignment['buffer_volume'] > 0:
                assignment['match_type'] = 'buffer'
                stats['fields_with_buffer_matches'] += 1
            else:
                stats['fields_with_no_matches'] += 1
        
        stats['total_flares_assigned'] = len(flare_competition)
        
        return field_assignments, stats

    @staticmethod
    def _allocate_by_production(
        flare_volume: float,
        competing_field_ids: List[int],
        field_production_data: Dict[int, float]
    ) -> Dict[int, float]:
        """
        Allocate flare volume proportionally based on oil production.
        """
        total_production = sum(field_production_data.get(field_id, 1.0) for field_id in competing_field_ids)
        
        if total_production <= 0:
            # Fallback to equal split if no production data
            return FlareService._allocate_equally(flare_volume, competing_field_ids)
        
        allocated_volumes = {}
        for field_id in competing_field_ids:
            field_production = field_production_data.get(field_id, 1.0)
            allocation_ratio = field_production / total_production
            allocated_volumes[field_id] = flare_volume * allocation_ratio
        
        return allocated_volumes

    @staticmethod
    def _allocate_equally(
        flare_volume: float,
        competing_field_ids: List[int]
    ) -> Dict[int, float]:
        """
        Allocate flare volume equally among competing fields.
        """
        volume_per_field = flare_volume / len(competing_field_ids)
        return {field_id: volume_per_field for field_id in competing_field_ids}

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
    def _generate_assignment_csv(
        field_assignments: Dict[int, Dict],
        fields: List[PyxisFieldMeta],
        start_date: date,
        end_date: date,
        output_path: str
    ) -> str:
        """
        Generate CSV file with flare assignment results.
        
        Args:
            field_assignments: Field assignment results
            fields: List of target fields
            start_date: Query start date
            end_date: Query end date
            output_path: Local file path to save CSV
            
        Returns:
            File path where CSV was saved
        """
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Write CSV
            with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = [
                    'field_id', 'field_name', 'field_country', 
                    'flare_sum', 'query_start_date', 'query_end_date'
                ]
                
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                # Write aggregated data for each field
                for field_id, assignment in field_assignments.items():
                    field = next(f for f in fields if f.id == field_id)
                    
                    writer.writerow({
                        'field_id': field.id,
                        'field_name': field.name or '',
                        'field_country': field.country or '',
                        'flare_sum': assignment['total_volume'],
                        'query_start_date': start_date,
                        'query_end_date': end_date
                    })
            
            logger.info(f"Generated flare assignment CSV: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Error generating CSV file: {str(e)}")
            raise ValueError(f"Failed to write CSV to {output_path}: {str(e)}")