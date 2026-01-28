"""
Load monthly flare data from global flaring dataset into Pyxis database.

This script:
1. Reads the global flare CSV file
2. Filters by country (ISO code) and flare type
3. Converts date format and prepares data for database
4. Loads data into the Flare table via the backend FlareService

Usage:
    # Load Argentina upstream flares (default)
    python load_flare_data.py --country ARG --type upstream

    # Load all types for a country
    python load_flare_data.py --country ARG --type all

    # Dry run to see what would be loaded
    python load_flare_data.py --country ARG --type upstream --dry-run

    # Load with specific API URL
    python load_flare_data.py --country ARG --type upstream --api-url http://localhost:8000
"""

import sys
import argparse
import io
from pathlib import Path
from datetime import datetime
from typing import Optional

import requests
from requests.exceptions import RequestException
import pandas as pd


# Default paths
FLARE_DATA_DIR = Path(__file__).parent.parent / 'flaring'
DEFAULT_FLARE_FILE = 'multiyear_flare_month_summary_all_run48.csv'

# Common country ISO codes for reference
COUNTRY_ISO_MAP = {
    'argentina': 'ARG',
    'russia': 'RUS',
    'usa': 'USA',
    'iraq': 'IRQ',
    'iran': 'IRN',
    'nigeria': 'NGA',
    'venezuela': 'VEN',
    'algeria': 'DZA',
    'libya': 'LBY',
    'mexico': 'MEX',
}

# Valid flare types in the dataset
VALID_FLARE_TYPES = [
    'upstream',      # Oil & gas production
    'downstream',    # Refineries, LNG plants
    'industrial',    # Power plants, chemical plants
    'metallurgy',    # Metal smelting
    'landfill',      # Biogas
    'volcano',       # Natural volcanic
    'sawmill',       # Wood processing
]


class FlareDataLoader:
    """Loader for global flare data into Pyxis database."""

    def __init__(self, api_url: str = "http://localhost:8000"):
        self.api_url = api_url
        self.token = None

    def login(self, email: str, password: str) -> bool:
        """Login to get JWT token."""
        url = f"{self.api_url}/api/v1/login/access-token"
        data = {"username": email, "password": password}

        try:
            response = requests.post(url, data=data, timeout=30)
            response.raise_for_status()

            result = response.json()
            self.token = result.get('access_token')
            print(f"  Logged in successfully")
            return True

        except RequestException as e:
            print(f"  Login failed: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"  Response: {e.response.text}")
            return False

    def upload_flare_csv(self, csv_data: bytes, update_existing: bool = True) -> dict:
        """Upload flare CSV data to the API."""
        if not self.token:
            raise ValueError("Not logged in")

        url = f"{self.api_url}/api/v1/flares/upload"
        headers = {"Authorization": f"Bearer {self.token}"}

        files = {
            'file': ('flares.csv', io.BytesIO(csv_data), 'text/csv')
        }

        params = {'update_existing': str(update_existing).lower()}

        try:
            response = requests.post(url, headers=headers, files=files,
                                    params=params, timeout=600)  # 10 min timeout for large files
            response.raise_for_status()
            return response.json()

        except RequestException as e:
            print(f"  Upload failed: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    print(f"  Error details: {error_detail}")
                except:
                    print(f"  Response text: {e.response.text}")
            raise


def parse_date(date_str: str) -> datetime:
    """
    Parse date string in format '01-Mmm-YYYY' (e.g., '01-Apr-2012').

    Args:
        date_str: Date string like '01-Apr-2012'

    Returns:
        datetime object
    """
    return datetime.strptime(date_str, '%d-%b-%Y')


def load_and_filter_flare_data(
    flare_file: Path,
    country_iso: str,
    flare_type: str,
    chunk_size: int = 100000
) -> pd.DataFrame:
    """
    Load flare data from CSV and filter by country and type.

    Uses chunked reading to handle large files efficiently.

    Args:
        flare_file: Path to the flare CSV file
        country_iso: ISO 3-letter country code (e.g., 'ARG')
        flare_type: Flare type to filter (e.g., 'upstream') or 'all'
        chunk_size: Number of rows to process per chunk

    Returns:
        Filtered DataFrame with required columns
    """
    print(f"\n2. Loading and filtering flare data...")
    print(f"   File: {flare_file.name}")
    print(f"   Country filter: {country_iso}")
    print(f"   Type filter: {flare_type}")

    filtered_chunks = []
    total_rows = 0
    matched_rows = 0

    # Read in chunks to handle large file
    for chunk in pd.read_csv(flare_file, chunksize=chunk_size):
        total_rows += len(chunk)

        # Filter by country
        mask = chunk['iso'] == country_iso

        # Filter by type if not 'all'
        if flare_type.lower() != 'all':
            mask &= chunk['type'] == flare_type.lower()

        filtered = chunk[mask]

        if len(filtered) > 0:
            filtered_chunks.append(filtered)
            matched_rows += len(filtered)

        # Progress update every 500k rows
        if total_rows % 500000 == 0:
            print(f"   Processed {total_rows:,} rows, found {matched_rows:,} matches...")

    print(f"   Total rows scanned: {total_rows:,}")
    print(f"   Matching rows: {matched_rows:,}")

    if not filtered_chunks:
        print(f"   WARNING: No data found for country={country_iso}, type={flare_type}")
        return pd.DataFrame()

    # Combine all filtered chunks
    df = pd.concat(filtered_chunks, ignore_index=True)

    return df


def prepare_flare_data_for_upload(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepare flare data for upload to the API.

    The API expects columns: lat, lon, month, id, BCM
    The 'month' column can be a date string (will be parsed by the service).

    Args:
        df: Filtered flare DataFrame

    Returns:
        DataFrame with required columns for API upload
    """
    print(f"\n3. Preparing data for upload...")

    # Select required columns
    required_cols = ['id', 'lat', 'lon', 'month', 'BCM']

    # Check all required columns exist
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    result = df[required_cols].copy()

    # Show data summary
    print(f"   Records to upload: {len(result):,}")
    print(f"   Unique flare IDs: {result['id'].nunique():,}")
    print(f"   Date range: {result['month'].min()} to {result['month'].max()}")
    print(f"   Total BCM volume: {result['BCM'].sum():.6f}")

    # Show volume by year
    result['_year'] = result['month'].apply(lambda x: parse_date(x).year)
    yearly = result.groupby('_year')['BCM'].sum()
    print(f"   Volume by year:")
    for year, vol in yearly.items():
        print(f"      {year}: {vol:.6f} BCM")
    result.drop(columns=['_year'], inplace=True)

    return result


def load_flare_data(
    country: str,
    flare_type: str = 'upstream',
    flare_file: Optional[Path] = None,
    email: Optional[str] = None,
    password: Optional[str] = None,
    api_url: str = "http://localhost:8000",
    dry_run: bool = False,
    update_existing: bool = True
):
    """
    Main function to load flare data into the database.

    Args:
        country: Country name or ISO code
        flare_type: Flare type to filter ('upstream', 'downstream', etc. or 'all')
        flare_file: Path to flare CSV file (uses default if not specified)
        email: User email for API authentication
        password: User password
        api_url: API base URL
        dry_run: If True, only show what would be uploaded without actually uploading
        update_existing: If True, update existing records; if False, skip them
    """
    start_time = datetime.now()

    # Normalize country to ISO code
    country_iso = country.upper()
    if country.lower() in COUNTRY_ISO_MAP:
        country_iso = COUNTRY_ISO_MAP[country.lower()]

    print(f"=== Loading Flare Data ===")
    print(f"Started: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Country: {country} ({country_iso})")
    print(f"Type: {flare_type}")
    print(f"Dry run: {dry_run}")

    # Validate flare type
    if flare_type.lower() != 'all' and flare_type.lower() not in VALID_FLARE_TYPES:
        print(f"\nERROR: Invalid flare type: {flare_type}")
        print(f"Valid types: {VALID_FLARE_TYPES} or 'all'")
        sys.exit(1)

    # Determine flare file path
    if flare_file is None:
        flare_file = FLARE_DATA_DIR / DEFAULT_FLARE_FILE

    print(f"\n1. Checking input file...")
    if not flare_file.exists():
        print(f"   ERROR: Flare file not found: {flare_file}")
        sys.exit(1)

    file_size_mb = flare_file.stat().st_size / (1024 * 1024)
    print(f"   File: {flare_file}")
    print(f"   Size: {file_size_mb:.1f} MB")

    # Load and filter data
    df = load_and_filter_flare_data(flare_file, country_iso, flare_type)

    if df.empty:
        print(f"\nNo data to upload. Exiting.")
        sys.exit(0)

    # Prepare for upload
    upload_df = prepare_flare_data_for_upload(df)

    if dry_run:
        print(f"\n=== DRY RUN - No data uploaded ===")
        print(f"\nSample data (first 10 rows):")
        print(upload_df.head(10).to_string())
        print(f"\nTo actually load data, run without --dry-run flag")
        return

    # Convert to CSV bytes
    print(f"\n4. Converting to CSV...")
    csv_bytes = upload_df.to_csv(index=False).encode('utf-8')
    print(f"   CSV size: {len(csv_bytes)/1024:.1f} KB")

    # Login and upload
    print(f"\n5. Connecting to API at {api_url}...")

    if not email or not password:
        print(f"   ERROR: Email and password required for upload")
        print(f"   Use --email and --password arguments")
        sys.exit(1)

    loader = FlareDataLoader(api_url)
    if not loader.login(email, password):
        sys.exit(1)

    print(f"\n6. Uploading flare data...")
    print(f"   Update existing: {update_existing}")

    try:
        result = loader.upload_flare_csv(csv_bytes, update_existing=update_existing)

        print(f"\n=== Upload Complete ===")
        print(f"   Processed records: {result.get('processed_records', 'N/A')}")
        print(f"   Created records: {result.get('created_records', 'N/A')}")
        print(f"   Updated records: {result.get('updated_records', 'N/A')}")
        print(f"   Skipped records: {result.get('skipped_records', 'N/A')}")

        errors = result.get('errors', [])
        if errors:
            print(f"   Errors: {len(errors)}")
            for err in errors[:5]:  # Show first 5 errors
                print(f"      - {err}")
            if len(errors) > 5:
                print(f"      ... and {len(errors) - 5} more errors")

    except Exception as e:
        print(f"\n   Upload failed: {str(e)}")
        sys.exit(1)

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    print(f"\nFinished: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Duration: {duration:.1f} seconds")


def main():
    parser = argparse.ArgumentParser(
        description='Load monthly flare data into Pyxis database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Load Argentina upstream flares
    python load_flare_data.py --country ARG --type upstream --email user@example.com --password xxx

    # Load all flare types for Argentina
    python load_flare_data.py --country ARG --type all --email user@example.com --password xxx

    # Dry run to preview what would be loaded
    python load_flare_data.py --country ARG --type upstream --dry-run

Country codes:
    ARG=Argentina, RUS=Russia, USA, IRQ=Iraq, IRN=Iran, NGA=Nigeria,
    VEN=Venezuela, DZA=Algeria, LBY=Libya, MEX=Mexico

Flare types:
    upstream, downstream, industrial, metallurgy, landfill, volcano, sawmill, all
        """
    )

    parser.add_argument('--country', type=str, required=True,
                       help='Country name or ISO code (e.g., ARG, Argentina)')
    parser.add_argument('--type', type=str, default='upstream',
                       help='Flare type to load (default: upstream). Use "all" for all types.')
    parser.add_argument('--file', type=str, default=None,
                       help='Path to flare CSV file (uses default if not specified)')
    parser.add_argument('--email', type=str, default=None,
                       help='User email for API authentication')
    parser.add_argument('--password', type=str, default=None,
                       help='User password')
    parser.add_argument('--api-url', type=str, default='http://localhost:8000',
                       help='API base URL (default: http://localhost:8000)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Preview data without uploading')
    parser.add_argument('--no-update', action='store_true',
                       help='Skip existing records instead of updating them')

    args = parser.parse_args()

    flare_file = Path(args.file) if args.file else None

    load_flare_data(
        country=args.country,
        flare_type=args.type,
        flare_file=flare_file,
        email=args.email,
        password=args.password,
        api_url=args.api_url,
        dry_run=args.dry_run,
        update_existing=not args.no_update
    )


if __name__ == "__main__":
    main()
