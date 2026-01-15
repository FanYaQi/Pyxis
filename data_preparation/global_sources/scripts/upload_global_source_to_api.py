"""
Upload global source static field data to Pyxis API.

Usage:
    python upload_global_source_to_api.py --source cd --country Argentina --email user@example.com --password xxx
    python upload_global_source_to_api.py --source gogi --country Argentina --email user@example.com --password xxx
"""

import sys
import json
import argparse
import io
from pathlib import Path
from datetime import datetime
from typing import Dict

import requests
from requests.exceptions import RequestException
import pandas as pd


# Data source ID mapping
SOURCE_ID_MAP = {
    'cd': 2,      # Commercial Dataset
    'gogi': 3,    # GOGI
    'zhang': 4    # Zhang (future use)
}


class PyxisAPIClient:
    """Client for interacting with Pyxis API."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.token = None

    def login(self, email: str, password: str) -> bool:
        """Login to get JWT token."""
        url = f"{self.base_url}/api/v1/login/access-token"
        data = {"username": email, "password": password}

        try:
            response = requests.post(url, data=data, timeout=30)
            response.raise_for_status()

            result = response.json()
            self.token = result.get('access_token')
            print(f"✓ Logged in as {email}")
            return True

        except RequestException as e:
            print(f"❌ Login failed: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"   Response: {e.response.text}")
            return False

    def upload_data_entry(self, source_id: int, csv_data: bytes, config_json: Dict,
                         granularity: str, alias: str) -> int:
        """Upload a data entry with in-memory CSV and config."""
        if not self.token:
            raise ValueError("Not logged in")

        url = f"{self.base_url}/api/v1/data-entries/"
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

        url = f"{self.base_url}/api/v1/data-entries/{data_entry_id}/process"
        headers = {"Authorization": f"Bearer {self.token}"}
        params = {"prevent_self_matching": str(prevent_self_matching).lower()}

        try:
            response = requests.post(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            return response.json()

        except RequestException as e:
            print(f"❌ Processing trigger failed: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"   Response: {e.response.text}")
            raise

    def get_entry_status(self, data_entry_id: int) -> Dict:
        """Get status of a data entry."""
        if not self.token:
            raise ValueError("Not logged in")

        url = f"{self.base_url}/api/v1/data-entries/{data_entry_id}/status"
        headers = {"Authorization": f"Bearer {self.token}"}

        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()

        except RequestException as e:
            print(f"❌ Status check failed: {str(e)}")
            return {}


def upload_global_source(source: str, country: str, email: str, password: str,
                        base_url: str = "http://localhost:8000"):
    """
    Upload global source data to Pyxis API.

    Args:
        source: Source name (cd, gogi, zhang)
        country: Country name (e.g., Argentina)
        email: User email
        password: User password
        base_url: API base URL
    """
    print(f"=== Uploading {source.upper()} Data for {country} ===")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Validate source
    if source.lower() not in SOURCE_ID_MAP:
        print(f"❌ Invalid source: {source}")
        print(f"   Valid sources: {list(SOURCE_ID_MAP.keys())}")
        sys.exit(1)

    source_id = SOURCE_ID_MAP[source.lower()]

    # Construct file paths
    scripts_dir = Path(__file__).parent
    output_dir = scripts_dir.parent / 'output' / country.lower()
    csv_path = output_dir / f"{country.lower()}_pyxis_static_fields_{source.lower()}.csv"
    config_path = output_dir / f"{country.lower()}_pyxis_static_fields_config_{source.lower()}.json"

    # Check files exist
    if not csv_path.exists():
        print(f"❌ CSV file not found: {csv_path}")
        print(f"   Run extract_{source.lower()}_fields.py first")
        sys.exit(1)

    if not config_path.exists():
        print(f"❌ Config file not found: {config_path}")
        print(f"   Run extract_{source.lower()}_fields.py first")
        sys.exit(1)

    print(f"1. Loading data files:")
    print(f"   CSV: {csv_path.name}")
    print(f"   Config: {config_path.name}")

    # Load CSV
    df = pd.read_csv(csv_path)
    print(f"   Records: {len(df):,}")

    # Load config
    with open(config_path, 'r') as f:
        config = json.load(f)

    # Convert CSV to bytes
    csv_bytes = df.to_csv(index=False).encode('utf-8')
    print(f"   CSV size: {len(csv_bytes)/1024:.1f} KB")

    # Login
    print(f"\n2. Logging in to API at {base_url}...")
    client = PyxisAPIClient(base_url)
    if not client.login(email, password):
        sys.exit(1)

    # Upload
    alias = f"{country}_{source.upper()}_Static"
    print(f"\n3. Uploading data entry...")
    print(f"   Source ID: {source_id} ({source.upper()})")
    print(f"   Granularity: field")
    print(f"   Alias: {alias}")

    try:
        data_entry_id = client.upload_data_entry(
            source_id=source_id,
            csv_data=csv_bytes,
            config_json=config,
            granularity='field',
            alias=alias
        )
        print(f"   ✓ Data entry created: ID {data_entry_id}")

    except Exception as e:
        print(f"\n❌ Upload failed: {str(e)}")
        sys.exit(1)

    # Trigger processing
    print(f"\n4. Triggering processing...")
    try:
        result = client.trigger_processing(data_entry_id, prevent_self_matching=False)
        print(f"   ✓ Processing started")
        print(f"   Message: {result.get('message', 'N/A')}")

    except Exception as e:
        print(f"\n❌ Processing trigger failed: {str(e)}")
        print(f"   You can manually trigger processing via API")

    # Check initial status
    print(f"\n5. Checking status...")
    status = client.get_entry_status(data_entry_id)
    if status:
        print(f"   Status: {status.get('status', 'UNKNOWN')}")

    print(f"\n✅ Upload complete!")
    print(f"   Data Entry ID: {data_entry_id}")
    print(f"   Monitor at: {base_url}/api/v1/data-entries/{data_entry_id}/status")
    print(f"\nFinished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


def main():
    parser = argparse.ArgumentParser(description='Upload global source data to Pyxis API')
    parser.add_argument('--source', type=str, required=True,
                       choices=['cd', 'gogi', 'zhang'],
                       help='Data source (cd, gogi, zhang)')
    parser.add_argument('--country', type=str, required=True,
                       help='Country name (e.g., Argentina)')
    parser.add_argument('--email', type=str, required=True,
                       help='User email for authentication')
    parser.add_argument('--password', type=str, required=True,
                       help='User password')
    parser.add_argument('--api-url', type=str, default='http://localhost:8000',
                       help='API base URL (default: http://localhost:8000)')

    args = parser.parse_args()

    upload_global_source(
        source=args.source,
        country=args.country,
        email=args.email,
        password=args.password,
        base_url=args.api_url
    )


if __name__ == "__main__":
    main()
