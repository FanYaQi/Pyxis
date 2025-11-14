"""
Upload Static Pyxis Field Data to API

This script uploads the static Argentina field data to the Pyxis backend API.

Requirements:
- Backend API running at http://localhost:8000
- User credentials configured
- Static CSV and config JSON files generated

Usage:
    cd data_preparation/argentina/scripts
    pipenv run python 07_upload_static_to_api.py --email YOUR_EMAIL --password YOUR_PASSWORD

Or set environment variables:
    export PYXIS_EMAIL="your@email.com"
    export PYXIS_PASSWORD="yourpassword"
    pipenv run python 07_upload_static_to_api.py
"""

import sys
from pathlib import Path
import argparse
import json
import time
import os

import requests
from requests.exceptions import RequestException


# ============================================================================
# CONFIGURATION
# ============================================================================

API_BASE_URL = "http://localhost:8000/api/v1"
DATA_SOURCE_ID = 5  # AR_GOV data source ID
GRANULARITY = "field"  # Data granularity
ALIAS = "Argentina Static Fields"
POLL_INTERVAL = 5  # seconds


# ============================================================================
# API CLIENT
# ============================================================================

class PyxisAPIClient:
    """Client for interacting with Pyxis API"""

    def __init__(self, base_url: str, email: str, password: str):
        """
        Initialize API client.

        Args:
            base_url: Base URL of the API
            email: User email
            password: User password
        """
        self.base_url = base_url
        self.email = email
        self.password = password
        self.token = None

    def login(self):
        """Login and obtain access token."""
        print(f"Logging in as {self.email}...")

        url = f"{self.base_url}/login/access-token"
        data = {
            "username": self.email,
            "password": self.password
        }

        try:
            response = requests.post(url, data=data, timeout=30)
            response.raise_for_status()

            token_data = response.json()
            self.token = token_data.get("access_token")

            if not self.token:
                raise ValueError("No access token in response")

            print("✅ Login successful")
            return self.token

        except RequestException as e:
            print(f"❌ Login failed: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"   Response: {e.response.text}")
            raise

    def upload_data_entry(self, data_file_path: Path, config_file_path: Path,
                         source_id: int, granularity: str, alias: str):
        """
        Upload a data entry.

        Args:
            data_file_path: Path to data CSV file
            config_file_path: Path to config JSON file
            source_id: Data source ID
            granularity: Data granularity
            alias: Human-readable name

        Returns:
            Data entry ID
        """
        if not self.token:
            raise ValueError("Not logged in. Call login() first.")

        print(f"\nUploading data entry...")
        print(f"  Data file: {data_file_path}")
        print(f"  Config file: {config_file_path}")
        print(f"  Source ID: {source_id}")
        print(f"  Granularity: {granularity}")
        print(f"  Alias: {alias}")

        url = f"{self.base_url}/data-entries/"

        headers = {
            "Authorization": f"Bearer {self.token}"
        }

        # Prepare multipart form data
        with open(data_file_path, 'rb') as data_file, \
             open(config_file_path, 'rb') as config_file:

            files = {
                'data_file': (data_file_path.name, data_file, 'text/csv'),
                'config_file': (config_file_path.name, config_file, 'application/json')
            }

            data = {
                'source_id': str(source_id),
                'granularity': granularity,
                'alias': alias
            }

            try:
                response = requests.post(
                    url,
                    headers=headers,
                    files=files,
                    data=data,
                    timeout=120
                )
                response.raise_for_status()

                result = response.json()
                data_entry_id = result['data_entry']['id']

                print(f"✅ Upload successful - Data Entry ID: {data_entry_id}")
                return data_entry_id

            except RequestException as e:
                print(f"❌ Upload failed: {str(e)}")
                if hasattr(e, 'response') and e.response is not None:
                    print(f"   Response: {e.response.text}")
                raise

    def trigger_processing(self, data_entry_id: int, prevent_self_matching: bool = False):
        """
        Trigger processing for a data entry.

        Args:
            data_entry_id: Data entry ID
            prevent_self_matching: Prevent self-matching

        Returns:
            Processing status
        """
        if not self.token:
            raise ValueError("Not logged in. Call login() first.")

        print(f"\nTriggering processing for data entry {data_entry_id}...")
        print(f"  Prevent self-matching: {prevent_self_matching}")

        url = f"{self.base_url}/data-entries/{data_entry_id}/process"
        params = {'prevent_self_matching': prevent_self_matching}

        headers = {
            "Authorization": f"Bearer {self.token}"
        }

        try:
            response = requests.post(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()

            result = response.json()
            print(f"✅ Processing triggered: {result.get('message')}")
            return result

        except RequestException as e:
            print(f"❌ Failed to trigger processing: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"   Response: {e.response.text}")
            raise

    def get_processing_status(self, data_entry_id: int):
        """
        Get processing status for a data entry.

        Args:
            data_entry_id: Data entry ID

        Returns:
            Status information
        """
        if not self.token:
            raise ValueError("Not logged in. Call login() first.")

        url = f"{self.base_url}/data-entries/{data_entry_id}/status"

        headers = {
            "Authorization": f"Bearer {self.token}"
        }

        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            return response.json()

        except RequestException as e:
            print(f"❌ Failed to get status: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"   Response: {e.response.text}")
            raise

    def wait_for_completion(self, data_entry_id: int, poll_interval: int = 5, max_wait: int = 600):
        """
        Wait for data entry processing to complete.

        Args:
            data_entry_id: Data entry ID
            poll_interval: Seconds between status checks
            max_wait: Maximum wait time in seconds

        Returns:
            Final status
        """
        print(f"\nWaiting for processing to complete...")
        print(f"  Polling every {poll_interval} seconds (max wait: {max_wait}s)")

        elapsed = 0
        while elapsed < max_wait:
            status_info = self.get_processing_status(data_entry_id)
            status = status_info.get('status')
            error_msg = status_info.get('error_message')
            fields_count = status_info.get('processed_fields_count', 0)

            print(f"  [{elapsed}s] Status: {status}, Fields processed: {fields_count}")

            if status == 'COMPLETED':
                print(f"✅ Processing completed successfully!")
                print(f"   Total fields processed: {fields_count}")
                return status_info

            elif status == 'FAILED':
                print(f"❌ Processing failed!")
                if error_msg:
                    print(f"   Error: {error_msg}")
                return status_info

            time.sleep(poll_interval)
            elapsed += poll_interval

        print(f"⚠️  Timeout reached after {max_wait}s")
        return self.get_processing_status(data_entry_id)


# ============================================================================
# MAIN FUNCTION
# ============================================================================

def main():
    """Main execution."""
    parser = argparse.ArgumentParser(description='Upload static Argentina field data to Pyxis API')
    parser.add_argument('--email', type=str, help='User email (or set PYXIS_EMAIL env var)')
    parser.add_argument('--password', type=str, help='User password (or set PYXIS_PASSWORD env var)')
    parser.add_argument('--source-id', type=int, default=DATA_SOURCE_ID, help=f'Data source ID (default: {DATA_SOURCE_ID})')
    parser.add_argument('--prevent-self-matching', action='store_true', help='Prevent self-matching during processing')
    parser.add_argument('--data-file', type=str, help='Path to data CSV file (default: ../output/argentina_pyxis_static_fields.csv)')
    parser.add_argument('--config-file', type=str, help='Path to config JSON file (default: ../output/argentina_pyxis_static_fields_config.json)')
    args = parser.parse_args()

    # Get credentials
    email = args.email or os.getenv('PYXIS_EMAIL')
    password = args.password or os.getenv('PYXIS_PASSWORD')

    if not email or not password:
        print("❌ Error: Email and password required")
        print("   Provide via --email/--password or set PYXIS_EMAIL/PYXIS_PASSWORD environment variables")
        sys.exit(1)

    # Get file paths
    base_dir = Path(__file__).parent.parent
    output_dir = base_dir / 'output'

    data_file = Path(args.data_file) if args.data_file else output_dir / 'argentina_pyxis_static_fields.csv'
    config_file = Path(args.config_file) if args.config_file else output_dir / 'argentina_pyxis_static_fields_config.json'

    # Validate files exist
    if not data_file.exists():
        print(f"❌ Error: Data file not found: {data_file}")
        sys.exit(1)

    if not config_file.exists():
        print(f"❌ Error: Config file not found: {config_file}")
        sys.exit(1)

    print("="*70)
    print("ARGENTINA STATIC DATA → PYXIS API UPLOAD")
    print("="*70)
    print(f"API URL: {API_BASE_URL}")
    print(f"User: {email}")
    print(f"Data Source ID: {args.source_id}")
    print(f"Data file: {data_file}")
    print(f"Config file: {config_file}")
    print("="*70)

    try:
        # Initialize API client
        client = PyxisAPIClient(API_BASE_URL, email, password)

        # Login
        client.login()

        # Upload data entry
        data_entry_id = client.upload_data_entry(
            data_file_path=data_file,
            config_file_path=config_file,
            source_id=args.source_id,
            granularity=GRANULARITY,
            alias=ALIAS
        )

        # Trigger processing
        client.trigger_processing(data_entry_id, prevent_self_matching=args.prevent_self_matching)

        # Wait for completion
        final_status = client.wait_for_completion(data_entry_id, poll_interval=POLL_INTERVAL)

        # Print final summary
        print("\n" + "="*70)
        if final_status.get('status') == 'COMPLETED':
            print("✅ UPLOAD AND PROCESSING COMPLETED SUCCESSFULLY")
            print(f"   Data Entry ID: {data_entry_id}")
            print(f"   Fields processed: {final_status.get('processed_fields_count', 0)}")
        else:
            print("❌ PROCESSING FAILED OR INCOMPLETE")
            print(f"   Status: {final_status.get('status')}")
            if final_status.get('error_message'):
                print(f"   Error: {final_status.get('error_message')}")
        print("="*70)

    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
