"""
Service for generating OPGEE-compatible input data.
"""

import csv
import os
import logging
from datetime import datetime, date
from typing import Dict, Any, List, Tuple, Optional

import logfire
from sqlalchemy.orm import Session

from app.postgres.models.pyxis_field import PyxisFieldMeta, PyxisFieldData
from app.postgres.models.data_entry import DataEntry
from app.postgres.models.data_source import DataSourceMeta, SourceType
from app.services.flare_service import FlareService
from app.schemas.flare import FlareAssignmentConfig
from app.utils.merge_utils import merge_specific_attributes
from app.utils.path_util import get_data_path


logger = logging.getLogger(__name__)


class OpgeeService:
    """Service for generating OPGEE input data"""

    @staticmethod
    @logfire.instrument("Generate OPGEE input for time range {start_date} to {end_date}")
    def generate_opgee_input(
        start_date: date,
        end_date: date,
        db: Session,
        field_ids: Optional[List[int]] = None,
        country: Optional[str] = None,
        flare_config: FlareAssignmentConfig = FlareAssignmentConfig(),
        csv_output_path: Optional[str] = None,
        require_multi_source_coverage: bool = True,
        min_source_coverage_ratio: float = 0.5,
        trusted_source_types: List[SourceType] = None
    ) -> Tuple[Dict[str, Any], Optional[str]]:
        """
        Generate OPGEE-compatible input by merging field data and integrating flare assignments.
        
        Args:
            start_date: Start date for time range filter
            end_date: End date for time range filter
            db: Database session
            field_ids: Optional list of specific field IDs
            country: Optional country filter for fields
            flare_config: Configuration for flare assignment
            csv_output_path: Optional path to save CSV file
            require_multi_source_coverage: Filter fields by source coverage
            min_source_coverage_ratio: Minimum ratio of sources required (0.0-1.0)
            trusted_source_types: Source types that bypass coverage requirements
            
        Returns:
            Tuple of (statistics_dict, csv_file_path_or_none)
        """
        start_time = datetime.now()
        
        # Set default trusted source types
        if trusted_source_types is None:
            trusted_source_types = [SourceType.GOVERNMENT]
        
        # Validate inputs
        if start_date > end_date:
            raise ValueError("start_date must be before or equal to end_date")
        
        logger.info(f"Starting OPGEE input generation for {start_date} to {end_date}")
        
        # Step 1: Get target fields
        with logfire.span("Get target fields"):
            fields = OpgeeService._get_target_fields(db, field_ids, country)
            if not fields:
                raise ValueError("No fields found matching the criteria")
            
            logger.info(f"Found {len(fields)} initial fields")
        
        # Step 1.5: Apply source coverage filter BEFORE flare assignment
        source_filter_stats = {}
        if require_multi_source_coverage:
            with logfire.span("Filter fields by source coverage"):
                fields, source_filter_stats = OpgeeService._filter_fields_by_source_coverage(
                    fields, db, min_source_coverage_ratio, trusted_source_types
                )
                if not fields:
                    raise ValueError("No fields remaining after source coverage filtering")
                
                logger.info(f"After source filtering: {len(fields)} fields remaining")
        
        # Step 2: Assign flares to fields (calculation only)
        with logfire.span("Assign flares to fields"):
            flare_stats, field_flare_assignments = FlareService.assign_flares_to_fields_calculation(
                start_date=start_date,
                end_date=end_date,
                db=db,
                field_ids=[f.id for f in fields],  # Use filtered field IDs
                country=None,  # Don't filter by country again
                proximity_distance_km=flare_config.proximity_distance_km,
                buffer_distance_km=flare_config.buffer_distance_km
            )
            
            logger.info(f"Flare assignment completed: {flare_stats['total_flares_assigned']} flares assigned")
        
        # Step 3: Process each field
        with logfire.span("Process field data and calculate FOR"):
            opgee_data = []
            fields_with_data = 0
            fields_with_flare = 0
            
            for field in fields:
                field_result = OpgeeService._process_single_field(
                    field, start_date, end_date, db, field_flare_assignments
                )
                
                if field_result:
                    opgee_data.append(field_result)
                    fields_with_data += 1
                    
                    if field_result.get('for_value', 0) > 0:
                        fields_with_flare += 1
        
        # Step 4: Generate CSV if requested
        csv_file_path = None
        if csv_output_path:
            with logfire.span("Generate CSV output"):
                csv_file_path = OpgeeService._generate_csv_output(
                    opgee_data, csv_output_path, start_date, end_date
                )
        
        # Step 5: Calculate final statistics
        processing_time = (datetime.now() - start_time).total_seconds()
        
        statistics = {
            'total_fields_processed': len(fields),
            'fields_with_data': fields_with_data,
            'fields_with_flare_assignment': fields_with_flare,
            'total_flare_volume_assigned': flare_stats.get('total_volume_assigned', 0.0),
            'processing_time_seconds': processing_time,
            'fields_with_exact_flare_matches': flare_stats.get('fields_with_exact_matches', 0),
            'fields_with_buffer_flare_matches': flare_stats.get('fields_with_buffer_matches', 0),
            'fields_with_no_flare_matches': flare_stats.get('fields_with_no_matches', 0)
        }
        
        # Add source filtering statistics if filtering was applied
        if require_multi_source_coverage and source_filter_stats:
            statistics.update({
                'total_fields_before_source_filtering': source_filter_stats.get('total_before_filtering'),
                'fields_filtered_by_source_coverage': source_filter_stats.get('filtered_out_count'),
                'fields_with_trusted_source_exception': source_filter_stats.get('trusted_exception_count'),
                'contributing_sources_count': source_filter_stats.get('contributing_sources_count')
            })
        
        logger.info(f"OPGEE input generation completed in {processing_time:.2f} seconds")
        
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
    def _filter_fields_by_source_coverage(
        fields: List[PyxisFieldMeta],
        db: Session,
        min_coverage_ratio: float,
        trusted_source_types: List[SourceType]
    ) -> Tuple[List[PyxisFieldMeta], Dict[str, Any]]:
        """
        Filter fields based on source coverage requirements.
        
        Args:
            fields: List of PyxisFieldMeta objects to filter
            db: Database session
            min_coverage_ratio: Minimum ratio of sources required (0.0-1.0)
            trusted_source_types: Source types that bypass coverage requirements
            
        Returns:
            Tuple of (filtered_fields, filter_statistics)
        """
        if not fields:
            return [], {}
        
        logger.info(f"Applying source coverage filter to {len(fields)} fields")
        
        # Batch query: Get all field-to-source mappings at once
        field_source_mapping = db.query(
            PyxisFieldData.pyxis_field_meta_id,
            DataEntry.source_id,
            DataSourceMeta.source_type
        ).join(
            DataEntry, PyxisFieldData.data_entry_id == DataEntry.id
        ).join(
            DataSourceMeta, DataEntry.source_id == DataSourceMeta.id
        ).filter(
            PyxisFieldData.pyxis_field_meta_id.in_([f.id for f in fields])
        ).distinct().all()
        
        # Get total count of sources that have contributed field data
        contributing_source_ids = set(mapping.source_id for mapping in field_source_mapping)
        total_contributing_sources = len(contributing_source_ids)
        
        logger.info(f"Found {total_contributing_sources} sources contributing field data")
        
        if total_contributing_sources == 0:
            logger.warning("No sources found contributing field data")
            return [], {
                'total_before_filtering': len(fields),
                'filtered_out_count': len(fields),
                'trusted_exception_count': 0,
                'coverage_passed_count': 0,
                'contributing_sources_count': 0
            }
        
        # Group by field_id
        field_sources = {}
        for mapping in field_source_mapping:
            field_id = mapping.pyxis_field_meta_id
            if field_id not in field_sources:
                field_sources[field_id] = {
                    'source_ids': set(),
                    'source_types': set()
                }
            field_sources[field_id]['source_ids'].add(mapping.source_id)
            field_sources[field_id]['source_types'].add(mapping.source_type)
        
        # Filter fields
        filtered_fields = []
        stats = {
            'total_before_filtering': len(fields),
            'trusted_exception_count': 0,
            'coverage_passed_count': 0,
            'filtered_out_count': 0,
            'contributing_sources_count': total_contributing_sources
        }
        
        for field in fields:
            field_info = field_sources.get(field.id, {'source_ids': set(), 'source_types': set()})
            
            # Check trusted source exception
            has_trusted_source = any(
                source_type in trusted_source_types 
                for source_type in field_info['source_types']
            )
            
            if has_trusted_source:
                filtered_fields.append(field)
                stats['trusted_exception_count'] += 1
                continue
            
            # Check coverage ratio
            source_count = len(field_info['source_ids'])
            coverage_ratio = source_count / total_contributing_sources if total_contributing_sources > 0 else 0
            
            if coverage_ratio >= min_coverage_ratio:
                filtered_fields.append(field)
                stats['coverage_passed_count'] += 1
            else:
                stats['filtered_out_count'] += 1
                logger.debug(
                    f"Field {field.id} filtered out: {source_count}/{total_contributing_sources} "
                    f"sources ({coverage_ratio:.2f} < {min_coverage_ratio})"
                )
        
        logger.info(
            f"Source coverage filter: {stats['total_before_filtering']} → {len(filtered_fields)} fields "
            f"({stats['trusted_exception_count']} trusted exception, "
            f"{stats['coverage_passed_count']} coverage passed, "
            f"{stats['filtered_out_count']} filtered out)"
        )
        
        return filtered_fields, stats

    @staticmethod
    def _process_single_field(
        field: PyxisFieldMeta,
        start_date: date,
        end_date: date,
        db: Session,
        field_flare_assignments: Dict[int, Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Process a single field to generate OPGEE input data.
        
        Args:
            field: PyxisFieldMeta object
            start_date: Start date for time range
            end_date: End date for time range
            db: Database session
            field_flare_assignments: Dict mapping field_id to flare assignment results
            
        Returns:
            Dict with OPGEE input data for the field, or None if no data
        """
        # Get all PyxisFieldData records for this field
        field_data_records = db.query(PyxisFieldData).filter(
            PyxisFieldData.pyxis_field_meta_id == field.id
        ).all()
        
        if not field_data_records:
            logger.warning(f"No field data found for field {field.id}")
            # Still create entry with basic info and flare data
            return OpgeeService._create_basic_field_entry(field, start_date, end_date, field_flare_assignments)
        
        # Merge all attributes using time-weighted processing
        merged_attributes = merge_specific_attributes(
            field_data_records=field_data_records,
            attributes=OpgeeService._get_opgee_attributes(),
            query_start=start_date,
            query_end=end_date
        )
        
        # Add pyxis_field_code at the beginning
        result = {
            'pyxis_field_code': field.pyxis_field_code
        }
        
        # Add merged attributes
        result.update(merged_attributes)
        
        # Calculate and add FOR (Flaring-to-Oil Ratio)
        flare_volume = field_flare_assignments.get(field.id, {}).get('total_volume', 0.0)
        for_value = OpgeeService._calculate_for(
            flare_volume, 
            merged_attributes.get('oil_prod', 0), 
            start_date, 
            end_date
        )
        result['for_value'] = for_value
        
        return result

    @staticmethod
    def _create_basic_field_entry(
        field: PyxisFieldMeta,
        start_date: date,
        end_date: date,
        field_flare_assignments: Dict[int, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Create a basic field entry when no PyxisFieldData is available.
        
        Args:
            field: PyxisFieldMeta object
            start_date: Start date for time range
            end_date: End date for time range
            field_flare_assignments: Dict mapping field_id to flare assignment results
            
        Returns:
            Dict with basic field info and calculated FOR
        """
        flare_volume = field_flare_assignments.get(field.id, {}).get('total_volume', 0.0)
        for_value = OpgeeService._calculate_for(flare_volume, 0, start_date, end_date)
        
        return {
            'pyxis_field_code': field.pyxis_field_code,
            'for_value': for_value
        }

    @staticmethod
    def _calculate_for(
        flare_volume_bcm: float, 
        oil_prod_bbl_per_day: Optional[float], 
        start_date: date, 
        end_date: date
    ) -> float:
        """
        Calculate Flaring-to-Oil Ratio (FOR) in scf/bbl_oil.
        
        Args:
            flare_volume_bcm: Flare volume in billion cubic meters
            oil_prod_bbl_per_day: Oil production in barrels per day
            start_date: Start date of period
            end_date: End date of period
            
        Returns:
            FOR value in scf/bbl_oil
        """
        if not oil_prod_bbl_per_day:
            oil_prod_bbl_per_day = 1.0  # Use pseudo value to avoid division by zero
        
        # Calculate days in range
        days_in_range = (end_date - start_date).days + 1
        
        # Convert BCM to SCF: 1 BCM = 35.3147 billion SCF
        flare_volume_scf = flare_volume_bcm * 35.3147e9
        
        # Calculate total oil production over the period
        total_oil_prod_bbl = oil_prod_bbl_per_day * days_in_range
        
        # Calculate FOR: scf_flare / bbl_oil
        if total_oil_prod_bbl > 0:
            for_value = flare_volume_scf / total_oil_prod_bbl
        else:
            for_value = 0.0
        
        return for_value

    @staticmethod
    def _get_opgee_attributes() -> List[str]:
        """
        Get list of all OPGEE-compatible attributes to merge in the order defined in rules.
        
        Returns:
            List of attribute names in the order from OPGEE_cols_merge_rules.json
        """
        from app.utils.merge_utils import load_merge_rules
        
        merge_rules = load_merge_rules()
        # Return attributes in the same order as defined in the JSON file
        return list(merge_rules.keys())

    @staticmethod
    def _generate_csv_output(
        opgee_data: List[Dict[str, Any]],
        output_path: str,
        start_date: date,
        end_date: date
    ) -> str:
        """
        Generate CSV file with OPGEE input data in the order of OPGEE rules.
        
        Args:
            opgee_data: List of field data dictionaries
            output_path: Path to save CSV file
            start_date: Query start date
            end_date: Query end date
            
        Returns:
            Path to generated CSV file
        """
        if not opgee_data:
            raise ValueError("No data to write to CSV")
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Get ordered column names: pyxis_field_code first, then OPGEE attributes in order
        opgee_attributes = OpgeeService._get_opgee_attributes()
        fieldnames = ['pyxis_field_code'] + opgee_attributes
        
        # Write CSV
        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for record in opgee_data:
                # Ensure all fields have values (fill with empty string if missing)
                complete_record = {field: record.get(field, '') for field in fieldnames}
                writer.writerow(complete_record)
        
        logger.info(f"Generated OPGEE CSV file: {output_path} with {len(opgee_data)} records")
        return output_path