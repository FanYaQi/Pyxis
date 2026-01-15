"""
Download methane plume data from Carbon Mapper API.

Usage:
    python download_carbon_mapper_plumes.py --country argentina
    python download_carbon_mapper_plumes.py --country argentina --gas CH4 --sector 1B2
    python download_carbon_mapper_plumes.py --bbox -73.5,-55.0,-53.6,-21.8 --start-date 2023-01-01
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from collections import Counter

import requests
from requests.exceptions import RequestException
import pandas as pd

# Carbon Mapper API configuration
API_BASE_URL = "https://api.carbonmapper.org/api/v1"
API_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzY0Mjk1MzEyLCJpYXQiOjE3NjM2OTA1MTIsImp0aSI6ImEyZGFlYjVkZjMwZDRjYjI5ZTlkOWVjMzUyNzE4NjcyIiwic2NvcGUiOiJzdGFjIGNhdGFsb2c6cmVhZCIsImdyb3VwcyI6IlB1YmxpYyIsImFsbF9ncm91cF9uYW1lcyI6eyJjb21tb24iOlsiUHVibGljIl19LCJvcmdhbml6YXRpb25zIjoiIiwic2V0dGluZ3MiOnt9LCJpc19zdGFmZiI6ZmFsc2UsImlzX3N1cGVydXNlciI6ZmFsc2UsInVzZXJfaWQiOjIxNDV9.1Jwa4lAWQnQ7HKWjQ1mRcHyEnfzBgjStp7LWB9ZKC8I"

# Country bounding boxes (min_lon, min_lat, max_lon, max_lat)
COUNTRY_BBOX = {
    'argentina': (-73.5, -55.0, -53.6, -21.8),
    'usa': (-125.0, 24.0, -66.0, 49.0),
    'mexico': (-118.0, 14.5, -86.0, 32.7),
}

# IPCC sector codes
SECTORS = {
    '1B2': 'Oil & Gas',
    '6A': 'Solid Waste',
    '6B': 'Wastewater',
    '4B': 'Agriculture',
    '1B1a': 'Coal Mining',
    '1A1': 'Energy',
    'other': 'Other',
    'NULL': 'Unclassified',
    'NA': 'Not Available'
}

# Paths
SCRIPTS_DIR = Path(__file__).parent
METHANE_RAW_DIR = SCRIPTS_DIR.parent / 'methane_raw'


class CarbonMapperClient:
    """Client for Carbon Mapper API."""

    def __init__(self, token: str = API_TOKEN):
        self.base_url = API_BASE_URL
        self.token = token
        self.headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }

    def fetch_plumes(
        self,
        bbox: Optional[Tuple[float, float, float, float]] = None,
        gas_type: Optional[str] = None,
        sectors: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 1000,
        offset: int = 0
    ) -> Dict:
        """
        Fetch plumes from Carbon Mapper API.

        Args:
            bbox: Bounding box (min_lon, min_lat, max_lon, max_lat)
            gas_type: Gas type filter ('CH4' or 'CO2')
            sectors: List of IPCC sector codes
            start_date: Start datetime (ISO format: 2023-01-01T00:00:00Z)
            end_date: End datetime (ISO format: 2024-12-31T23:59:59Z)
            limit: Number of results per page (max 1000)
            offset: Pagination offset

        Returns:
            API response dictionary
        """
        url = f"{self.base_url}/catalog/plumes/annotated"

        params = {
            'limit': limit,
            'offset': offset
        }

        if bbox:
            # bbox needs to be passed as array parameter
            # requests will handle it as bbox=val1&bbox=val2&bbox=val3&bbox=val4
            params['bbox'] = list(bbox)

        if gas_type:
            params['plume_gas'] = gas_type

        if sectors:
            params['sectors'] = sectors

        if start_date and end_date:
            params['datetime'] = f"{start_date}/{end_date}"
        elif start_date:
            params['datetime'] = f"{start_date}/.."
        elif end_date:
            params['datetime'] = f"../{end_date}"

        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=60)
            response.raise_for_status()
            return response.json()

        except RequestException as e:
            print(f"❌ API request failed: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"   Response: {e.response.text}")
            raise

    def fetch_all_plumes(
        self,
        bbox: Optional[Tuple[float, float, float, float]] = None,
        gas_type: Optional[str] = None,
        sectors: Optional[List[str]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        max_results: Optional[int] = None
    ) -> List[Dict]:
        """
        Fetch all plumes with pagination.

        Args:
            Same as fetch_plumes, plus:
            max_results: Maximum number of results to fetch (None = all)

        Returns:
            List of all plume dictionaries
        """
        all_plumes = []
        offset = 0
        limit = 1000
        total_count = None

        print(f"\n📡 Fetching plumes from Carbon Mapper API...")

        while True:
            print(f"   Fetching page: offset={offset}, limit={limit}")

            response = self.fetch_plumes(
                bbox=bbox,
                gas_type=gas_type,
                sectors=sectors,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
                offset=offset
            )

            plumes = response.get('items', [])
            if total_count is None:
                total_count = response.get('total_count', 0)
                print(f"   Total plumes available: {total_count:,}")

            if not plumes:
                break

            all_plumes.extend(plumes)
            print(f"   Retrieved {len(plumes)} plumes (total so far: {len(all_plumes):,})")

            # Check if we've reached max_results
            if max_results and len(all_plumes) >= max_results:
                all_plumes = all_plumes[:max_results]
                print(f"   Reached max_results limit: {max_results:,}")
                break

            # Check if we've retrieved all available plumes
            if len(all_plumes) >= total_count:
                break

            offset += limit

        print(f"\n✅ Downloaded {len(all_plumes):,} plumes")
        return all_plumes


def flatten_plume_data(plumes: List[Dict]) -> pd.DataFrame:
    """
    Flatten plume data into pandas DataFrame for analysis.

    Args:
        plumes: List of plume dictionaries from API

    Returns:
        DataFrame with key plume attributes
    """
    records = []

    for plume in plumes:
        # Extract geometry coordinates
        geometry = plume.get('geometry_json', {})
        if isinstance(geometry, str):
            geometry = json.loads(geometry)
        coords = geometry.get('coordinates', [None, None])

        record = {
            'plume_id': plume.get('plume_id'),
            'datetime': plume.get('scene_timestamp'),
            'latitude': coords[1] if len(coords) > 1 else None,
            'longitude': coords[0] if len(coords) > 0 else None,
            'gas': plume.get('gas'),
            'emission_rate_kg_hr': plume.get('emission_auto'),
            'emission_uncertainty_kg_hr': plume.get('emission_uncertainty_auto'),
            'sector': plume.get('sector'),
            'quality': plume.get('plume_quality'),
            'instrument': plume.get('instrument'),
            'platform': plume.get('platform'),
            'wind_speed_m_s': plume.get('wind_speed_avg_auto'),
            'wind_direction_deg': plume.get('wind_direction_avg_auto'),
            'is_offshore': plume.get('is_offshore'),
            'status': plume.get('status'),
            'published_at': plume.get('published_at'),
            'plume_bounds': json.dumps(plume.get('plume_bounds')) if plume.get('plume_bounds') else None,
        }

        records.append(record)

    return pd.DataFrame(records)


def generate_statistics(plumes: List[Dict], df: pd.DataFrame) -> str:
    """
    Generate statistics report from plume data.

    Args:
        plumes: Raw plume data
        df: Flattened DataFrame

    Returns:
        Statistics report as string
    """
    lines = []
    lines.append("=" * 80)
    lines.append("CARBON MAPPER PLUME DATA - STATISTICS REPORT")
    lines.append("=" * 80)
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    # Overall counts
    lines.append("OVERALL SUMMARY")
    lines.append("-" * 80)
    lines.append(f"Total plumes: {len(plumes):,}")
    lines.append("")

    # Gas type breakdown
    lines.append("GAS TYPE BREAKDOWN")
    lines.append("-" * 80)
    gas_counts = df['gas'].value_counts()
    for gas, count in gas_counts.items():
        pct = count / len(df) * 100
        lines.append(f"  {gas:10s} {count:6,} ({pct:5.1f}%)")
    lines.append("")

    # Sector breakdown
    lines.append("IPCC SECTOR BREAKDOWN")
    lines.append("-" * 80)
    sector_counts = df['sector'].value_counts(dropna=False)
    for sector, count in sector_counts.items():
        sector_name = SECTORS.get(str(sector) if sector else 'NULL', 'Unknown')
        pct = count / len(df) * 100
        lines.append(f"  {str(sector):10s} {sector_name:20s} {count:6,} ({pct:5.1f}%)")
    lines.append("")

    # Quality breakdown
    lines.append("QUALITY BREAKDOWN")
    lines.append("-" * 80)
    quality_counts = df['quality'].value_counts(dropna=False)
    for quality, count in quality_counts.items():
        pct = count / len(df) * 100
        quality_str = str(quality) if quality else 'NULL'
        lines.append(f"  {quality_str:15s} {count:6,} ({pct:5.1f}%)")
    lines.append("")

    # Instrument breakdown
    lines.append("INSTRUMENT/PLATFORM BREAKDOWN")
    lines.append("-" * 80)
    instrument_counts = df['instrument'].value_counts()
    for instrument, count in instrument_counts.items():
        platform = df[df['instrument'] == instrument]['platform'].iloc[0]
        pct = count / len(df) * 100
        lines.append(f"  {instrument:10s} ({platform:20s}) {count:6,} ({pct:5.1f}%)")
    lines.append("")

    # Emission statistics (for CH4 only)
    ch4_df = df[df['gas'] == 'CH4']
    if len(ch4_df) > 0:
        lines.append("METHANE EMISSION STATISTICS (kg/hr)")
        lines.append("-" * 80)
        emission_data = ch4_df['emission_rate_kg_hr'].dropna()
        if len(emission_data) > 0:
            lines.append(f"  Count:      {len(emission_data):,}")
            lines.append(f"  Mean:       {emission_data.mean():.2f}")
            lines.append(f"  Median:     {emission_data.median():.2f}")
            lines.append(f"  Std Dev:    {emission_data.std():.2f}")
            lines.append(f"  Min:        {emission_data.min():.2f}")
            lines.append(f"  Max:        {emission_data.max():.2f}")
            lines.append(f"  25th %ile:  {emission_data.quantile(0.25):.2f}")
            lines.append(f"  75th %ile:  {emission_data.quantile(0.75):.2f}")
            lines.append(f"  95th %ile:  {emission_data.quantile(0.95):.2f}")
        lines.append("")

    # Temporal distribution
    lines.append("TEMPORAL DISTRIBUTION")
    lines.append("-" * 80)
    df['year'] = pd.to_datetime(df['datetime'], format='ISO8601').dt.year
    year_counts = df['year'].value_counts().sort_index()
    for year, count in year_counts.items():
        pct = count / len(df) * 100
        lines.append(f"  {int(year):4d}  {count:6,} ({pct:5.1f}%)")
    lines.append("")

    # Geographic extent
    lines.append("GEOGRAPHIC EXTENT")
    lines.append("-" * 80)
    lat_data = df['latitude'].dropna()
    lon_data = df['longitude'].dropna()
    if len(lat_data) > 0 and len(lon_data) > 0:
        lines.append(f"  Latitude range:  {lat_data.min():.4f} to {lat_data.max():.4f}")
        lines.append(f"  Longitude range: {lon_data.min():.4f} to {lon_data.max():.4f}")
        lines.append(f"  Center:          ({lat_data.mean():.4f}, {lon_data.mean():.4f})")
    lines.append("")

    # Offshore vs onshore (for oil & gas sector)
    oil_gas_df = df[df['sector'] == '1B2']
    if len(oil_gas_df) > 0:
        lines.append("OIL & GAS SECTOR - OFFSHORE vs ONSHORE")
        lines.append("-" * 80)
        offshore_counts = oil_gas_df['is_offshore'].value_counts(dropna=False)
        for is_offshore, count in offshore_counts.items():
            pct = count / len(oil_gas_df) * 100
            location = 'Offshore' if is_offshore else 'Onshore' if is_offshore is False else 'Unknown'
            lines.append(f"  {location:10s} {count:6,} ({pct:5.1f}%)")
        lines.append("")

    lines.append("=" * 80)

    return "\n".join(lines)


def download_plumes(
    country: Optional[str] = None,
    bbox: Optional[str] = None,
    gas_type: Optional[str] = None,
    sector: Optional[str] = None,
    include_null_sectors: bool = False,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    max_results: Optional[int] = None,
    output_name: Optional[str] = None
):
    """
    Download plumes and save to files.

    Args:
        country: Country name (argentina, usa, mexico)
        bbox: Custom bounding box (min_lon,min_lat,max_lon,max_lat)
        gas_type: Gas type filter (CH4 or CO2)
        sector: IPCC sector code
        include_null_sectors: Include NULL/NA sectors
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        max_results: Maximum results to fetch
        output_name: Custom output filename prefix
    """
    print("=" * 80)
    print("CARBON MAPPER PLUME DOWNLOADER")
    print("=" * 80)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Determine bounding box
    bbox_tuple = None
    if country:
        country_lower = country.lower()
        if country_lower not in COUNTRY_BBOX:
            print(f"❌ Unknown country: {country}")
            print(f"   Available: {list(COUNTRY_BBOX.keys())}")
            sys.exit(1)
        bbox_tuple = COUNTRY_BBOX[country_lower]
        print(f"📍 Country: {country.upper()}")
        print(f"   Bounding box: {bbox_tuple}")
    elif bbox:
        try:
            bbox_tuple = tuple(map(float, bbox.split(',')))
            if len(bbox_tuple) != 4:
                raise ValueError
            print(f"📍 Custom bounding box: {bbox_tuple}")
        except ValueError:
            print(f"❌ Invalid bbox format. Use: min_lon,min_lat,max_lon,max_lat")
            sys.exit(1)

    # Format datetime for API
    api_start_date = None
    api_end_date = None
    if start_date:
        api_start_date = f"{start_date}T00:00:00Z"
        print(f"📅 Start date: {start_date}")
    if end_date:
        api_end_date = f"{end_date}T23:59:59Z"
        print(f"📅 End date: {end_date}")

    # Prepare sectors filter
    sectors_list = None
    if sector:
        sectors_list = [sector]
        print(f"🏭 Sector filter: {sector} ({SECTORS.get(sector, 'Unknown')})")
    if include_null_sectors:
        print(f"⚠️  Including NULL/NA sectors")

    if gas_type:
        print(f"💨 Gas filter: {gas_type}")

    # Create client and fetch data
    client = CarbonMapperClient()

    plumes = client.fetch_all_plumes(
        bbox=bbox_tuple,
        gas_type=gas_type,
        sectors=sectors_list,
        start_date=api_start_date,
        end_date=api_end_date,
        max_results=max_results
    )

    if len(plumes) == 0:
        print("\n⚠️  No plumes found matching criteria")
        print("   Try adjusting filters or expanding geographic/temporal range")
        return

    # Determine output directory and filename
    if country:
        output_dir = METHANE_RAW_DIR / country.lower()
    else:
        output_dir = METHANE_RAW_DIR / 'custom'

    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate output filename
    if output_name:
        base_name = output_name
    else:
        parts = []
        if country:
            parts.append(country.lower())
        if gas_type:
            parts.append(gas_type.lower())
        if sector:
            parts.append(sector.lower())
        if start_date or end_date:
            parts.append('filtered')
        base_name = '_'.join(parts) if parts else 'plumes'

    # Save raw JSON
    json_path = output_dir / f"{base_name}_raw.json"
    with open(json_path, 'w') as f:
        json.dump(plumes, f, indent=2)
    print(f"\n💾 Saved raw JSON: {json_path}")
    print(f"   File size: {json_path.stat().st_size / 1024:.1f} KB")

    # Convert to DataFrame and save CSV
    df = flatten_plume_data(plumes)
    csv_path = output_dir / f"{base_name}_summary.csv"
    df.to_csv(csv_path, index=False)
    print(f"💾 Saved summary CSV: {csv_path}")
    print(f"   Records: {len(df):,}")

    # Generate and save statistics
    stats = generate_statistics(plumes, df)
    stats_path = output_dir / f"{base_name}_statistics.txt"
    with open(stats_path, 'w') as f:
        f.write(stats)
    print(f"📊 Saved statistics: {stats_path}")

    # Save download metadata
    metadata = {
        'download_timestamp': datetime.now().isoformat(),
        'api_base_url': API_BASE_URL,
        'query_parameters': {
            'country': country,
            'bbox': bbox_tuple,
            'gas_type': gas_type,
            'sector': sector,
            'include_null_sectors': include_null_sectors,
            'start_date': start_date,
            'end_date': end_date,
            'max_results': max_results
        },
        'results': {
            'total_plumes': len(plumes),
            'output_files': {
                'raw_json': str(json_path),
                'summary_csv': str(csv_path),
                'statistics': str(stats_path)
            }
        }
    }
    metadata_path = output_dir / f"{base_name}_metadata.json"
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    print(f"📋 Saved metadata: {metadata_path}")

    # Print statistics summary
    print("\n" + stats)

    print(f"\n✅ Download complete!")
    print(f"   Total files: 4 (JSON, CSV, stats, metadata)")
    print(f"   Output directory: {output_dir}")
    print(f"\nFinished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


def main():
    parser = argparse.ArgumentParser(
        description='Download methane plume data from Carbon Mapper API',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download all plumes for Argentina
  python download_carbon_mapper_plumes.py --country argentina

  # Download only CH4 plumes from oil & gas sector
  python download_carbon_mapper_plumes.py --country argentina --gas CH4 --sector 1B2

  # Download with date range
  python download_carbon_mapper_plumes.py --country argentina --start-date 2023-01-01 --end-date 2024-12-31

  # Download for custom bounding box
  python download_carbon_mapper_plumes.py --bbox -120,35,-115,40 --gas CH4

  # Download USA data with result limit
  python download_carbon_mapper_plumes.py --country usa --max-results 5000
        """
    )

    parser.add_argument('--country', type=str, choices=['argentina', 'usa', 'mexico'],
                       help='Country to download data for')
    parser.add_argument('--bbox', type=str,
                       help='Custom bounding box: min_lon,min_lat,max_lon,max_lat')
    parser.add_argument('--gas', type=str, choices=['CH4', 'CO2'],
                       help='Gas type filter')
    parser.add_argument('--sector', type=str,
                       help='IPCC sector code (e.g., 1B2 for Oil & Gas)')
    parser.add_argument('--include-null-sectors', action='store_true',
                       help='Include plumes with NULL/NA sectors')
    parser.add_argument('--start-date', type=str,
                       help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str,
                       help='End date (YYYY-MM-DD)')
    parser.add_argument('--max-results', type=int,
                       help='Maximum number of results to fetch')
    parser.add_argument('--output-name', type=str,
                       help='Custom output filename prefix')

    args = parser.parse_args()

    # Validate arguments
    if not args.country and not args.bbox:
        parser.error("Either --country or --bbox must be specified")

    download_plumes(
        country=args.country,
        bbox=args.bbox,
        gas_type=args.gas,
        sector=args.sector,
        include_null_sectors=args.include_null_sectors,
        start_date=args.start_date,
        end_date=args.end_date,
        max_results=args.max_results,
        output_name=args.output_name
    )


if __name__ == "__main__":
    main()
