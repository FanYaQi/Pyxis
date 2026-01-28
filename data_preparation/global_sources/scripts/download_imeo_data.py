#!/usr/bin/env python3
"""
Download methane emissions data from IMEO (International Methane Emissions Observatory).

IMEO provides methane emissions data for the oil and gas sector globally.
API Documentation: https://www.unep.org/explore-topics/energy/what-we-do/methane/imeo-data-portal

Usage:
    python download_imeo_data.py --api-token YOUR_TOKEN --output-dir ../methane_raw_imeo
    python download_imeo_data.py --api-token YOUR_TOKEN --country ARG
"""

import argparse
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

import requests
import pandas as pd

# IMEO API Configuration
IMEO_API_BASE = "https://imeo-api.unep.org/api/v1"
IMEO_API_TOKEN = "3os7P2xOWq7IPlIlbTFf8SPwuOdoZ4hINBIcisxbAZ3G55EG7Nc2U4cOnJGe6jX34u1mnSrLf7xciFVSksWrd4dDm37teWvR9jU0yOdmjzO69hEdjAHGYWYAv2Xl2Vae5nt9LiYZOedqpigmydsc1v"


class IMEODataDownloader:
    """Client for downloading data from IMEO API."""

    def __init__(self, api_token: str, base_url: str = IMEO_API_BASE):
        self.api_token = api_token
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }

    def get_emissions_data(
        self,
        country: Optional[str] = None,
        sector: str = "oil_and_gas",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict]:
        """
        Fetch methane emissions data from IMEO API.

        Args:
            country: Country ISO code (e.g., "ARG" for Argentina)
            sector: Sector filter (default: "oil_and_gas")
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format

        Returns:
            List of emission records
        """
        endpoint = f"{self.base_url}/emissions"

        params = {}
        if country:
            params["country"] = country
        if sector:
            params["sector"] = sector
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date

        print(f"Fetching emissions data from IMEO API...")
        print(f"  Endpoint: {endpoint}")
        print(f"  Parameters: {params}")

        try:
            response = requests.get(
                endpoint,
                headers=self.headers,
                params=params,
                timeout=60,
                verify=True
            )
            response.raise_for_status()

            data = response.json()
            records = data.get("results", []) or data.get("data", []) or (data if isinstance(data, list) else [])
            print(f"✓ Retrieved {len(records)} emission records")
            return records

        except requests.exceptions.SSLError as e:
            print(f"❌ SSL Error: {e}")
            print(f"   Try: Check if API endpoint URL is correct")
            return []
        except requests.exceptions.HTTPError as e:
            print(f"❌ HTTP Error: {e}")
            if e.response is not None:
                print(f"   Status Code: {e.response.status_code}")
                print(f"   Response: {e.response.text[:500]}")
            return []
        except Exception as e:
            print(f"❌ Error fetching emissions data: {e}")
            return []

    def get_facilities_data(
        self,
        country: Optional[str] = None,
        facility_type: str = "oil_and_gas"
    ) -> List[Dict]:
        """
        Fetch facility/infrastructure data from IMEO API.

        Args:
            country: Country ISO code
            facility_type: Type of facilities to fetch

        Returns:
            List of facility records
        """
        endpoint = f"{self.base_url}/facilities"

        params = {}
        if facility_type:
            params["type"] = facility_type
        if country:
            params["country"] = country

        print(f"Fetching facilities data from IMEO API...")
        print(f"  Endpoint: {endpoint}")
        print(f"  Parameters: {params}")

        try:
            response = requests.get(
                endpoint,
                headers=self.headers,
                params=params,
                timeout=60,
                verify=True
            )
            response.raise_for_status()

            data = response.json()
            records = data.get("results", []) or data.get("data", []) or (data if isinstance(data, list) else [])
            print(f"✓ Retrieved {len(records)} facility records")
            return records

        except requests.exceptions.SSLError as e:
            print(f"❌ SSL Error: {e}")
            print(f"   Try: Check if API endpoint URL is correct")
            return []
        except requests.exceptions.HTTPError as e:
            print(f"❌ HTTP Error: {e}")
            if e.response is not None:
                print(f"   Status Code: {e.response.status_code}")
                print(f"   Response: {e.response.text[:500]}")
            return []
        except Exception as e:
            print(f"❌ Error fetching facilities data: {e}")
            return []


def save_data(records: List[Dict], output_path: Path, format: str = "csv"):
    """Save records to file in specified format."""
    if not records:
        print("⚠ No records to save")
        return

    df = pd.DataFrame(records)

    if format == "csv":
        df.to_csv(output_path, index=False)
        print(f"✓ Saved {len(records)} records to {output_path}")
    elif format == "json":
        with open(output_path, 'w') as f:
            json.dump(records, f, indent=2)
        print(f"✓ Saved {len(records)} records to {output_path}")
    else:
        raise ValueError(f"Unsupported format: {format}")


def main():
    parser = argparse.ArgumentParser(
        description="Download methane emissions data from IMEO API"
    )
    parser.add_argument(
        "--api-token",
        type=str,
        required=True,
        help="IMEO API token (required)"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("../methane_raw_imeo"),
        help="Output directory for downloaded data"
    )
    parser.add_argument(
        "--country",
        type=str,
        help="Country ISO code (e.g., ARG for Argentina)"
    )
    parser.add_argument(
        "--start-date",
        type=str,
        help="Start date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--end-date",
        type=str,
        help="End date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--format",
        choices=["csv", "json"],
        default="csv",
        help="Output format"
    )

    args = parser.parse_args()

    # Create output directory
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Initialize downloader with API token from command line
    downloader = IMEODataDownloader(args.api_token)

    # Generate timestamp for filenames
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Download emissions data
    print("\n" + "="*60)
    print("DOWNLOADING EMISSIONS DATA")
    print("="*60)
    emissions = downloader.get_emissions_data(
        country=args.country,
        start_date=args.start_date,
        end_date=args.end_date
    )

    if emissions:
        filename = f"imeo_emissions_{args.country or 'global'}_{timestamp}.{args.format}"
        save_data(emissions, args.output_dir / filename, args.format)

    # Download facilities data
    print("\n" + "="*60)
    print("DOWNLOADING FACILITIES DATA")
    print("="*60)
    facilities = downloader.get_facilities_data(country=args.country)

    if facilities:
        filename = f"imeo_facilities_{args.country or 'global'}_{timestamp}.{args.format}"
        save_data(facilities, args.output_dir / filename, args.format)

    print("\n" + "="*60)
    print("DOWNLOAD COMPLETE")
    print("="*60)
    print(f"Output directory: {args.output_dir}")
    print(f"Total emissions records: {len(emissions)}")
    print(f"Total facility records: {len(facilities)}")


if __name__ == "__main__":
    main()
