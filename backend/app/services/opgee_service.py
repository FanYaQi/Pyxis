"""
Service for generating OPGEE-compatible input data.
Updated with new flow: merge first, then assign flares, then calculate FOR.
"""

import csv
import os
import logging
from datetime import datetime, date
from typing import Dict, Any, List, Tuple, Optional

import logfire
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.postgres.models.pyxis_field import PyxisFieldMeta, PyxisFieldData
from app.postgres.models.data_entry import DataEntry
from app.postgres.models.data_source import DataSourceMeta, SourceType
from app.services.flare_service import FlareService
from app.schemas.flare import FlareAssignmentConfig
from app.utils.merge_utils import merge_specific_attributes
from app.utils.path_util import get_data_path


logger = logging.getLogger(__name__)


class OpgeeService:
    """Service for generating OPGEE input data with improved flow"""

    @staticmethod
    @logfire.instrument("Generate OPGEE input for time range {start_date} to {end_date}")
    def generate_opgee_input(
        start_date: date,
        end_date: date,
        db: Session,
        field_ids: Optional[List[int]] = None,
        country: Optional[str] = None,
        production_type: Optional[str] = None,
        flare_config: FlareAssignmentConfig = FlareAssignmentConfig(),
        csv_output_path: Optional[str] = None,
        require_multi_source_coverage: bool = True,
        min_source_coverage_ratio: float = 0.5,
        trusted_source_types: List[SourceType] = None,
        debug_mode: bool = False
    ) -> Tuple[Dict[str, Any], Optional[str]]:
        """
        Generate OPGEE-compatible input with NEW FLOW:
        1. Get fields and apply source filtering
        2. Merge field data for each filtered field
        3. Assign flares using original field geometries  
        4. Calculate FOR using merged oil_prod + assigned flare volumes
        5. Generate final CSV output
        
        Args:
            start_date: Start date for time range filter
            end_date: End date for time range filter
            db: Database session
            field_ids: Optional list of specific field IDs
            country: Optional country filter for fields
            production_type: Optional filter for fields by production type ("oil" or "gas")
            flare_config: Configuration for flare assignment
            csv_output_path: Optional path to save CSV file
            require_multi_source_coverage: Filter fields by source coverage
            min_source_coverage_ratio: Minimum ratio of sources required (0.0-1.0)
            trusted_source_types: Source types that bypass coverage requirements
            debug_mode: Enable detailed logging for debugging
            
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
        
        if production_type is not None and production_type not in ["oil", "gas"]:
            raise ValueError("production_type must be 'oil' or 'gas'")
        
        logger.info(f"Starting OPGEE input generation for {start_date} to {end_date} "
                   f"(production_type={production_type}, debug={debug_mode})")
        
        # Step 1: Get target fields
        with logfire.span("Get target fields"):
            fields = OpgeeService._get_target_fields(db, field_ids, country, production_type)
            if not fields:
                raise ValueError("No fields found matching the criteria")
            
            logger.info(f"STEP 1 - Initial field retrieval:")
            logger.info(f"  - Total fields found: {len(fields)}")
            logger.info(f"  - Filters applied: field_ids={bool(field_ids)}, country={country}, production_type={production_type}")
            
            # Debug: Show functional_unit distribution for retrieved fields
            if fields and debug_mode:
                field_ids_for_debug = [f.id for f in fields]
                functional_unit_dist = db.query(
                    PyxisFieldData.functional_unit, 
                    func.count(PyxisFieldData.pyxis_field_meta_id.distinct()).label('field_count')
                ).filter(
                    PyxisFieldData.pyxis_field_meta_id.in_(field_ids_for_debug)
                ).group_by(PyxisFieldData.functional_unit).all()
                
                func_unit_dict = {row[0] or 'NULL': row[1] for row in functional_unit_dist}
                logger.info(f"  - Functional unit distribution: {func_unit_dict}")
            
        # Step 2: Apply source coverage filter
        source_filter_stats = {}
        fields_before_source_filter = len(fields)
        
        if require_multi_source_coverage:
            with logfire.span("Filter fields by source coverage"):
                logger.info(f"STEP 2 - Source coverage filtering:")
                logger.info(f"  - Fields before filtering: {fields_before_source_filter}")
                logger.info(f"  - Min coverage ratio: {min_source_coverage_ratio}")
                logger.info(f"  - Trusted source types: {trusted_source_types}")
                
                fields, source_filter_stats = OpgeeService._filter_fields_by_source_coverage(
                    fields, db, min_source_coverage_ratio, trusted_source_types
                )
                
                logger.info(f"  - Fields after filtering: {len(fields)}")
                logger.info(f"  - Fields removed: {fields_before_source_filter - len(fields)}")
                logger.info(f"  - Trusted exceptions: {source_filter_stats.get('trusted_exception_count', 0)}")
                logger.info(f"  - Coverage passed: {source_filter_stats.get('coverage_passed_count', 0)}")
                
                if not fields:
                    raise ValueError("No fields remaining after source coverage filtering")
        else:
            logger.info(f"STEP 2 - Source coverage filtering SKIPPED (require_multi_source_coverage=False)")
            source_filter_stats = {
                'total_before_filtering': fields_before_source_filter,
                'filtered_out_count': 0,
                'trusted_exception_count': 0,
                'coverage_passed_count': fields_before_source_filter,
                'contributing_sources_count': 0
            }
    
        # Step 3: NEW - Merge field data FIRST (before flare assignment)
        with logfire.span("Merge field data for filtered fields"):
            logger.info(f"STEP 3 - Merging field data:")
            logger.info(f"  - Fields to merge: {len(fields)}")
            
            merged_field_data = OpgeeService._merge_field_data_for_fields(
                fields, start_date, end_date, db, debug_mode
            )
            
            fields_with_merged_data = len(merged_field_data)
            fields_without_data = len(fields) - fields_with_merged_data
            
            logger.info(f"  - Fields with merged data: {fields_with_merged_data}")
            logger.info(f"  - Fields without data: {fields_without_data}")
        
        # Step 3.5: Filter out fields with zero/null oil production for oil fields
        if production_type == "oil":
            with logfire.span("Filter fields by oil production volume"):
                logger.info(f"STEP 3.5 - Oil production filtering:")
                
                # Analyze oil production in merged data
                fields_before_oil_filter = len(fields)
                zero_oil_prod = 0
                null_oil_prod = 0
                positive_oil_prod = 0
                
                valid_field_ids = set()
                for field_id, merged_data in merged_field_data.items():
                    oil_prod = merged_data.get('oil_prod')
                    
                    if oil_prod is None:
                        null_oil_prod += 1
                    elif oil_prod <= 0:
                        zero_oil_prod += 1
                        logger.debug(f"Field {field_id}: oil_prod = {oil_prod} (filtered out)")
                    else:
                        positive_oil_prod += 1
                        valid_field_ids.add(field_id)
                
                # Filter fields and merged data
                fields = [f for f in fields if f.id in valid_field_ids]
                merged_field_data = {fid: data for fid, data in merged_field_data.items() if fid in valid_field_ids}
                
                fields_after_oil_filter = len(fields)
                fields_removed_oil = fields_before_oil_filter - fields_after_oil_filter
                
                logger.info(f"  - Fields before oil production filter: {fields_before_oil_filter}")
                logger.info(f"  - Fields with positive oil_prod: {positive_oil_prod}")
                logger.info(f"  - Fields with zero oil_prod: {zero_oil_prod}")
                logger.info(f"  - Fields with null oil_prod: {null_oil_prod}")
                logger.info(f"  - Fields after oil production filter: {fields_after_oil_filter}")
                logger.info(f"  - Fields removed by oil production filter: {fields_removed_oil}")
        
        # Step 4: Assign flares using original field geometries
        with logfire.span("Assign flares to filtered fields"):
            logger.info(f"STEP 4 - Flare assignment:")
            logger.info(f"  - Fields for flare assignment: {len(fields)}")
            logger.info(f"  - Proximity distance: {flare_config.proximity_distance_km}km")
            logger.info(f"  - Buffer distance: {flare_config.buffer_distance_km}km")
            
            flare_stats, field_flare_assignments, _ = FlareService.assign_flares_to_fields(
                start_date=start_date,
                end_date=end_date,
                db=db,
                field_ids=[f.id for f in fields],  # Use filtered field IDs
                proximity_distance_km=flare_config.proximity_distance_km,
                buffer_distance_km=flare_config.buffer_distance_km,
                allocation_strategy=flare_config.allocation_strategy.value  # Add this line
            )
            
            total_flares_assigned = flare_stats.get('total_flares_assigned', 0)
            fields_with_flares = len([f for f in field_flare_assignments.values() if f.get('total_volume', 0) > 0])
            
            logger.info(f"  - Total flares assigned: {total_flares_assigned}")
            logger.info(f"  - Fields with flare assignments: {fields_with_flares}")
            logger.info(f"  - Total flare volume assigned: {flare_stats.get('total_flare_volume_assigned', 0.0):.6f} BCM")
        
        # Step 5: Calculate FOR using merged oil_prod + assigned flare volumes
        with logfire.span("Calculate FOR from assignments and merged data"):
            merged_oil_prod_data = {
                field_id: merged_data.get('oil_prod') 
                for field_id, merged_data in merged_field_data.items()
            }
            
            for_values = OpgeeService.calculate_for_from_assignments(
                field_flare_assignments, merged_oil_prod_data, start_date, end_date
            )
            
            logger.info(f"Calculated FOR for {len(for_values)} fields")
        
        # Step 5.5: Calculate total flaring sum (production * FOR)
        with logfire.span("Calculate total flaring sum"):
            total_flaring_sum = 0.0
            days_in_range = (end_date - start_date).days + 1
            
            for field_id, for_value in for_values.items():
                merged_data = merged_field_data.get(field_id, {})
                oil_prod = merged_data.get('oil_prod', 1.0)  # Default to 1.0 if not found
                
                # Calculate total flaring: oil_prod (bbl/day) * days * FOR (scf/bbl) = total scf
                if oil_prod and oil_prod > 0 and for_value > 0:
                    field_flaring_scf = oil_prod * days_in_range * for_value
                    total_flaring_sum += field_flaring_scf
                    
                    logger.debug(f"Field {field_id}: {oil_prod} bbl/day * {days_in_range} days * {for_value:.6f} scf/bbl = {field_flaring_scf:.2f} scf")
            
            # Convert to more readable units (BCM - billion cubic meters)
            total_flaring_bcm = total_flaring_sum / 35.3147e9  # 1 BCM = 35.3147 billion SCF
            
            logger.info(f"Total flaring calculated: {total_flaring_sum:.2f} SCF ({total_flaring_bcm:.6f} BCM)")
        
        # Step 6: Generate final OPGEE data combining merged attributes + FOR
        with logfire.span("Generate final OPGEE data"):
            opgee_data = []
            fields_with_data = 0
            fields_with_flare = 0
            
            for field in fields:
                field_result = OpgeeService._create_final_field_record(
                    field, merged_field_data, for_values
                )
                
                if field_result:
                    opgee_data.append(field_result)
                    fields_with_data += 1
                    
                    if field_result.get('for_value', 0) > 0:
                        fields_with_flare += 1
            
            logger.info(f"Generated OPGEE data for {fields_with_data} fields, {fields_with_flare} with flares")
        
        # Step 7: Generate CSV if requested
        csv_file_path = None
        if csv_output_path:
            with logfire.span("Generate CSV output"):
                csv_file_path = OpgeeService._generate_csv_output(
                    opgee_data, csv_output_path, start_date, end_date
                )
        
        # Step 8: Calculate final statistics
        processing_time = (datetime.now() - start_time).total_seconds()
        
        statistics = {
            'total_fields_processed': len(fields),
            'fields_with_data': fields_with_data,
            'fields_with_flare_assignment': fields_with_flare,
            'total_flare_volume_assigned': flare_stats.get('total_flare_volume_assigned', 0.0),
            'total_flaring_sum_scf': round(total_flaring_sum, 2),
            'total_flaring_sum_bcm': round(total_flaring_bcm, 6),
            'production_type': production_type or "all",
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
        production_type_label = production_type or "all"
        
        # Calculate total fields filtered out
        initial_fields = source_filter_stats.get('total_before_filtering', len(fields))
        total_filtered_out = initial_fields - len(fields)
        
        logger.info(f"FINAL SUMMARY:")
        logger.info(f"  - Initial fields: {initial_fields}")
        logger.info(f"  - Final fields processed: {len(fields)} ({production_type_label})")
        logger.info(f"  - Total filtered out: {total_filtered_out}")
        logger.info(f"  - Fields with flare assignments: {fields_with_flare}")
        logger.info(f"  - Total flaring: {total_flaring_bcm:.6f} BCM")
        logger.info(f"  - Processing time: {processing_time:.2f} seconds")
        
        return statistics, csv_file_path

    @staticmethod
    def calculate_for_from_assignments(
        field_assignments: Dict[int, Dict[str, Any]],
        merged_oil_prod_data: Dict[int, Optional[float]], 
        start_date: date,
        end_date: date
    ) -> Dict[int, float]:
        """
        Calculate FOR values using flare assignments and merged oil production data.
        
        Args:
            field_assignments: Result from FlareService.assign_flares_to_fields()
            merged_oil_prod_data: field_id -> merged oil_prod (None allowed)
            start_date: Start date for calculation
            end_date: End date for calculation
            
        Returns:
            Dict mapping field_id -> for_value (scf/bbl_oil)
        """
        for_values = {}
        days_in_range = (end_date - start_date).days + 1
        
        for field_id, assignment in field_assignments.items():
            flare_volume_bcm = assignment.get('total_volume', 0.0)
            oil_prod = merged_oil_prod_data.get(field_id)
            
            # Handle null oil_prod with default value and logging
            if oil_prod is None or oil_prod <= 0:
                original_value = oil_prod
                oil_prod = 1.0  # Default value
                if field_id in merged_oil_prod_data:  # Was explicitly provided but None/zero
                    logger.warning(f"Field {field_id}: Using default oil_prod=1.0 (original was {original_value})")
            
            # Calculate FOR: Convert BCM to SCF, then divide by total oil production
            flare_volume_scf = flare_volume_bcm * 35.3147e9  # 1 BCM = 35.3147 billion SCF
            total_oil_prod_bbl = oil_prod * days_in_range
            for_value = flare_volume_scf / total_oil_prod_bbl if total_oil_prod_bbl > 0 else 0.0
            
            for_values[field_id] = for_value
            
            logger.debug(f"Field {field_id} FOR calculation: {flare_volume_bcm:.6f} BCM, "
                        f"{oil_prod} bbl/day, {days_in_range} days → {for_value:.6f} scf/bbl_oil")
            
        return for_values

    @staticmethod
    def _merge_field_data_for_fields(
        fields: List[PyxisFieldMeta],
        start_date: date,
        end_date: date,
        db: Session,
        debug_mode: bool = False
    ) -> Dict[int, Dict[str, Any]]:
        """
        Merge field data for each field using the existing merge utilities.
        
        Args:
            fields: List of filtered PyxisFieldMeta objects
            start_date: Start date for time filtering
            end_date: End date for time filtering
            db: Database session
            debug_mode: Enable debug logging
            
        Returns:
            Dict mapping field_id -> merged_attributes
        """
        merged_field_data = {}
        mergeable_attributes = OpgeeService._get_mergeable_attributes()
        
        for field in fields:
            # Get all PyxisFieldData records for this field
            field_data_records = db.query(PyxisFieldData).filter(
                PyxisFieldData.pyxis_field_meta_id == field.id
            ).all()
            
            if debug_mode:
                logger.debug(f"Field {field.id} has {len(field_data_records)} data records")
            
            if field_data_records:
                # Merge attributes using existing merge utilities
                merged_attributes = merge_specific_attributes(
                    field_data_records=field_data_records,
                    attributes=mergeable_attributes,
                    query_start=start_date,
                    query_end=end_date
                )
                merged_field_data[field.id] = merged_attributes
                
                if debug_mode:
                    logger.debug(f"Field {field.id} merged {len(merged_attributes)} attributes")
            else:
                # No data records for this field
                merged_field_data[field.id] = {}
                if debug_mode:
                    logger.debug(f"Field {field.id} has no data records")
        
        return merged_field_data

    @staticmethod
    def _create_final_field_record(
        field: PyxisFieldMeta,
        merged_field_data: Dict[int, Dict[str, Any]],
        for_values: Dict[int, float]
    ) -> Dict[str, Any]:
        """
        Create final field record combining merged attributes and calculated FOR.
        
        Args:
            field: PyxisFieldMeta object
            merged_field_data: Dict of merged field data
            for_values: Dict of calculated FOR values
            
        Returns:
            Final field record for CSV output
        """
        # Start with pyxis_field_code
        result = {
            'pyxis_field_code': field.pyxis_field_code
        }
        
        # Add merged attributes
        merged_attributes = merged_field_data.get(field.id, {})
        result.update(merged_attributes)
        
        # Add calculated FOR value
        for_value = for_values.get(field.id, 0.0)
        result['for_value'] = for_value
        
        return result

    @staticmethod
    def _get_mergeable_attributes() -> List[str]:
        """Get list of attributes that should be merged (excludes calculated fields)."""
        from app.utils.merge_utils import load_merge_rules
        return list(load_merge_rules().keys())

    @staticmethod
    def _get_output_attributes() -> List[str]:
        """Get list of all attributes for CSV output (includes calculated fields)."""
        mergeable = OpgeeService._get_mergeable_attributes()
        calculated = ['for_value']  # Add other calculated fields here if needed
        return mergeable + calculated

    @staticmethod
    def _get_target_fields(
        db: Session,
        field_ids: Optional[List[int]] = None,
        country: Optional[str] = None,
        production_type: Optional[str] = None
    ) -> List[PyxisFieldMeta]:
        """
        Get target fields based on field_ids, country, and production type.
        
        Args:
            db: Database session
            field_ids: Optional list of field IDs
            country: Optional country filter
            production_type: Optional production type filter ("oil" or "gas")
            
        Returns:
            List of PyxisFieldMeta objects
        """
        base_query = db.query(PyxisFieldMeta)
        
        # Apply production type filter if specified
        if production_type:
            # Use subquery approach to avoid join issues
            logger.info(f"Applying production type filter: {production_type}")
            
            # Get field IDs that have records with the desired functional_unit
            field_ids_with_type = db.query(PyxisFieldData.pyxis_field_meta_id).filter(
                PyxisFieldData.functional_unit == production_type
            ).distinct().all()
            
            field_ids_list = [row[0] for row in field_ids_with_type]
            logger.info(f"Found {len(field_ids_list)} fields with functional_unit='{production_type}'")
            
            if not field_ids_list:
                logger.warning(f"No fields found with functional_unit='{production_type}'")
                return []
            
            base_query = base_query.filter(PyxisFieldMeta.id.in_(field_ids_list))
        
        if field_ids:
            fields = base_query.filter(
                PyxisFieldMeta.id.in_(field_ids)
            ).all()
            if len(fields) != len(field_ids):
                found_ids = [f.id for f in fields]
                missing_ids = [fid for fid in field_ids if fid not in found_ids]
                logger.warning(f"Some field IDs not found: {missing_ids}")
            return fields
        elif country:
            return base_query.filter(
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
        
        logger.info(f"SOURCE COVERAGE FILTER - Starting with {len(fields)} fields")
        logger.info(f"  - Min coverage ratio: {min_coverage_ratio}")
        logger.info(f"  - Trusted source types: {trusted_source_types}")
        
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
        
        logger.info(f"  - Found {total_contributing_sources} sources contributing field data")
        logger.info(f"  - Total field-source mappings: {len(field_source_mapping)}")
        
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
    def _generate_csv_output(
        opgee_data: List[Dict[str, Any]],
        output_path: str,
        start_date: date,
        end_date: date
    ) -> str:
        """
        Generate CSV file with OPGEE input data including calculated fields.
        """
        if not opgee_data:
            raise ValueError("No data to write to CSV")
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Get all possible column names from the data
        all_columns = set()
        for record in opgee_data:
            all_columns.update(record.keys())
        
        # Ensure pyxis_field_code is first, then alphabetical order for others
        fieldnames = ['pyxis_field_code']
        other_columns = sorted([col for col in all_columns if col != 'pyxis_field_code'])
        fieldnames.extend(other_columns)
        
        # Write CSV
        with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for record in opgee_data:
                # Ensure all fields have values (fill with empty string if missing)
                complete_record = {field: record.get(field, '') for field in fieldnames}
                writer.writerow(complete_record)
        
        logger.info(f"Generated OPGEE CSV file: {output_path} with {len(opgee_data)} records")
        logger.info(f"CSV columns: {fieldnames}")
        return output_path