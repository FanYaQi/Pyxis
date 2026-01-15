#!/usr/bin/env python3
"""
Upload ONLY static Argentina data (no time-series).

Usage:
    python upload_static_only.py --email yaqif@stanford.edu --password yaqiyaqi
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import requests
from requests.exceptions import RequestException


API_BASE = "http://localhost:8000"
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent

# Only static data files
STATIC_FILES = {
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

# Only 3 data sources
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
            return False

    def get_all_data_sources(self) -> List[Dict]:
        """Get all data sources."""
        if not self.token:
            raise ValueError("Not logged in")

        url = f"{self.base_url}/api/v1/data-sources/"
        headers = {"Authorization": f"Bearer {self.token}"}

        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except RequestException as e:
            print(f"❌ Failed to fetch data sources: {str(e)}")
            return []

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
            print(f"✓ Created '{source_config['name']}' (ID: {source_id}, score: {source_config['pyxis_score']})")
            return source_id
        except RequestException as e:
            print(f"❌ Failed to create '{source_config['name']}': {str(e)}")
            return None

    def upload_data_entry(self, source_id: int, csv_path: Path, config_path: Path, alias: str) -> Optional[int]:
        """Upload a data entry."""
        if not self.token:
            raise ValueError("Not logged in")

        url = f"{self.base_url}/api/v1/data-entries/"
        headers = {"Authorization": f"Bearer {self.token}"}

        with open(csv_path, 'rb') as csv_file, open(config_path, 'rb') as config_file:
            files = {
                'data_file': (csv_path.name, csv_file, 'text/csv'),
                'config_file': (config_path.name, config_file, 'application/json')
            }
            data = {
                'source_id': str(source_id),
                'granularity': 'field',
                'alias': alias
            }

            try:
                response = requests.post(url, headers=headers, files=files, data=data, timeout=120)
                response.raise_for_status()
                result = response.json()
                entry_id = result.get('id')
                print(f"✓ Uploaded '{alias}' (ID: {entry_id})")
                return entry_id
            except RequestException as e:
                print(f"❌ Upload failed for '{alias}': {str(e)}")
                if hasattr(e, 'response') and e.response is not None:
                    print(f"   Response: {e.response.text}")
                return None

    def batch_process_entries(self, entries: List[Dict], match_sequence: str = "source_score") -> Optional[Dict]:
        """Batch process entries."""
        if not self.token:
            raise ValueError("Not logged in")

        url = f"{self.base_url}/api/v1/data-entries/batch-process"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

        request_data = {
            "entries": entries,
            "match_sequence": match_sequence
        }

        try:
            print(f"\n⚙️  Processing {len(entries)} entries...")
            response = requests.post(url, headers=headers, json=request_data, timeout=3600)
            response.raise_for_status()
            return response.json()
        except RequestException as e:
            print(f"❌ Batch processing failed: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"   Response: {e.response.text}")
            return None


def print_results(result: Dict):
    """Print batch processing results."""
    print("\n" + "="*70)
    print("PROCESSING RESULTS")
    print("="*70)
    print(f"Total: {result['total_entries']} | Completed: {result['completed']} | Failed: {result['failed']}")
    print(f"Processing time: {result['total_processing_time_seconds']:.2f}s")
    print(f"Processing order: {result['processing_order']}")

    print("\nDetails:")
    for entry_result in result['results']:
        status_icon = "✅" if entry_result['status'] == 'COMPLETED' else "❌"
        print(f"\n{status_icon} Entry {entry_result['entry_id']}: {entry_result['alias']}")
        print(f"   Records: {entry_result.get('records_created', 0)} | "
              f"New fields: {entry_result.get('fields_created', 0)} | "
              f"Matched: {entry_result.get('fields_matched', 0)} | "
              f"Time: {entry_result.get('processing_time_seconds', 0):.1f}s")
        if entry_result.get('error_message'):
            print(f"   Error: {entry_result['error_message']}")


def main():
    parser = argparse.ArgumentParser(description="Upload Argentina static data only")
    parser.add_argument("--email", required=True, help="User email")
    parser.add_argument("--password", required=True, help="User password")
    args = parser.parse_args()

    client = PyxisAPIClient()

    # Step 1: Login
    print("="*70)
    print("STEP 1: LOGIN")
    print("="*70)
    if not client.login(args.email, args.password):
        sys.exit(1)

    # Step 2: Setup data sources (check for existing first)
    print("\n" + "="*70)
    print("STEP 2: SETUP DATA SOURCES")
    print("="*70)

    existing_sources = client.get_all_data_sources()
    existing_names = {s['name']: s['id'] for s in existing_sources}

    source_name_to_id = {}
    for source_config in DATA_SOURCES:
        name = source_config['name']
        if name in existing_names:
            source_id = existing_names[name]
            print(f"✓ '{name}' exists (ID: {source_id})")
            source_name_to_id[name] = source_id
        else:
            source_id = client.create_data_source(source_config)
            if source_id:
                source_name_to_id[name] = source_id

    if len(source_name_to_id) != 3:
        print(f"\n❌ Expected 3 data sources, got {len(source_name_to_id)}")
        sys.exit(1)

    # Step 3: Upload static files
    print("\n" + "="*70)
    print("STEP 3: UPLOAD STATIC FILES")
    print("="*70)

    entry_ids = []
    for key, file_info in STATIC_FILES.items():
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
            entry_ids.append(entry_id)

    if len(entry_ids) != 3:
        print(f"\n❌ Expected 3 uploads, got {len(entry_ids)}")
        sys.exit(1)

    # Step 4: Batch process
    print("\n" + "="*70)
    print("STEP 4: BATCH PROCESS STATIC DATA")
    print("="*70)

    entries = [
        {"entry_id": entry_ids[0], "prevent_self_matching": True, "match_by_source_id": False},   # Gov
        {"entry_id": entry_ids[1], "prevent_self_matching": False, "match_by_source_id": False},  # CD
        {"entry_id": entry_ids[2], "prevent_self_matching": False, "match_by_source_id": False}   # GOGI
    ]

    result = client.batch_process_entries(entries, "source_score")
    if result:
        print_results(result)

        if result['failed'] == 0:
            print("\n" + "="*70)
            print("✅ SUCCESS - All static data processed!")
            print("="*70)
        else:
            print("\n⚠️  Some entries failed - check details above")
            sys.exit(1)
    else:
        print("\n❌ Batch processing failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
