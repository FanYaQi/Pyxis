"""
Upload Monthly Dynamic Pyxis Field Data to API

This script uploads monthly Argentina field data to the Pyxis backend API.
It generates monthly data on-the-fly and uploads directly without saving intermediate files.

Dynamic attributes include:
- Production volumes (oil_prod, gas_prod, num_prod_wells, num_water_inj_wells)
- Ratios (gor, wor, wir, glir, sor)
- Fractions (fraction_elec_onsite, fraction_remaining_gas_inj, fraction_water_reinjected, etc.)

Usage:
    cd data_preparation/argentina/scripts

    # Upload all available years and months
    pipenv run python 08_upload_monthly_to_api.py --email YOUR_EMAIL --password YOUR_PASSWORD

    # Upload specific year
    pipenv run python 08_upload_monthly_to_api.py --year 2024

    # Upload specific year and month range
    pipenv run python 08_upload_monthly_to_api.py --year 2024 --months 1-6

    # Upload multiple years
    pipenv run python 08_upload_monthly_to_api.py --start-year 2020 --end-year 2024

    # Use environment variables for credentials
    export PYXIS_EMAIL="your@email.com"
    export PYXIS_PASSWORD="yourpassword"
    pipenv run python 08_upload_monthly_to_api.py --start-year 2009 --end-year 2024

Note: This script will automatically detect available data and skip missing months
"""

import sys
from pathlib import Path
import argparse
import json
import time
import os
import io
from datetime import datetime, date
from typing import Dict, List, Optional
import calendar

import requests
from requests.exceptions import RequestException
import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')


# ============================================================================
# CONFIGURATION
# ============================================================================

API_BASE_URL = "http://localhost:8000/api/v1"
DATA_SOURCE_ID = 5  # AR_GOV data source ID
GRANULARITY = "field"
POLL_INTERVAL = 3  # seconds between status checks
MAX_WAIT_PER_UPLOAD = 300  # 5 minutes max per upload

# Unit conversion constants
M3_TO_BBL = 6.28981
MM3_TO_SCF = 35314666.7  # 10^6 * 35.3147
KM3_TO_SCF = 35314.7      # 1000 * 35.3147
M_TO_FT = 3.28084

# Default year range (will auto-detect available data)
DEFAULT_START_YEAR = 2009
DEFAULT_END_YEAR = datetime.now().year


# ============================================================================
# DATA GENERATION FUNCTIONS (from 05_generate_pyxis_monthly.py)
# ============================================================================

def calculate_api_from_density(density_ton_m3):
    """Calculate API gravity from density."""
    if pd.isna(density_ton_m3) or density_ton_m3 <= 0:
        return None
    api = (141.5 / density_ton_m3) - 131.5
    return api if api > 0 else None


def generate_monthly_data(translated_dir: Path, year: int, month: int) -> Optional[pd.DataFrame]:
    """
    Generate monthly field data for a specific year-month.

    Args:
        translated_dir: Path to translated data directory
        year: Target year
        month: Target month (1-12)

    Returns:
        DataFrame with monthly field data, or None if data not available
    """
    print(f"  Generating data for {year}-{month:02d}...")

    try:
        # Load required data files
        daily_oil = pd.read_csv(translated_dir / 'daily_oil_production_english.csv')
        daily_gas = pd.read_csv(translated_dir / 'daily_gas_production_english.csv')
        gas_field = pd.read_csv(translated_dir / 'gas_field_production_english.csv')
        oil_field = pd.read_csv(translated_dir / 'oil_field_production_english.csv')
        formation_vintage = pd.read_csv(translated_dir / 'field_production_by_formation_vintage_english.csv')

        # Load well production if available
        well_file = translated_dir / f'well_production_{year}_english.csv'
        if well_file.exists():
            well_prod = pd.read_csv(well_file)
        else:
            well_prod = None

    except FileNotFoundError as e:
        print(f"    ⚠️  Required data file not found: {e}")
        return None

    # Filter to target month
    daily_oil_month = daily_oil[(daily_oil['year'] == year) & (daily_oil['month'] == month)]
    daily_gas_month = daily_gas[(daily_gas['year'] == year) & (daily_gas['month'] == month)]

    if len(daily_oil_month) == 0 and len(daily_gas_month) == 0:
        print(f"    ⚠️  No production data for {year}-{month:02d}")
        return None

    # Get all fields
    all_fields = set(daily_oil_month['field_id'].unique()) | set(daily_gas_month['field_id'].unique())

    if len(all_fields) == 0:
        print(f"    ⚠️  No fields found for {year}-{month:02d}")
        return None

    # Pre-aggregate data for performance
    formation_month = formation_vintage[(formation_vintage['year'] == year) &
                                        (formation_vintage['month'] == month)]

    formation_agg = formation_month.groupby('field_id').agg({
        'oil_production_m3': 'sum',
        'gas_production_km3': 'sum',
        'water_production_m3': 'sum',
        'water_injection_m3': 'sum',
        'gas_injection_km3': 'sum',
        'well_vintage_year': 'min',
        'field_name': 'first'
    }).to_dict('index')

    gas_field_month = gas_field[(gas_field['year'] == year) & (gas_field['month'] == month)]
    gas_production_concepts = [
        'high_pressure_gas_mm3',
        'medium_pressure_gas_mm3',
        'low_pressure_gas_mm3',
        'unconventional_gas_mm3'
    ]
    gas_prod_filtered = gas_field_month[gas_field_month['concept'].isin(gas_production_concepts)]
    gas_agg = gas_prod_filtered.groupby('field_id')['quantity'].sum().to_dict()

    # Process each field
    output = []
    # Calculate last day of month
    last_day = calendar.monthrange(year, month)[1]

    for field_id in all_fields:
        field_data = {
            'field_id': field_id,
            'year': year,
            'month': month,
            'valid_from': f"{year}-{month:02d}-01",
            'valid_to': f"{year}-{month:02d}-{last_day}",
            'country': 'Argentina'
        }

        # Field name
        oil_field_data = daily_oil_month[daily_oil_month['field_id'] == field_id]
        gas_field_data = daily_gas_month[daily_gas_month['field_id'] == field_id]
        field_data['field_name'] = oil_field_data['field_name'].iloc[0] if len(oil_field_data) > 0 else (
            gas_field_data['field_name'].iloc[0] if len(gas_field_data) > 0 else field_id
        )

        # Oil production (bbl/day)
        if len(oil_field_data) > 0:
            oil_m3_day = oil_field_data['oil_production_avg_daily_m3'].iloc[0]
            field_data['oil_prod'] = oil_m3_day * M3_TO_BBL if pd.notna(oil_m3_day) else None
        else:
            field_data['oil_prod'] = None

        # Gas production (scf/day)
        if len(gas_field_data) > 0:
            gas_mm3_day = gas_field_data['gas_production_avg_daily_mm3'].iloc[0]
            field_data['gas_prod'] = gas_mm3_day * MM3_TO_SCF if pd.notna(gas_mm3_day) else None
        else:
            # Fallback to gas_field_production
            gas_mm3_month = gas_agg.get(field_id, 0)
            if gas_mm3_month > 0:
                field_data['gas_prod'] = (gas_mm3_month * MM3_TO_SCF) / 30
            else:
                field_data['gas_prod'] = None

        # GOR (scf/bbl)
        if field_data.get('oil_prod') and field_data.get('gas_prod') and field_data['oil_prod'] > 0:
            field_data['gor'] = field_data['gas_prod'] / field_data['oil_prod']
        else:
            field_data['gor'] = None

        # Formation/vintage data
        formation_data = formation_agg.get(field_id, {})
        if formation_data:
            total_oil = formation_data.get('oil_production_m3', 0)
            total_water_prod = formation_data.get('water_production_m3', 0)
            total_water_inj = formation_data.get('water_injection_m3', 0)
            total_gas_inj_km3 = formation_data.get('gas_injection_km3', 0)

            # WOR (bbl_water/bbl_oil)
            field_data['wor'] = total_water_prod / total_oil if total_oil > 0 else None

            # WIR (bbl_water/bbl_oil)
            field_data['wir'] = total_water_inj / total_oil if total_oil > 0 else None

            # GLIR (scf/bbl_liquid)
            if total_oil > 0 and total_gas_inj_km3 > 0:
                gas_inj_scf = total_gas_inj_km3 * KM3_TO_SCF
                oil_bbl = total_oil * M3_TO_BBL
                water_bbl = total_water_prod * M3_TO_BBL
                liquid_bbl = oil_bbl + water_bbl
                field_data['glir'] = gas_inj_scf / liquid_bbl if liquid_bbl > 0 else None
            else:
                field_data['glir'] = None
        else:
            field_data['wor'] = None
            field_data['wir'] = None
            field_data['glir'] = None

        # Well counts
        if well_prod is not None:
            well_month = well_prod[(well_prod['field_id'] == field_id) &
                                   (well_prod['year'] == year) &
                                   (well_prod['month'] == month)]

            if len(well_month) > 0:
                active_wells = well_month[well_month['well_status'].str.contains('active|producing', case=False, na=False)]
                field_data['num_prod_wells'] = len(active_wells['well_id'].unique())

                inj_wells = well_month[well_month['water_injection_m3'] > 0]
                field_data['num_water_inj_wells'] = len(inj_wells['well_id'].unique())
            else:
                field_data['num_prod_wells'] = None
                field_data['num_water_inj_wells'] = None
        else:
            field_data['num_prod_wells'] = None
            field_data['num_water_inj_wells'] = None

        # Gas reinjection fraction
        gas_field_data = gas_field_month[gas_field_month['field_id'] == field_id]
        if len(gas_field_data) > 0:
            gas_reinj = gas_field_data[gas_field_data['concept'] == 'gas_reinjection_formation_mm3']['quantity'].sum()
            total_gas_prod = gas_field_data[
                gas_field_data['concept'].isin(['high_pressure_gas_mm3', 'medium_pressure_gas_mm3', 'low_pressure_gas_mm3'])
            ]['quantity'].sum()

            if total_gas_prod > 0 and gas_reinj > 0:
                field_data['fraction_remaining_gas_inj'] = gas_reinj / total_gas_prod
            else:
                field_data['fraction_remaining_gas_inj'] = None
        else:
            field_data['fraction_remaining_gas_inj'] = None

        output.append(field_data)

    output_df = pd.DataFrame(output)
    print(f"    ✓ Generated {len(output_df)} field records")

    return output_df


def generate_config_json() -> Dict:
    """Generate config JSON for monthly dynamic data upload."""
    return {
        "data_metadata": {
            "name": "Argentina Monthly Field Data",
            "description": "Monthly production and operational data for Argentina oil and gas fields",
            "type": "csv",
            "version": "1.0.0",
            "attributes": [
                {"name": "field_id", "type": "string", "units": None},
                {"name": "field_name", "type": "string", "units": None},
                {"name": "country", "type": "string", "units": None},
                {"name": "year", "type": "integer", "units": "year"},
                {"name": "month", "type": "integer", "units": "month"},
                {"name": "valid_from", "type": "date", "units": None},
                {"name": "valid_to", "type": "date", "units": None},
                {"name": "oil_prod", "type": "number", "units": "bbl/day"},
                {"name": "gas_prod", "type": "number", "units": "scf/day"},
                {"name": "gor", "type": "number", "units": "scf/bbl"},
                {"name": "wor", "type": "number", "units": "bbl/bbl"},
                {"name": "wir", "type": "number", "units": "bbl/bbl"},
                {"name": "glir", "type": "number", "units": "scf/bbl"},
                {"name": "num_prod_wells", "type": "integer", "units": None},
                {"name": "num_water_inj_wells", "type": "integer", "units": None},
                {"name": "fraction_remaining_gas_inj", "type": "number", "units": None}
            ]
        },
        "mappings": [
            {"source_attribute": "field_name", "target_attribute": "name"},
            {"source_attribute": "country", "target_attribute": "country"},
            {"source_attribute": "valid_from", "target_attribute": "valid_from"},
            {"source_attribute": "valid_to", "target_attribute": "valid_to"},
            {"source_attribute": "oil_prod", "target_attribute": "oil_prod"},
            {"source_attribute": "gor", "target_attribute": "gor"},
            {"source_attribute": "wor", "target_attribute": "wor"},
            {"source_attribute": "wir", "target_attribute": "wir"},
            {"source_attribute": "glir", "target_attribute": "glir"},
            {"source_attribute": "num_prod_wells", "target_attribute": "num_prod_wells"},
            {"source_attribute": "num_water_inj_wells", "target_attribute": "num_water_inj_wells"},
            {"source_attribute": "fraction_remaining_gas_inj", "target_attribute": "fraction_remaining_gas_inj"}
        ],
        "file_specific": {
            "csv": {
                "delimiter": ",",
                "encoding": "utf-8",
                "header_row": 0
            }
        }
    }


# ============================================================================
# API CLIENT
# ============================================================================

class PyxisAPIClient:
    """Client for interacting with Pyxis API"""

    def __init__(self, base_url: str, email: str, password: str):
        self.base_url = base_url
        self.email = email
        self.password = password
        self.token = None

    def login(self):
        """Login and obtain access token."""
        print(f"Logging in as {self.email}...")

        url = f"{self.base_url}/login/access-token"
        data = {"username": self.email, "password": self.password}

        try:
            response = requests.post(url, data=data, timeout=30)
            response.raise_for_status()

            token_data = response.json()
            self.token = token_data.get("access_token")

            if not self.token:
                raise ValueError("No access token in response")

            print("✅ Login successful\n")
            return self.token

        except RequestException as e:
            print(f"❌ Login failed: {str(e)}")
            raise

    def upload_data_entry(self, csv_data: bytes, config_json: Dict, source_id: int,
                         granularity: str, alias: str) -> int:
        """Upload a data entry with in-memory CSV and config."""
        if not self.token:
            raise ValueError("Not logged in")

        url = f"{self.base_url}/data-entries/"
        headers = {"Authorization": f"Bearer {self.token}"}

        # Prepare files as tuples (name, file_content, content_type)
        files = {
            'data_file': ('data.csv', io.BytesIO(csv_data), 'text/csv'),
            'config_file': ('config.json', io.BytesIO(json.dumps(config_json).encode()), 'application/json')
        }

        # Form fields
        data = {
            'source_id': str(source_id),
            'granularity': granularity,
            'alias': alias
        }

        try:
            response = requests.post(url, headers=headers, files=files, data=data, timeout=120)
            response.raise_for_status()

            result = response.json()
            data_entry_id = result['data_entry']['id']
            return data_entry_id

        except RequestException as e:
            print(f"❌ Upload failed: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    print(f"   Error details: {json.dumps(error_detail, indent=2)}")
                except:
                    print(f"   Response text: {e.response.text}")
            raise

    def trigger_processing(self, data_entry_id: int, prevent_self_matching: bool = True):
        """Trigger processing for a data entry."""
        if not self.token:
            raise ValueError("Not logged in")

        url = f"{self.base_url}/data-entries/{data_entry_id}/process"
        params = {'prevent_self_matching': prevent_self_matching}
        headers = {"Authorization": f"Bearer {self.token}"}

        try:
            response = requests.post(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except RequestException as e:
            print(f"❌ Failed to trigger processing: {str(e)}")
            raise

    def wait_for_completion(self, data_entry_id: int, poll_interval: int = 3, max_wait: int = 300):
        """Wait for processing to complete."""
        url = f"{self.base_url}/data-entries/{data_entry_id}/status"
        headers = {"Authorization": f"Bearer {self.token}"}

        elapsed = 0
        while elapsed < max_wait:
            try:
                response = requests.get(url, headers=headers, timeout=30)
                response.raise_for_status()
                status_info = response.json()

                status = status_info.get('status')

                if status == 'COMPLETED':
                    return status_info
                elif status == 'FAILED':
                    error_msg = status_info.get('error_message', 'Unknown error')
                    raise Exception(f"Processing failed: {error_msg}")

                time.sleep(poll_interval)
                elapsed += poll_interval

            except RequestException as e:
                print(f"⚠️  Status check failed: {str(e)}")
                time.sleep(poll_interval)
                elapsed += poll_interval

        raise TimeoutError(f"Processing timeout after {max_wait}s")


# ============================================================================
# MAIN FUNCTION
# ============================================================================

def main():
    """Main execution."""
    parser = argparse.ArgumentParser(description='Upload monthly Argentina field data to Pyxis API')
    parser.add_argument('--email', type=str, help='User email')
    parser.add_argument('--password', type=str, help='User password')
    parser.add_argument('--source-id', type=int, default=DATA_SOURCE_ID, help=f'Data source ID (default: {DATA_SOURCE_ID})')
    parser.add_argument('--year', type=int, help='Single year to upload')
    parser.add_argument('--start-year', type=int, default=DEFAULT_START_YEAR, help=f'Start year (default: {DEFAULT_START_YEAR})')
    parser.add_argument('--end-year', type=int, default=DEFAULT_END_YEAR, help=f'End year (default: current year)')
    parser.add_argument('--months', type=str, help='Month range (e.g., "1-12" or "1,3,5")')
    parser.add_argument('--prevent-self-matching', action='store_true', default=True, help='Prevent self-matching (default: True)')
    args = parser.parse_args()

    # Get credentials
    email = args.email or os.getenv('PYXIS_EMAIL')
    password = args.password or os.getenv('PYXIS_PASSWORD')

    if not email or not password:
        print("❌ Error: Email and password required")
        sys.exit(1)

    # Determine year range
    if args.year:
        years = [args.year]
    else:
        years = list(range(args.start_year, args.end_year + 1))

    # Determine months
    if args.months:
        if '-' in args.months:
            start, end = map(int, args.months.split('-'))
            months = list(range(start, end + 1))
        else:
            months = [int(m) for m in args.months.split(',')]
    else:
        months = list(range(1, 13))  # All months

    # Get data directory
    base_dir = Path(__file__).parent.parent
    translated_dir = base_dir / 'raw' / 'translated'

    if not translated_dir.exists():
        print(f"❌ Error: Translated data directory not found: {translated_dir}")
        sys.exit(1)

    print("="*70)
    print("ARGENTINA MONTHLY DYNAMIC DATA → PYXIS API UPLOAD")
    print("="*70)
    print(f"API URL: {API_BASE_URL}")
    print(f"Years: {years[0]}-{years[-1]} ({len(years)} years)")
    print(f"Months: {months}")
    print(f"Total uploads: {len(years) * len(months)}")
    print(f"Prevent self-matching: {args.prevent_self_matching}")
    print("="*70 + "\n")

    # Initialize API client
    client = PyxisAPIClient(API_BASE_URL, email, password)
    client.login()

    # Generate config once
    config = generate_config_json()

    # Upload each year-month
    total_uploads = 0
    successful_uploads = 0
    failed_uploads = []

    for year in years:
        for month in months:
            # Check if we should skip (e.g., future months in current year)
            if year == datetime.now().year and month > datetime.now().month:
                print(f"⊘ Skipping {year}-{month:02d} (future month)")
                continue

            print(f"📤 Uploading {year}-{month:02d}...")
            total_uploads += 1

            try:
                # Generate monthly data
                monthly_df = generate_monthly_data(translated_dir, year, month)

                if monthly_df is None or len(monthly_df) == 0:
                    print(f"  ⊘ Skipped (no data)\n")
                    continue

                # Convert to CSV bytes
                csv_buffer = io.BytesIO()
                monthly_df.to_csv(csv_buffer, index=False)
                csv_data = csv_buffer.getvalue()

                # Upload
                alias = f"Argentina Monthly {year}-{month:02d}"
                data_entry_id = client.upload_data_entry(
                    csv_data, config, args.source_id, GRANULARITY, alias
                )
                print(f"  ✓ Uploaded (Entry ID: {data_entry_id})")

                # Trigger processing
                client.trigger_processing(data_entry_id, prevent_self_matching=args.prevent_self_matching)
                print(f"  ✓ Processing triggered")

                # Wait for completion
                status = client.wait_for_completion(data_entry_id, POLL_INTERVAL, MAX_WAIT_PER_UPLOAD)
                fields_count = status.get('processed_fields_count', 0)
                print(f"  ✅ Completed ({fields_count} fields)\n")

                successful_uploads += 1

            except Exception as e:
                print(f"  ❌ Failed: {str(e)}\n")
                failed_uploads.append(f"{year}-{month:02d}: {str(e)}")

    # Final summary
    print("\n" + "="*70)
    print("UPLOAD SUMMARY")
    print("="*70)
    print(f"Total uploads attempted: {total_uploads}")
    print(f"Successful: {successful_uploads}")
    print(f"Failed: {len(failed_uploads)}")

    if failed_uploads:
        print("\nFailed uploads:")
        for failure in failed_uploads:
            print(f"  - {failure}")

    print("="*70)


if __name__ == "__main__":
    main()
