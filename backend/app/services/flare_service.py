"""
Flare service for processing flare data from CSV files.
"""

import io
import logging
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Tuple

import pandas as pd
import h3
from fastapi import UploadFile
from sqlalchemy import and_, func
from sqlalchemy.orm import Session
from geoalchemy2 import WKTElement

from app.postgres.models.flare import Flare
from app.schemas.flare import FlareCreate, FlareFilter


logger = logging.getLogger(__name__)


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
                    h3_index = h3.geo_to_h3(latitude, longitude, resolution=9)
                    
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