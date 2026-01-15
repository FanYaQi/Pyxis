"""
Download satellite scene (observation) data from Carbon Mapper API.

This script downloads ALL satellite observations, including null observations
(scenes where data was acquired but no plumes were detected).

Usage:
    python download_carbon_mapper_scenes.py --country argentina --instrument tan
    python download_carbon_mapper_scenes.py --country usa --instrument tan --not-cloudy
    python download_carbon_mapper_scenes.py --bbox -73.5,-55.0,-53.6,-21.8 --start-date 2023-01-01
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

    def fetch_scenes(
        self,
        bbox: Optional[Tuple[float, float, float, float]] = None,
        instruments: Optional[List[str]] = None,
        not_cloudy: Optional[bool] = None,
        cloud_cover_max: Optional[float] = None,
        plume_count_min: Optional[int] = None,
        plume_count_max: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 1000,
        offset: int = 0
    ) -> Dict:
        """
        Fetch scenes (satellite observations) from Carbon Mapper API.

        Args:
            bbox: Bounding box (min_lon, min_lat, max_lon, max_lat)
            instruments: List of instruments (e.g., ['tan', 'emi', 'ang'])
            not_cloudy: Filter to scenes with cloud_cover <= 25%
            cloud_cover_max: Maximum cloud cover percentage
            plume_count_min: Minimum published plume count
            plume_count_max: Maximum published plume count (use 0 for null observations)
            start_date: Start datetime (ISO format: 2023-01-01T00:00:00Z)
            end_date: End datetime (ISO format: 2024-12-31T23:59:59Z)
            limit: Number of results per page (max 1000)
            offset: Pagination offset

        Returns:
            API response dictionary
        """
        url = f"{self.base_url}/catalog/scenes/annotated"

        params = {
            'limit': limit,
            'offset': offset
        }

        if bbox:
            params['bbox'] = list(bbox)

        if instruments:
            params['instruments'] = instruments

        if not_cloudy is not None:
            params['not_cloudy'] = str(not_cloudy).lower()

        if cloud_cover_max is not None:
            params['cloud_cover_pct_max'] = cloud_cover_max

        if plume_count_min is not None:
            params['published_plume_count_min'] = plume_count_min

        if plume_count_max is not None:
            params['published_plume_count_max'] = plume_count_max

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

    def fetch_all_scenes(
        self,
        bbox: Optional[Tuple[float, float, float, float]] = None,
        instruments: Optional[List[str]] = None,
        not_cloudy: Optional[bool] = None,
        cloud_cover_max: Optional[float] = None,
        plume_count_min: Optional[int] = None,
        plume_count_max: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        max_results: Optional[int] = None
    ) -> List[Dict]:
        """
        Fetch all scenes with pagination.

        Args:
            Same as fetch_scenes, plus:
            max_results: Maximum number of results to fetch (None = all)

        Returns:
            List of all scene dictionaries
        """
        all_scenes = []
        offset = 0
        limit = 1000
        total_count = None

        print(f"\n📡 Fetching scenes from Carbon Mapper API...")

        while True:
            print(f"   Fetching page: offset={offset}, limit={limit}")

            response = self.fetch_scenes(
                bbox=bbox,
                instruments=instruments,
                not_cloudy=not_cloudy,
                cloud_cover_max=cloud_cover_max,
                plume_count_min=plume_count_min,
                plume_count_max=plume_count_max,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
                offset=offset
            )

            scenes = response.get('items', [])
            if total_count is None:
                total_count = response.get('total_count', 0)
                print(f"   Total scenes available: {total_count:,}")

            if not scenes:
                break

            all_scenes.extend(scenes)
            print(f"   Retrieved {len(scenes)} scenes (total so far: {len(all_scenes):,})")

            # Check if we've reached max_results
            if max_results and len(all_scenes) >= max_results:
                all_scenes = all_scenes[:max_results]
                print(f"   Reached max_results limit: {max_results:,}")
                break

            # Check if we've retrieved all available scenes
            if len(all_scenes) >= total_count:
                break

            offset += limit

        print(f"\n✅ Downloaded {len(all_scenes):,} scenes")
        return all_scenes


def flatten_scene_data(scenes: List[Dict]) -> pd.DataFrame:
    """
    Flatten scene data into pandas DataFrame for analysis.

    Args:
        scenes: List of scene dictionaries from API

    Returns:
        DataFrame with key scene attributes
    """
    records = []

    for scene in scenes:
        # Extract bounds
        bounds = scene.get('bounds', [None, None, None, None])

        record = {
            'scene_id': scene.get('id'),
            'name': scene.get('name'),
            'timestamp': scene.get('timestamp'),
            'published_plume_count': scene.get('published_plume_count', 0),
            'instrument': scene.get('instrument'),
            'platform': scene.get('platform'),
            'mission_phase': scene.get('mission_phase'),
            'cloud_cover_pct': scene.get('cloud_cover_pct'),
            'not_cloudy': scene.get('not_cloudy'),
            'area_sqkm': scene.get('area_sqkm'),
            'gsd': scene.get('gsd'),
            'sensitivity_mode': scene.get('sensitivity_mode'),
            'off_nadir': scene.get('off_nadir'),
            'solar_zenith_angle': scene.get('solar_zenith_angle'),
            'published_at': scene.get('published_at'),
            'modified': scene.get('modified'),
            'created': scene.get('created'),
            'bounds_min_lon': bounds[0] if len(bounds) > 0 else None,
            'bounds_min_lat': bounds[1] if len(bounds) > 1 else None,
            'bounds_max_lon': bounds[2] if len(bounds) > 2 else None,
            'bounds_max_lat': bounds[3] if len(bounds) > 3 else None,
        }

        records.append(record)

    return pd.DataFrame(records)


def generate_statistics(scenes: List[Dict], df: pd.DataFrame) -> str:
    """
    Generate statistics report from scene data.

    Args:
        scenes: Raw scene data
        df: Flattened DataFrame

    Returns:
        Statistics report as string
    """
    lines = []
    lines.append("=" * 80)
    lines.append("CARBON MAPPER SCENE DATA - STATISTICS REPORT")
    lines.append("=" * 80)
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    # Overall counts
    lines.append("OVERALL SUMMARY")
    lines.append("-" * 80)
    lines.append(f"Total scenes: {len(scenes):,}")
    lines.append("")

    # Plume detection breakdown
    lines.append("PLUME DETECTION BREAKDOWN")
    lines.append("-" * 80)
    null_obs = df[df['published_plume_count'] == 0]
    with_plumes = df[df['published_plume_count'] > 0]

    lines.append(f"  Scenes with 0 plumes (null observations): {len(null_obs):,} ({len(null_obs)/len(df)*100:.1f}%)")
    lines.append(f"  Scenes with 1+ plumes:                    {len(with_plumes):,} ({len(with_plumes)/len(df)*100:.1f}%)")

    if len(with_plumes) > 0:
        total_plumes = df['published_plume_count'].sum()
        lines.append(f"  Total plumes across all scenes:           {int(total_plumes):,}")
        lines.append(f"  Average plumes per scene (when >0):       {with_plumes['published_plume_count'].mean():.2f}")
        lines.append(f"  Max plumes in single scene:               {int(df['published_plume_count'].max()):,}")
    lines.append("")

    # Instrument/platform breakdown
    lines.append("INSTRUMENT/PLATFORM BREAKDOWN")
    lines.append("-" * 80)
    instrument_counts = df['instrument'].value_counts()
    for instrument, count in instrument_counts.items():
        inst_df = df[df['instrument'] == instrument]
        platform = inst_df['platform'].iloc[0] if len(inst_df) > 0 and pd.notna(inst_df['platform'].iloc[0]) else 'Unknown'
        pct = count / len(df) * 100
        inst_str = str(instrument) if pd.notna(instrument) else 'Unknown'
        lines.append(f"  {inst_str:10s} ({platform:20s}) {count:6,} ({pct:5.1f}%)")
    lines.append("")

    # Cloud cover statistics
    lines.append("CLOUD COVER STATISTICS")
    lines.append("-" * 80)
    cloud_data = df['cloud_cover_pct'].dropna()
    if len(cloud_data) > 0:
        lines.append(f"  Scenes with cloud data:     {len(cloud_data):,}")
        lines.append(f"  Mean cloud cover:           {cloud_data.mean():.1f}%")
        lines.append(f"  Median cloud cover:         {cloud_data.median():.1f}%")
        lines.append(f"  Min cloud cover:            {cloud_data.min():.1f}%")
        lines.append(f"  Max cloud cover:            {cloud_data.max():.1f}%")
        lines.append(f"  Cloud-free scenes (<= 25%): {len(df[df['not_cloudy'] == True]):,} ({len(df[df['not_cloudy'] == True])/len(df)*100:.1f}%)")
    lines.append("")

    # Temporal distribution
    lines.append("TEMPORAL DISTRIBUTION")
    lines.append("-" * 80)
    df['year'] = pd.to_datetime(df['timestamp'], format='ISO8601').dt.year
    df['month'] = pd.to_datetime(df['timestamp'], format='ISO8601').dt.to_period('M')

    year_counts = df['year'].value_counts().sort_index()
    for year, count in year_counts.items():
        pct = count / len(df) * 100
        lines.append(f"  {int(year):4d}  {count:6,} ({pct:5.1f}%)")

    lines.append("")
    lines.append("  Observation frequency:")
    month_counts = df['month'].value_counts().sort_index()
    if len(month_counts) > 0:
        lines.append(f"    Total months with observations: {len(month_counts)}")
        lines.append(f"    Average scenes per month:       {month_counts.mean():.1f}")
        lines.append(f"    Min scenes in a month:          {month_counts.min()}")
        lines.append(f"    Max scenes in a month:          {month_counts.max()}")
    lines.append("")

    # Geographic extent
    lines.append("GEOGRAPHIC EXTENT")
    lines.append("-" * 80)
    min_lat = df['bounds_min_lat'].min()
    max_lat = df['bounds_max_lat'].max()
    min_lon = df['bounds_min_lon'].min()
    max_lon = df['bounds_max_lon'].max()

    if pd.notna(min_lat) and pd.notna(max_lat):
        lines.append(f"  Latitude range:  {min_lat:.4f} to {max_lat:.4f}")
        lines.append(f"  Longitude range: {min_lon:.4f} to {max_lon:.4f}")

        # Calculate approximate area
        lat_diff = abs(max_lat - min_lat)
        lon_diff = abs(max_lon - min_lon)
        approx_area = lat_diff * lon_diff * 111 * 111  # Rough km² calculation
        lines.append(f"  Approximate area covered: {approx_area:,.0f} km²")

        total_scene_area = df['area_sqkm'].sum()
        if pd.notna(total_scene_area):
            lines.append(f"  Total scene area (sum):   {total_scene_area:,.0f} km²")
    lines.append("")

    # Detection rate analysis
    if len(with_plumes) > 0:
        lines.append("DETECTION RATE ANALYSIS")
        lines.append("-" * 80)
        detection_rate = len(with_plumes) / len(df) * 100
        lines.append(f"  Overall detection rate:          {detection_rate:.2f}%")

        # By instrument
        lines.append(f"  Detection rate by instrument:")
        for instrument in df['instrument'].unique():
            inst_df = df[df['instrument'] == instrument]
            inst_with_plumes = len(inst_df[inst_df['published_plume_count'] > 0])
            inst_rate = inst_with_plumes / len(inst_df) * 100 if len(inst_df) > 0 else 0
            lines.append(f"    {str(instrument):10s} {inst_rate:5.2f}% ({inst_with_plumes}/{len(inst_df)})")

        # By cloud condition
        if df['not_cloudy'].notna().any():
            clear_df = df[df['not_cloudy'] == True]
            cloudy_df = df[df['not_cloudy'] == False]
            if len(clear_df) > 0:
                clear_rate = len(clear_df[clear_df['published_plume_count'] > 0]) / len(clear_df) * 100
                lines.append(f"  Detection rate (cloud-free):     {clear_rate:.2f}%")
            if len(cloudy_df) > 0:
                cloudy_rate = len(cloudy_df[cloudy_df['published_plume_count'] > 0]) / len(cloudy_df) * 100
                lines.append(f"  Detection rate (cloudy):         {cloudy_rate:.2f}%")
        lines.append("")

    lines.append("=" * 80)

    return "\n".join(lines)


def download_scenes(
    country: Optional[str] = None,
    bbox: Optional[str] = None,
    instrument: Optional[str] = None,
    not_cloudy: bool = False,
    cloud_cover_max: Optional[float] = None,
    null_observations_only: bool = False,
    with_plumes_only: bool = False,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    max_results: Optional[int] = None,
    output_name: Optional[str] = None
):
    """
    Download scenes and save to files.

    Args:
        country: Country name (argentina, usa, mexico)
        bbox: Custom bounding box (min_lon,min_lat,max_lon,max_lat)
        instrument: Instrument filter (tan, emi, ang, av3)
        not_cloudy: Filter to cloud-free scenes only
        cloud_cover_max: Maximum cloud cover percentage
        null_observations_only: Only download scenes with 0 plumes
        with_plumes_only: Only download scenes with 1+ plumes
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        max_results: Maximum results to fetch
        output_name: Custom output filename prefix
    """
    print("=" * 80)
    print("CARBON MAPPER SCENE DOWNLOADER")
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

    # Prepare instrument filter
    instruments_list = None
    if instrument:
        instruments_list = [instrument]
        print(f"🛰️  Instrument filter: {instrument}")

    # Cloud filter
    if not_cloudy:
        print(f"☁️  Cloud filter: not_cloudy (<=25% cloud cover)")
    elif cloud_cover_max is not None:
        print(f"☁️  Cloud filter: max {cloud_cover_max}%")

    # Plume count filter
    plume_count_min = None
    plume_count_max = None
    if null_observations_only:
        plume_count_max = 0
        print(f"🔍 Filter: NULL OBSERVATIONS ONLY (0 plumes)")
    elif with_plumes_only:
        plume_count_min = 1
        print(f"🔍 Filter: WITH PLUMES ONLY (1+ plumes)")

    # Create client and fetch data
    client = CarbonMapperClient()

    scenes = client.fetch_all_scenes(
        bbox=bbox_tuple,
        instruments=instruments_list,
        not_cloudy=not_cloudy if not_cloudy else None,
        cloud_cover_max=cloud_cover_max,
        plume_count_min=plume_count_min,
        plume_count_max=plume_count_max,
        start_date=api_start_date,
        end_date=api_end_date,
        max_results=max_results
    )

    if len(scenes) == 0:
        print("\n⚠️  No scenes found matching criteria")
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
        if instrument:
            parts.append(instrument)
        if null_observations_only:
            parts.append('null_obs')
        elif with_plumes_only:
            parts.append('with_plumes')
        if not_cloudy:
            parts.append('cloudfree')
        parts.append('scenes')
        base_name = '_'.join(parts)

    # Save raw JSON
    json_path = output_dir / f"{base_name}_raw.json"
    with open(json_path, 'w') as f:
        json.dump(scenes, f, indent=2)
    print(f"\n💾 Saved raw JSON: {json_path}")
    print(f"   File size: {json_path.stat().st_size / 1024:.1f} KB")

    # Convert to DataFrame and save CSV
    df = flatten_scene_data(scenes)
    csv_path = output_dir / f"{base_name}_summary.csv"
    df.to_csv(csv_path, index=False)
    print(f"💾 Saved summary CSV: {csv_path}")
    print(f"   Records: {len(df):,}")

    # Generate and save statistics
    stats = generate_statistics(scenes, df)
    stats_path = output_dir / f"{base_name}_statistics.txt"
    with open(stats_path, 'w') as f:
        f.write(stats)
    print(f"📊 Saved statistics: {stats_path}")

    # Save download metadata
    metadata = {
        'download_timestamp': datetime.now().isoformat(),
        'api_base_url': API_BASE_URL,
        'endpoint': '/catalog/scenes/annotated',
        'query_parameters': {
            'country': country,
            'bbox': list(bbox_tuple) if bbox_tuple else None,
            'instrument': instrument,
            'not_cloudy': not_cloudy,
            'cloud_cover_max': cloud_cover_max,
            'null_observations_only': null_observations_only,
            'with_plumes_only': with_plumes_only,
            'start_date': start_date,
            'end_date': end_date,
            'max_results': max_results
        },
        'results': {
            'total_scenes': len(scenes),
            'scenes_with_plumes': len(df[df['published_plume_count'] > 0]),
            'null_observations': len(df[df['published_plume_count'] == 0]),
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
        description='Download satellite scene (observation) data from Carbon Mapper API',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download all scenes for Argentina
  python download_carbon_mapper_scenes.py --country argentina

  # Download only Tanager satellite scenes for Argentina
  python download_carbon_mapper_scenes.py --country argentina --instrument tan

  # Download cloud-free Tanager scenes
  python download_carbon_mapper_scenes.py --country argentina --instrument tan --not-cloudy

  # Download only null observations (0 plumes detected)
  python download_carbon_mapper_scenes.py --country argentina --null-observations-only

  # Download only scenes with plumes
  python download_carbon_mapper_scenes.py --country argentina --with-plumes-only

  # Download with date range
  python download_carbon_mapper_scenes.py --country argentina --start-date 2023-01-01 --end-date 2024-12-31

  # Download USA scenes with result limit
  python download_carbon_mapper_scenes.py --country usa --instrument tan --max-results 10000
        """
    )

    parser.add_argument('--country', type=str, choices=['argentina', 'usa', 'mexico'],
                       help='Country to download data for')
    parser.add_argument('--bbox', type=str,
                       help='Custom bounding box: min_lon,min_lat,max_lon,max_lat')
    parser.add_argument('--instrument', type=str, choices=['tan', 'emi', 'ang', 'av3'],
                       help='Instrument filter')
    parser.add_argument('--not-cloudy', action='store_true',
                       help='Filter to cloud-free scenes only (cloud cover <= 25%)')
    parser.add_argument('--cloud-cover-max', type=float,
                       help='Maximum cloud cover percentage')
    parser.add_argument('--null-observations-only', action='store_true',
                       help='Only download scenes with 0 plumes detected')
    parser.add_argument('--with-plumes-only', action='store_true',
                       help='Only download scenes with 1+ plumes detected')
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

    if args.null_observations_only and args.with_plumes_only:
        parser.error("Cannot use both --null-observations-only and --with-plumes-only")

    download_scenes(
        country=args.country,
        bbox=args.bbox,
        instrument=args.instrument,
        not_cloudy=args.not_cloudy,
        cloud_cover_max=args.cloud_cover_max,
        null_observations_only=args.null_observations_only,
        with_plumes_only=args.with_plumes_only,
        start_date=args.start_date,
        end_date=args.end_date,
        max_results=args.max_results,
        output_name=args.output_name
    )


if __name__ == "__main__":
    main()
