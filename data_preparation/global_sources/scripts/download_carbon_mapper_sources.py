#!/usr/bin/env python3
"""
Download Carbon Mapper source-level methane emission data.

This script uses the /catalog/sources.geojson API endpoint to get pre-clustered
emission sources with:
- Persistent source IDs
- Pre-calculated persistence (detection days / observation days)
- Linked plume IDs
- Aggregated emission statistics

Usage:
    python download_carbon_mapper_sources.py --country argentina
    python download_carbon_mapper_sources.py --bbox -73.5,-55.0,-53.6,-21.8
    python download_carbon_mapper_sources.py --country usa --sector 1B2
"""

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests
from requests.exceptions import RequestException

API_BASE_URL = "https://api.carbonmapper.org/api/v1"

# Country bounding boxes (min_lon, min_lat, max_lon, max_lat)
COUNTRY_BBOX = {
    "argentina": (-73.5, -55.0, -53.6, -21.8),
    "usa": (-125.0, 24.0, -66.0, 49.0),
    "mexico": (-118.0, 14.5, -86.0, 32.7),
    "permian": (-104.5, 30.5, -101.5, 33.5),  # Permian Basin
}

SCRIPTS_DIR = Path(__file__).parent
RAW_DIR = SCRIPTS_DIR.parent / "methane_CM_raw"
PROCESSED_DIR = SCRIPTS_DIR.parent / "methane_CM_processed"


class CarbonMapperClient:
    def __init__(self, token: Optional[str] = None):
        """Initialize client. Token is optional for sources endpoint."""
        self.base_url = API_BASE_URL
        self.headers = {"Accept": "application/json"}
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

    def fetch_sources_geojson(
        self,
        sectors: Optional[List[str]] = None,
        plume_gas: str = "CH4",
        status: str = "published",
        instruments: Optional[List[str]] = None,
        datetime_range: Optional[str] = None,
    ) -> Dict:
        """
        Fetch all sources as GeoJSON from the API.

        Note: bbox filtering doesn't work well in the API, so we fetch all
        and filter locally.
        """
        url = f"{self.base_url}/catalog/sources.geojson"
        params = {
            "plume_gas": plume_gas,
            "status": status,
        }

        if sectors:
            params["sectors"] = sectors
        if instruments:
            params["instruments"] = instruments
        if datetime_range:
            params["datetime"] = datetime_range

        print(f"\n📡 Fetching sources from Carbon Mapper API...")
        print(f"   URL: {url}")
        print(f"   Params: {params}")

        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=120)
            response.raise_for_status()
            data = response.json()
            print(f"   ✅ Retrieved {len(data.get('features', []))} sources")
            return data
        except RequestException as exc:
            print(f"❌ API request failed: {exc}")
            if hasattr(exc, "response") and exc.response is not None:
                print(f"   Response: {exc.response.text[:500]}")
            raise

    def fetch_source_plumes(
        self,
        source_name: str,
        status: str = "published",
    ) -> List[Dict]:
        """Fetch all plumes for a specific source."""
        # Parse source name components
        # Format: CH4_1B2_500m_-69.34834_-52.66638
        parts = source_name.split("_")
        if len(parts) < 5:
            print(f"   ⚠️ Invalid source name format: {source_name}")
            return []

        gas = parts[0]
        sector = parts[1]
        eps = parts[2]
        lon = parts[3]
        lat = parts[4]

        url = f"{self.base_url}/catalog/source-plumes-csv/{gas}_{sector}_{eps}_{lon}_{lat}"
        params = {"status": status}

        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=60)
            response.raise_for_status()
            # Parse CSV response
            from io import StringIO
            df = pd.read_csv(StringIO(response.text))
            return df.to_dict("records")
        except RequestException as exc:
            print(f"   ⚠️ Failed to fetch plumes for {source_name}: {exc}")
            return []


def filter_sources_by_bbox(
    features: List[Dict],
    bbox: Tuple[float, float, float, float],
) -> List[Dict]:
    """Filter GeoJSON features by bounding box."""
    min_lon, min_lat, max_lon, max_lat = bbox
    filtered = []
    for f in features:
        coords = f["geometry"]["coordinates"]
        lon, lat = coords[0], coords[1]
        if min_lon <= lon <= max_lon and min_lat <= lat <= max_lat:
            filtered.append(f)
    return filtered


def process_sources(features: List[Dict]) -> pd.DataFrame:
    """
    Process source features into a clean DataFrame with:
    - source_id, source_name
    - geometry (lon, lat)
    - plume_count, plume_ids
    - observation_date_count, detection_date_count
    - persistence
    - emission_auto (mean emission when detected)
    - persistence_adjusted_emission (emission × persistence)
    """
    records = []

    for f in features:
        props = f["properties"]
        coords = f["geometry"]["coordinates"]

        # Clean source name (remove query params if present)
        source_name = props.get("source_name", "")
        if "?" in source_name:
            source_name = source_name.split("?")[0]

        # Get emission values
        emission_auto = props.get("emission_auto")
        persistence = props.get("persistence")

        # Calculate persistence-adjusted emission
        # This is the expected emission rate accounting for non-detection days
        persistence_adjusted = None
        if emission_auto is not None and persistence is not None:
            persistence_adjusted = emission_auto * persistence

        records.append({
            "source_id": f.get("id", "").split("?")[0],
            "source_name": source_name,
            "longitude": coords[0],
            "latitude": coords[1],
            "gas": props.get("gas"),
            "sector": props.get("sector"),
            "plume_count": props.get("plume_count"),
            "plume_ids": json.dumps(props.get("plume_ids", [])),
            "observation_date_count": props.get("observation_date_count"),
            "detection_date_count": props.get("detection_date_count"),
            "persistence": persistence,
            "emission_auto_kg_hr": emission_auto,
            "emission_uncertainty_kg_hr": props.get("emission_uncertainty_auto"),
            "persistence_adjusted_emission_kg_hr": persistence_adjusted,
            "timestamp_min": props.get("timestamp_min"),
            "timestamp_max": props.get("timestamp_max"),
            "published_at_min": props.get("published_at_min"),
            "published_at_max": props.get("published_at_max"),
        })

    df = pd.DataFrame(records)

    # Convert dates
    for col in ["timestamp_min", "timestamp_max", "published_at_min", "published_at_max"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    return df


def generate_summary_stats(df: pd.DataFrame) -> Dict:
    """Generate summary statistics for the processed data."""
    valid_persistence = df["persistence"].dropna()
    valid_emissions = df["emission_auto_kg_hr"].dropna()
    valid_adjusted = df["persistence_adjusted_emission_kg_hr"].dropna()

    summary = {
        "total_sources": len(df),
        "total_plumes": int(df["plume_count"].sum()) if not df["plume_count"].isna().all() else 0,
        "sources_with_persistence": len(valid_persistence),
        "mean_persistence": float(valid_persistence.mean()) if len(valid_persistence) > 0 else None,
        "median_persistence": float(valid_persistence.median()) if len(valid_persistence) > 0 else None,
        "mean_emission_kg_hr": float(valid_emissions.mean()) if len(valid_emissions) > 0 else None,
        "median_emission_kg_hr": float(valid_emissions.median()) if len(valid_emissions) > 0 else None,
        "mean_persistence_adjusted_emission_kg_hr": float(valid_adjusted.mean()) if len(valid_adjusted) > 0 else None,
        "total_observation_days": int(df["observation_date_count"].sum()) if not df["observation_date_count"].isna().all() else 0,
        "total_detection_days": int(df["detection_date_count"].sum()) if not df["detection_date_count"].isna().all() else 0,
    }

    # By sector breakdown
    if "sector" in df.columns:
        sector_counts = df["sector"].value_counts().to_dict()
        summary["sources_by_sector"] = sector_counts

    return summary


def download_sources(
    country: Optional[str] = None,
    bbox: Optional[str] = None,
    sectors: Optional[List[str]] = None,
    plume_gas: str = "CH4",
    instruments: Optional[List[str]] = None,
    datetime_range: Optional[str] = None,
    output_name: Optional[str] = None,
    token: Optional[str] = None,
) -> None:
    """
    Download and process Carbon Mapper source data.

    Args:
        country: Country name (argentina, usa, mexico, permian)
        bbox: Bounding box as "min_lon,min_lat,max_lon,max_lat"
        sectors: List of sectors to filter (e.g., ["1B2"] for Oil & Gas)
        plume_gas: Gas type (CH4 or CO2)
        instruments: List of instruments to filter
        datetime_range: Date range filter (RFC 3339 format)
        output_name: Output filename prefix
        token: API token (optional)
    """
    # Determine bounding box
    bbox_tuple = None
    region_name = "global"

    if country:
        country_lower = country.lower()
        if country_lower not in COUNTRY_BBOX:
            raise ValueError(f"Unknown country: {country}. Available: {list(COUNTRY_BBOX.keys())}")
        bbox_tuple = COUNTRY_BBOX[country_lower]
        region_name = country_lower
    elif bbox:
        bbox_tuple = tuple(map(float, bbox.split(",")))
        if len(bbox_tuple) != 4:
            raise ValueError("Invalid bbox format. Use: min_lon,min_lat,max_lon,max_lat")
        region_name = "custom"

    # Create output directories
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    # Initialize client
    client = CarbonMapperClient(token=token or os.environ.get("CARBON_MAPPER_API_TOKEN"))

    # Fetch sources
    data = client.fetch_sources_geojson(
        sectors=sectors,
        plume_gas=plume_gas,
        instruments=instruments,
        datetime_range=datetime_range,
    )

    features = data.get("features", [])
    if not features:
        print("⚠️ No sources found.")
        return

    # Filter by bbox if specified
    if bbox_tuple:
        print(f"\n📍 Filtering for region: {region_name}")
        print(f"   Bbox: {bbox_tuple}")
        features = filter_sources_by_bbox(features, bbox_tuple)
        print(f"   Sources in region: {len(features)}")

    if not features:
        print("⚠️ No sources found in the specified region.")
        return

    # Generate filenames
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = output_name or f"{plume_gas.lower()}_{region_name}_sources"
    file_prefix = f"{base_name}_{timestamp}"

    # Save raw GeoJSON
    raw_geojson = {"type": "FeatureCollection", "features": features}
    raw_path = RAW_DIR / f"{file_prefix}_raw.geojson"
    with raw_path.open("w") as f:
        json.dump(raw_geojson, f, indent=2)
    print(f"\n📁 Saved raw GeoJSON: {raw_path.name}")

    # Process to DataFrame
    print("\n⚙️ Processing source data...")
    df = process_sources(features)

    # Save processed CSV
    processed_path = PROCESSED_DIR / f"{file_prefix}_processed.csv"
    df.to_csv(processed_path, index=False)
    print(f"📊 Saved processed CSV: {processed_path.name}")

    # Generate and save summary
    summary = generate_summary_stats(df)
    summary["region"] = region_name
    summary["bbox"] = list(bbox_tuple) if bbox_tuple else None
    summary["gas"] = plume_gas
    summary["sectors"] = sectors
    summary["timestamp"] = timestamp

    summary_path = PROCESSED_DIR / f"{file_prefix}_summary.json"
    with summary_path.open("w") as f:
        json.dump(summary, f, indent=2)
    print(f"📌 Saved summary: {summary_path.name}")

    # Print summary
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    print(f"Total sources: {summary['total_sources']}")
    print(f"Total plumes: {summary['total_plumes']}")
    if summary["mean_persistence"]:
        print(f"Mean persistence: {summary['mean_persistence']:.1%}")
    if summary["mean_emission_kg_hr"]:
        print(f"Mean emission (when detected): {summary['mean_emission_kg_hr']:.1f} kg/hr")
    if summary["mean_persistence_adjusted_emission_kg_hr"]:
        print(f"Mean persistence-adjusted emission: {summary['mean_persistence_adjusted_emission_kg_hr']:.1f} kg/hr")

    # Show top emitters
    if not df.empty:
        print("\n📊 Top 5 sources by persistence-adjusted emission:")
        top_sources = df.nlargest(5, "persistence_adjusted_emission_kg_hr")
        for _, row in top_sources.iterrows():
            print(f"   {row['source_name']}")
            print(f"      Emission: {row['emission_auto_kg_hr']:.0f} kg/hr × {row['persistence']:.0%} = {row['persistence_adjusted_emission_kg_hr']:.0f} kg/hr")
            print(f"      Plumes: {row['plume_count']}, Obs days: {row['observation_date_count']}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download Carbon Mapper source-level emission data."
    )
    parser.add_argument(
        "--country",
        type=str,
        choices=list(COUNTRY_BBOX.keys()),
        help="Country/region to download",
    )
    parser.add_argument(
        "--bbox",
        type=str,
        help="Bounding box: min_lon,min_lat,max_lon,max_lat",
    )
    parser.add_argument(
        "--gas",
        type=str,
        default="CH4",
        choices=["CH4", "CO2"],
        help="Gas type (default: CH4)",
    )
    parser.add_argument(
        "--sector",
        action="append",
        dest="sectors",
        help="Sector filter (can specify multiple). 1B2=Oil&Gas, 6A=Landfills",
    )
    parser.add_argument(
        "--instrument",
        action="append",
        dest="instruments",
        help="Instrument filter (tan, emi, ang, GAO, av3)",
    )
    parser.add_argument(
        "--datetime",
        type=str,
        help="Date range filter (RFC 3339 format, e.g., 2024-01-01/2024-12-31)",
    )
    parser.add_argument(
        "--output-name",
        type=str,
        help="Output filename prefix",
    )
    parser.add_argument(
        "--token",
        type=str,
        help="API token (optional, can use CARBON_MAPPER_API_TOKEN env var)",
    )
    args = parser.parse_args()

    if not args.country and not args.bbox:
        print("⚠️ No region specified. Downloading global data (this may be large).")

    download_sources(
        country=args.country,
        bbox=args.bbox,
        sectors=args.sectors,
        plume_gas=args.gas,
        instruments=args.instruments,
        datetime_range=args.datetime,
        output_name=args.output_name,
        token=args.token,
    )


if __name__ == "__main__":
    main()
