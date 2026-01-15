#!/usr/bin/env python3
"""Generate OPGEE CSV for Argentina oil fields - January 2021"""

import requests
import json

API_BASE = "http://localhost:8000"

# Get token
response = requests.post(
    f"{API_BASE}/api/v1/login/access-token",
    data={"username": "test@example.com", "password": "testpassword123"},
    headers={"Content-Type": "application/x-www-form-urlencoded"}
)
token = response.json()["access_token"]

# Generate OPGEE input
print("Generating OPGEE input for Argentina oil fields (January 2021)...")
response = requests.post(
    f"{API_BASE}/api/v1/opgee/generate-input",
    headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    },
    json={
        "start_date": "2021-01-01",
        "end_date": "2021-01-31",
        "country": "Argentina",
        "production_type": "oil",
        "require_multi_source_coverage": False,
        "csv_output_path": "/Users/yaqifan/Documents/Github/Pyxis/data_preparation/global_sources/output/argentina/argentina_oil_fields_opgee_2021-01.csv"
    }
)

result = response.json()
print(json.dumps(result, indent=2))

if result.get("csv_file_path"):
    print(f"\n✓ CSV saved to: {result['csv_file_path']}")
