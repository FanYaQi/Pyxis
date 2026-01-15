#!/usr/bin/env python3
"""
Upload and process Argentina data using the batch processing API.

This script:
1. Logs in to get authentication token
2. Creates data sources with quality scores
3. Uploads all Argentina data entries (static + time-series)
4. Batch processes static data in quality order
5. Batch processes time-series data with source-based matching
6. Verifies results

Usage:
    python upload_argentina_data.py --email yaqif@stanford.edu --password yaqiyaqi
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import requests
from requests.exceptions import RequestException


# API Configuration
API_BASE = "http://localhost:8000"

# Data file paths (relative to project root)
# Script is in: data_preparation/argentina/scripts/
# Go up 3 levels to reach project root: /Users/yaqifan/Documents/Github/Pyxis
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
DATA_FILES = {
    "gov_static": {
        "csv": PROJECT_ROOT / "data_preparation/argentina/output/argentina_pyxis_static_fields.csv",
        "config": PROJECT_ROOT / "data_preparation/argentina/output/argentina_pyxis_static_fields_config.json",
        "alias": "Argentina Gov Static 2009-2024",
        "source": "Argentina Government"
    },
    "cd_static": {
        "csv": PROJECT_ROOT / "data_preparation/global_sources/output/argentina/argentina_pyxis_static_fields_cd.csv",
        "config": PROJECT_ROOT / "data_preparation/global_sources/output/argentina/argentina_pyxis_static_fields_config_cd.json",
        "alias": "Argentina CD Static",
        "source": "Commercial Dataset (CD)"
    },
    "gogi_static": {
        "csv": PROJECT_ROOT / "data_preparation/global_sources/output/argentina/argentina_pyxis_static_fields_gogi.csv",
        "config": PROJECT_ROOT / "data_preparation/global_sources/output/argentina/argentina_pyxis_static_fields_config_gogi.json",
        "alias": "Argentina GOGI Static",
        "source": "GOGI"
    }
}

# Data source configurations
DATA_SOURCES = [
    {
        "name": "Argentina Government",
        "description": "Official government data from Argentina Secretary of Energy",
        "urls": ["https://datos.energia.gob.ar/"],
        "source_type": "government",
        "data_access_type": "file_upload",
        "reliability_score": 5.0,
        "recency_score": 4.0,
        "richness_score": 4.5,
        "pyxis_score": 4.5
    },
    {
        "name": "Commercial Dataset (CD)",
        "description": "Commercial third-party oil and gas field data",
        "urls": [],
        "source_type": "commercial",
        "data_access_type": "file_upload",
        "reliability_score": 4.0,
        "recency_score": 3.0,
        "richness_score": 4.0,
        "pyxis_score": 3.5
    },
    {
        "name": "GOGI",
        "description": "Global Oil & Gas Intelligence dataset",
        "urls": [],
        "source_type": "commercial",
        "data_access_type": "file_upload",
        "reliability_score": 3.0,
        "recency_score": 3.0,
        "richness_score": 3.0,
        "pyxis_score": 3.0
    }
]


class PyxisAPIClient:
    """Client for interacting with Pyxis API."""

    def __init__(self, base_url: str = API_BASE):
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

    def create_data_source(self, source_config: Dict) -> Optional[int]:
        """Create a data source and return its ID."""
        if not self.token:
            raise ValueError("Not logged in")

        url = f"{self.base_url}/api/v1/data-sources/"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(url, headers=headers, json=source_config, timeout=30)
            response.raise_for_status()

            result = response.json()
            source_id = result.get('id')
            print(f"✓ Created data source '{source_config['name']}' (ID: {source_id}, score: {source_config['pyxis_score']})")
            return source_id

        except RequestException as e:
            print(f"❌ Failed to create data source '{source_config['name']}': {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"   Response: {e.response.text}")
            return None

    def get_data_source_by_name(self, name: str) -> Optional[int]:
        """Get data source ID by name."""
        if not self.token:
            raise ValueError("Not logged in")

        url = f"{self.base_url}/api/v1/data-sources/"
        headers = {"Authorization": f"Bearer {self.token}"}

        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            sources = response.json()
            for source in sources:
                if source.get('name') == name:
                    return source.get('id')

            return None

        except RequestException as e:
            print(f"❌ Failed to fetch data sources: {str(e)}")
            return None

    def upload_data_entry(
        self,
        source_id: int,
        csv_path: Path,
        config_path: Path,
        alias: str,
        granularity: str = "field"
    ) -> Optional[int]:
        """Upload a data entry and return its ID."""
        if not self.token:
            raise ValueError("Not logged in")

        url = f"{self.base_url}/api/v1/data-entries/"
        headers = {"Authorization": f"Bearer {self.token}"}

        files = {
            'data_file': (csv_path.name, open(csv_path, 'rb'), 'text/csv'),
            'config_file': (config_path.name, open(config_path, 'rb'), 'application/json')
        }

        data = {
            'source_id': str(source_id),
            'granularity': granularity,
            'alias': alias
        }

        try:
            response = requests.post(url, headers=headers, files=files, data=data, timeout=120)
            response.raise_for_status()

            result = response.json()
            # Response format: {"data_entry": {...}, "message": "..."}
            entry_id = result.get('data_entry', {}).get('id') or result.get('id')
            if not entry_id:
                print(f"⚠️  Upload response for '{alias}': {result}")
            print(f"✓ Uploaded '{alias}' (Entry ID: {entry_id})")
            return entry_id

        except RequestException as e:
            print(f"❌ Failed to upload '{alias}': {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"   Response: {e.response.text}")
            return None
        finally:
            # Close file handles
            for f in files.values():
                if hasattr(f[1], 'close'):
                    f[1].close()

    def batch_process_entries(self, request: Dict) -> Optional[Dict]:
        """Batch process data entries."""
        if not self.token:
            raise ValueError("Not logged in")

        url = f"{self.base_url}/api/v1/data-entries/batch-process"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

        try:
            print(f"\n⚙️  Processing {len(request['entries'])} entries (sequence: {request['match_sequence']})...")
            response = requests.post(url, headers=headers, json=request, timeout=3600)
            response.raise_for_status()

            result = response.json()
            return result

        except RequestException as e:
            print(f"❌ Batch processing failed: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"   Response: {e.response.text}")
            return None


def print_batch_results(result: Dict):
    """Pretty print batch processing results."""
    print("\n" + "="*60)
    print("BATCH PROCESSING RESULTS")
    print("="*60)
    print(f"Total entries: {result['total_entries']}")
    print(f"Completed: {result['completed']}")
    print(f"Failed: {result['failed']}")
    print(f"Processing time: {result['total_processing_time_seconds']:.2f}s")
    print(f"Processing order: {result['processing_order']}")

    print("\nPer-entry results:")
    for entry_result in result['results']:
        status_icon = "✓" if entry_result['status'] == 'COMPLETED' else "❌"
        print(f"  {status_icon} Entry {entry_result['entry_id']} ({entry_result['alias']})")
        print(f"     Status: {entry_result['status']}")
        print(f"     Records created: {entry_result.get('records_created', 0)}")
        print(f"     Fields created: {entry_result.get('fields_created', 0)}")
        print(f"     Fields matched: {entry_result.get('fields_matched', 0)}")
        print(f"     Time: {entry_result.get('processing_time_seconds', 0):.2f}s")
        if entry_result.get('error_message'):
            print(f"     Error: {entry_result['error_message']}")


def main():
    parser = argparse.ArgumentParser(description="Upload and process Argentina data")
    parser.add_argument("--email", required=True, help="User email")
    parser.add_argument("--password", required=True, help="User password")
    parser.add_argument("--skip-upload", action="store_true", help="Skip upload, only process")

    args = parser.parse_args()

    # Initialize client
    client = PyxisAPIClient()

    # Step 1: Login
    print("\n" + "="*60)
    print("STEP 1: LOGIN")
    print("="*60)
    if not client.login(args.email, args.password):
        sys.exit(1)

    # Step 2: Create or get data sources
    print("\n" + "="*60)
    print("STEP 2: CREATE DATA SOURCES")
    print("="*60)
    source_name_to_id = {}
    for source_config in DATA_SOURCES:
        existing_id = client.get_data_source_by_name(source_config['name'])
        if existing_id:
            print(f"✓ Data source '{source_config['name']}' already exists (ID: {existing_id})")
            source_name_to_id[source_config['name']] = existing_id
        else:
            source_id = client.create_data_source(source_config)
            if source_id:
                source_name_to_id[source_config['name']] = source_id

    if not args.skip_upload:
        # Step 3: Upload data entries
        print("\n" + "="*60)
        print("STEP 3: UPLOAD DATA ENTRIES")
        print("="*60)
        entry_ids = {}
        for key, file_info in DATA_FILES.items():
            source_id = source_name_to_id.get(file_info['source'])
            if not source_id:
                print(f"⚠️  Skipping '{key}' - source not found")
                continue

            if not file_info['csv'].exists():
                print(f"⚠️  Skipping '{key}' - file not found: {file_info['csv']}")
                continue

            entry_id = client.upload_data_entry(
                source_id=source_id,
                csv_path=file_info['csv'],
                config_path=file_info['config'],
                alias=file_info['alias']
            )
            if entry_id:
                entry_ids[key] = entry_id

        print(f"\n✓ Uploaded {len(entry_ids)} data entries")
    else:
        # If skipping upload, query for existing entries
        print("\n⚠️  Skipping upload - assuming entries already exist")
        print("   Please manually provide entry IDs or modify script")
        sys.exit(0)

    # Step 4: Batch process static data
    print("\n" + "="*60)
    print("STEP 4: BATCH PROCESS STATIC DATA")
    print("="*60)
    static_request = {
        "entries": [
            {
                "entry_id": entry_ids['gov_static'],
                "prevent_self_matching": True,
                "match_by_source_id": False
            },
            {
                "entry_id": entry_ids['cd_static'],
                "prevent_self_matching": False,
                "match_by_source_id": False
            },
            {
                "entry_id": entry_ids['gogi_static'],
                "prevent_self_matching": False,
                "match_by_source_id": False
            }
        ],
        "match_sequence": "source_score"
    }

    static_result = client.batch_process_entries(static_request)
    if static_result:
        print_batch_results(static_result)
    else:
        print("❌ Static data processing failed")
        sys.exit(1)

    # Step 5: Summary
    print("\n" + "="*60)
    print("STATIC DATA UPLOAD AND PROCESSING COMPLETE")
    print("="*60)
    print(f"Total static entries processed: {static_result['total_entries']}")
    print(f"Total processing time: {static_result['total_processing_time_seconds']:.2f}s")
    print("\nNext step: Upload monthly time-series data using 08_upload_monthly_to_api.py")


if __name__ == "__main__":
    main()
