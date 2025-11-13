"""
Download Raw Data from Argentina Energy Data Portal

This script downloads all required raw data files from the Argentina Ministry of Energy
CKAN data portal (datos.energia.gob.ar) using their API.

Downloads 12 CSV files:
    1. Oil field production (monthly by recovery type)
    2. Gas field production (monthly by pressure category)
    3. Well production (monthly by extraction method)
    4. Well characteristics (static metadata)
    5. Fracture completion (hydraulic fracturing details)
    6. Field shapes & depth (GeoJSON boundaries)
    7. Daily oil production (average daily rates)
    8. Daily gas production (average daily rates)
    9. Field production by formation/vintage (includes injection)
    10. Plant gas processing (includes flaring)
    11. Historical gas wells (pre-2009 well counts)
    12. Historical oil wells (pre-2009 well counts)

Usage:
    cd data_preparation/argentina/scripts
    pipenv run python 00_download_raw_data.py

    # Or download specific datasets:
    pipenv run python 00_download_raw_data.py --datasets oil_field gas_field
"""

import sys
from pathlib import Path
import argparse
import json
from datetime import datetime
import time

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import requests
import pandas as pd
import warnings
warnings.filterwarnings('ignore')


# ============================================================================
# CONFIGURATION
# ============================================================================

# CKAN API base URL
CKAN_BASE_URL = "http://datos.energia.gob.ar/api/3/action"

# Dataset definitions with resource IDs from datos.energia.gob.ar
# These IDs can be found by exploring the datasets on the portal
DATASETS = {
    # Core production data
    "well_production": {
        "name": "Producción de petróleo y gas por pozo (Capítulo IV)",
        "package_id": "produccion-de-petroleo-y-gas-por-pozo",
        "resource_id": "cb5c0f04-7835-45cd-b982-3e25ca7d7751",
        "direct_url": "http://datos.energia.gob.ar/dataset/c846e79c-026c-4040-897f-1ad3543b407c/resource/cb5c0f04-7835-45cd-b982-3e25ca7d7751/download/capitulo-iv-pozos.csv",
        "output_file": "well_production_full.csv",
        "description": "Well production data - monthly by extraction method"
    },

    # Well production by year (2009-2025)
    "well_production_by_year": {
        "name": "Producción de petróleo y gas por pozo (por año)",
        "package_id": "produccion-de-petroleo-y-gas-por-pozo",
        "description": "Well production data by year (2009-2025)",
        "batch_download": True,  # Special flag for batch download
        "year_resources": {
            "2009": "48585038-055a-4437-bb1d-4fe36073f453",
            "2010": "364ca28e-d069-4bd6-8771-925f0db152a8",
            "2011": "4817272c-7365-4bdd-b02d-75b118218b10",
            "2012": "0dce0e75-1556-47ee-8615-1955fbd54ade",
            "2013": "bc7ac8fe-2cec-4dab-acdd-322ea1ccc887",
            "2014": "cd9813a7-1e19-4f60-a02a-7903dd81aff7",
            "2015": "e375aa35-fd8d-41d6-aa0c-e6879ca567a1",
            "2016": "d8539ae8-0a71-4339-a16c-139b21bd2cd0",
            "2017": "df4857e1-7c3f-4980-b5b5-184fe78bfcf0",
            "2018": "333fd72a-9b83-4bc1-bc94-0f5940b52331",
            "2019": "8bc0d61c-0408-43d4-a7bc-7178fcb5d37e",
            "2020": "c4a4a6a0-e75a-4e12-ae5c-54d53a70348c",
            "2021": "465be754-a372-4c31-b855-81dc5fe3309f",
            "2022": "876b3746-85e2-4039-adeb-b1354436159f",
            "2023": "231c39b3-e81e-4398-af8d-b115807f2c25",
            "2024": "43a09dce-1742-44d0-bc13-f193deaab563",
            "2025": "d774b5d7-0756-48fe-88f2-8729b57b22da"
        }
    },

    # Additional datasets - these need to be mapped to actual resource IDs
    # You'll need to explore datos.energia.gob.ar to find the correct IDs
    "oil_field": {
        "name": "Producción de petróleo por yacimiento",
        "package_id": "produccion-de-petroleo-y-gas-tablas-dinamicas",
        "resource_id": "745facdc-73dc-46d8-83d5-d027bdaa3210",
        "direct_url": "http://datos.energia.gob.ar/dataset/590d1284-fd6d-4686-afd8-b3da5d90a6e9/resource/745facdc-73dc-46d8-83d5-d027bdaa3210/download/produccin-de-petrleo-por-yacimiento.csv",
        "output_file": "produccin-de-petrleo-por-yacimiento.csv",  # Original Spanish filename from portal
        "description": "Oil field production - monthly by recovery type",
        "supports_year_filter": True  # Can filter by year column
    },

    "gas_field": {
        "name": "Producción de gas por yacimiento",
        "package_id": "produccion-de-petroleo-y-gas-tablas-dinamicas",
        "resource_id": "ce479c85-2e8b-441e-9c68-9681597b3694",
        "direct_url": "http://datos.energia.gob.ar/dataset/590d1284-fd6d-4686-afd8-b3da5d90a6e9/resource/ce479c85-2e8b-441e-9c68-9681597b3694/download/produccin-de-gas-por-yacimiento.csv",
        "output_file": "produccin-de-gas-por-yacimiento.csv",  # Original Spanish filename from portal
        "description": "Gas field production - monthly by pressure category",
        "supports_year_filter": True  # Can filter by year column
    },

    "well_characteristics": {
        "name": "Características de pozos",
        "package_id": None,
        "resource_id": None,
        "direct_url": None,
        "output_file": "well_characteristics.csv",
        "description": "Well characteristics - static metadata"
    },

    "fracture_completion": {
        "name": "Completamiento de pozos - fractura hidráulica",
        "package_id": None,
        "resource_id": None,
        "direct_url": None,
        "output_file": "fracture_completion.csv",
        "description": "Fracture completion - hydraulic fracturing details"
    },

    "field_shapes": {
        "name": "Áreas de yacimientos",
        "package_id": None,
        "resource_id": None,
        "direct_url": None,
        "output_file": "field_shapes_depth.csv",
        "description": "Field shapes & depth - GeoJSON boundaries"
    },

    "daily_oil": {
        "name": "Producción diaria de petróleo",
        "package_id": None,
        "resource_id": None,
        "direct_url": None,
        "output_file": "daily_oil_production.csv",
        "description": "Daily oil production - average daily rates"
    },

    "daily_gas": {
        "name": "Producción diaria de gas",
        "package_id": None,
        "resource_id": None,
        "direct_url": None,
        "output_file": "daily_gas_production.csv",
        "description": "Daily gas production - average daily rates"
    },

    "formation_vintage": {
        "name": "Producción por formación y añada",
        "package_id": None,
        "resource_id": None,
        "direct_url": None,
        "output_file": "field_production_by_formation_vintage.csv",
        "description": "Field production by formation/vintage - includes injection"
    },

    "plant_gas": {
        "name": "Procesamiento de gas en plantas",
        "package_id": None,
        "resource_id": None,
        "direct_url": None,
        "output_file": "plant_gas_processing.csv",
        "description": "Plant gas processing - includes flaring"
    },

    "historical_gas_wells": {
        "name": "Pozos de gas históricos",
        "package_id": None,
        "resource_id": None,
        "direct_url": None,
        "output_file": "historical_gas_wells.csv",
        "description": "Historical gas wells - pre-2009 well counts"
    },

    "historical_oil_wells": {
        "name": "Pozos de petróleo históricos",
        "package_id": None,
        "resource_id": None,
        "direct_url": None,
        "output_file": "historical_oil_wells.csv",
        "description": "Historical oil wells - pre-2009 well counts"
    }
}


# ============================================================================
# API HELPER FUNCTIONS
# ============================================================================

def ckan_api_call(action, params=None, timeout=30):
    """
    Make a CKAN API call.

    Args:
        action: CKAN API action (e.g., 'package_search', 'resource_show')
        params: Dictionary of parameters
        timeout: Request timeout in seconds

    Returns:
        API response as dictionary
    """
    url = f"{CKAN_BASE_URL}/{action}"

    try:
        response = requests.get(url, params=params, timeout=timeout, verify=False)
        response.raise_for_status()

        data = response.json()

        if not data.get('success', False):
            print(f"  ✗ API call failed: {data.get('error', 'Unknown error')}")
            return None

        return data.get('result')

    except requests.exceptions.Timeout:
        print(f"  ✗ Request timeout after {timeout}s")
        return None
    except requests.exceptions.RequestException as e:
        print(f"  ✗ Request error: {e}")
        return None
    except json.JSONDecodeError:
        print(f"  ✗ Invalid JSON response")
        return None


def search_datasets(query, max_results=10):
    """
    Search for datasets matching a query.

    Args:
        query: Search query string
        max_results: Maximum number of results to return

    Returns:
        List of matching dataset dictionaries
    """
    print(f"\nSearching for datasets: '{query}'")

    params = {
        'q': query,
        'rows': max_results
    }

    result = ckan_api_call('package_search', params)

    if result and 'results' in result:
        datasets = result['results']
        print(f"  ✓ Found {len(datasets)} datasets")
        return datasets

    return []


def get_package_resources(package_id):
    """
    Get all resources for a package/dataset.

    Args:
        package_id: Package identifier

    Returns:
        List of resource dictionaries
    """
    print(f"\nGetting resources for package: {package_id}")

    params = {'id': package_id}
    result = ckan_api_call('package_show', params)

    if result and 'resources' in result:
        resources = result['resources']
        print(f"  ✓ Found {len(resources)} resources")
        return resources

    return []


def get_resource_info(resource_id):
    """
    Get metadata for a specific resource.

    Args:
        resource_id: Resource identifier

    Returns:
        Resource dictionary
    """
    params = {'id': resource_id}
    result = ckan_api_call('resource_show', params)

    if result:
        print(f"  ✓ Resource: {result.get('name', 'Unknown')}")
        print(f"    Format: {result.get('format', 'Unknown')}")
        print(f"    URL: {result.get('url', 'None')}")
        if 'size' in result and result['size']:
            print(f"    Size: {result['size'] / 1024 / 1024:.1f} MB")

    return result


# ============================================================================
# DOWNLOAD FUNCTIONS
# ============================================================================

def download_file(url, output_path, chunk_size=8192):
    """
    Download a file with progress indication.

    Args:
        url: Download URL
        output_path: Path to save file
        chunk_size: Download chunk size in bytes

    Returns:
        True if successful, False otherwise
    """
    try:
        response = requests.get(url, stream=True, timeout=300, verify=False)
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0

        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)

                    if total_size > 0:
                        progress = (downloaded / total_size) * 100
                        print(f"\r  Downloading... {progress:.1f}% ({downloaded / 1024 / 1024:.1f} MB)", end='')

        print()  # New line after progress
        return True

    except requests.exceptions.RequestException as e:
        print(f"\n  ✗ Download failed: {e}")
        return False


def filter_csv_by_year(input_path, output_path, years, year_column='anio'):
    """
    Filter a CSV file by year(s) to reduce file size.

    Args:
        input_path: Path to input CSV file
        output_path: Path to save filtered CSV file
        years: List of years to keep (e.g., [2024, 2025])
        year_column: Name of year column (default: 'anio')

    Returns:
        True if successful, False otherwise
    """
    try:
        import pandas as pd

        print(f"  Filtering by years: {years}")
        print(f"  Reading full file...")

        # Read CSV
        df = pd.read_csv(input_path, low_memory=False)
        original_rows = len(df)
        original_size = input_path.stat().st_size / 1024 / 1024

        print(f"    Original: {original_rows:,} rows ({original_size:.1f} MB)")

        # Filter by year
        if year_column in df.columns:
            df_filtered = df[df[year_column].isin(years)]
            filtered_rows = len(df_filtered)

            # Save filtered data
            df_filtered.to_csv(output_path, index=False)
            filtered_size = output_path.stat().st_size / 1024 / 1024

            print(f"    Filtered: {filtered_rows:,} rows ({filtered_size:.1f} MB)")
            print(f"    Reduction: {(1 - filtered_rows/original_rows)*100:.1f}% fewer rows, {(1 - filtered_size/original_size)*100:.1f}% smaller")

            return True
        else:
            print(f"  ✗ Year column '{year_column}' not found in CSV")
            print(f"    Available columns: {', '.join(df.columns[:10])}...")
            return False

    except Exception as e:
        print(f"  ✗ Filter failed: {e}")
        return False


def download_dataset(dataset_key, dataset_info, output_dir, force=False, filter_years=None):
    """
    Download a dataset using direct URL or resource ID.

    Args:
        dataset_key: Dataset key from DATASETS
        dataset_info: Dataset configuration dictionary
        output_dir: Output directory path
        force: Force re-download even if file exists
        filter_years: List of years to filter (e.g., [2024, 2025]). Only works if dataset supports it.

    Returns:
        True if successful, False otherwise
    """
    print(f"\n{'='*70}")
    print(f"Dataset: {dataset_info['name']}")
    print(f"{'='*70}")

    # Determine if we need to download to temp file for filtering
    supports_filter = dataset_info.get('supports_year_filter', False)
    use_temp_file = filter_years and supports_filter

    # Modify output filename to include year range if filtering
    base_output_path = output_dir / dataset_info['output_file']
    if use_temp_file:
        # Add year range to filename: file.csv -> file_2024-2025.csv
        year_str = f"{min(filter_years)}-{max(filter_years)}" if len(filter_years) > 1 else str(filter_years[0])
        output_path = output_dir / f"{base_output_path.stem}_{year_str}{base_output_path.suffix}"
        temp_path = output_dir / f"{base_output_path.stem}_temp{base_output_path.suffix}"
        download_path = temp_path
        print(f"  Year filter enabled: {filter_years}")
        print(f"  Output file: {output_path.name}")
    else:
        output_path = base_output_path
        download_path = output_path

    # Check if file already exists
    if output_path.exists() and not force:
        file_size = output_path.stat().st_size / 1024 / 1024
        print(f"  ✓ File already exists: {output_path.name} ({file_size:.1f} MB)")
        print(f"    Use --force to re-download")
        return True

    # Try direct URL first
    if dataset_info.get('direct_url'):
        print(f"  Using direct URL: {dataset_info['direct_url']}")
        success = download_file(dataset_info['direct_url'], download_path)

        if success:
            # Apply year filter if needed
            if use_temp_file:
                filter_success = filter_csv_by_year(temp_path, output_path, filter_years)

                # Delete temp file if it exists
                if temp_path.exists():
                    temp_path.unlink()

                if filter_success:
                    file_size = output_path.stat().st_size / 1024 / 1024
                    print(f"  ✓ Downloaded and filtered: {output_path.name} ({file_size:.1f} MB)")
                    return True
                else:
                    return False
            else:
                file_size = output_path.stat().st_size / 1024 / 1024
                print(f"  ✓ Downloaded: {output_path.name} ({file_size:.1f} MB)")
                return True

    # Try using resource_id via API
    if dataset_info.get('resource_id'):
        print(f"  Using resource ID: {dataset_info['resource_id']}")
        resource = get_resource_info(dataset_info['resource_id'])

        if resource and resource.get('url'):
            success = download_file(resource['url'], download_path)

            if success:
                # Apply year filter if needed
                if use_temp_file:
                    filter_success = filter_csv_by_year(temp_path, output_path, filter_years)

                    # Delete temp file if it exists
                    if temp_path.exists():
                        temp_path.unlink()

                    if filter_success:
                        file_size = output_path.stat().st_size / 1024 / 1024
                        print(f"  ✓ Downloaded and filtered: {output_path.name} ({file_size:.1f} MB)")
                        return True
                    else:
                        return False
                else:
                    file_size = output_path.stat().st_size / 1024 / 1024
                    print(f"  ✓ Downloaded: {output_path.name} ({file_size:.1f} MB)")
                    return True

    # Could not download
    print(f"  ✗ Unable to download dataset")
    print(f"    Manual download required:")
    print(f"    1. Visit: https://datos.energia.gob.ar")
    print(f"    2. Search for: {dataset_info['name']}")
    print(f"    3. Download and save as: {output_path.name}")

    return False


def download_well_production_by_year(dataset_info, output_dir, force=False, year_range=None):
    """
    Download well production data for multiple years.

    Args:
        dataset_info: Dataset configuration dictionary with year_resources
        output_dir: Output directory path
        force: Force re-download even if file exists
        year_range: Optional list of specific years to download (e.g., [2020, 2021, 2022])
                   If None, downloads all available years

    Returns:
        Number of successfully downloaded years
    """
    print(f"\n{'='*70}")
    print(f"Dataset: {dataset_info['name']}")
    print(f"{'='*70}")

    year_resources = dataset_info.get('year_resources', {})

    # Determine which years to download
    if year_range:
        years_to_download = {str(y): rid for y, rid in year_resources.items() if int(y) in year_range}
    else:
        years_to_download = year_resources

    print(f"  Years to download: {len(years_to_download)}")
    print(f"  Years: {', '.join(sorted(years_to_download.keys()))}\n")

    success_count = 0
    failed_years = []

    for year in sorted(years_to_download.keys()):
        resource_id = years_to_download[year]
        output_file = output_dir / f"produccin-de-pozos-de-gas-y-petrleo-{year}.csv"

        print(f"\n  [{year}] Downloading...")

        # Check if file already exists
        if output_file.exists() and not force:
            file_size = output_file.stat().st_size / 1024 / 1024
            print(f"    ✓ Already exists: {output_file.name} ({file_size:.1f} MB)")
            print(f"      Use --force to re-download")
            success_count += 1
            continue

        # Get resource info via API
        resource = get_resource_info(resource_id)

        if resource and resource.get('url'):
            success = download_file(resource['url'], output_file)

            if success:
                file_size = output_file.stat().st_size / 1024 / 1024
                print(f"    ✓ Downloaded: {output_file.name} ({file_size:.1f} MB)")
                success_count += 1
            else:
                failed_years.append(year)
                print(f"    ✗ Download failed for {year}")
        else:
            failed_years.append(year)
            print(f"    ✗ Could not get resource info for {year}")

        time.sleep(1)  # Rate limiting

    # Summary
    print(f"\n  {'='*66}")
    print(f"  Batch Download Summary for Well Production")
    print(f"  {'='*66}")
    print(f"  Total years: {len(years_to_download)}")
    print(f"  Successfully downloaded: {success_count}")
    print(f"  Failed: {len(failed_years)}")
    if failed_years:
        print(f"  Failed years: {', '.join(failed_years)}")

    return success_count


def discover_datasets():
    """
    Interactively discover dataset IDs by searching the portal.
    """
    print("="*70)
    print("DATASET DISCOVERY MODE")
    print("="*70)
    print("\nThis will help you find resource IDs for datasets on datos.energia.gob.ar\n")

    search_queries = [
        "producción petróleo yacimiento",
        "producción gas yacimiento",
        "características pozos",
        "completamiento fractura hidráulica",
        "áreas yacimientos",
        "producción diaria petróleo",
        "producción diaria gas",
        "producción formación añada",
        "procesamiento gas plantas",
        "pozos históricos"
    ]

    for query in search_queries:
        datasets = search_datasets(query, max_results=3)

        if datasets:
            for i, dataset in enumerate(datasets, 1):
                print(f"\n  [{i}] {dataset.get('title', 'Unknown')}")
                print(f"      ID: {dataset.get('id', 'None')}")
                print(f"      Name: {dataset.get('name', 'None')}")

                if 'resources' in dataset:
                    print(f"      Resources: {len(dataset['resources'])}")
                    for res in dataset['resources'][:2]:  # Show first 2 resources
                        print(f"        - {res.get('name', 'Unknown')} ({res.get('format', 'Unknown')})")
                        print(f"          Resource ID: {res.get('id', 'None')}")

        time.sleep(1)  # Rate limiting


# ============================================================================
# MAIN PIPELINE
# ============================================================================

def main():
    """Main download pipeline."""
    parser = argparse.ArgumentParser(description='Download Argentina energy data from CKAN portal')
    parser.add_argument('--datasets', nargs='+', help='Specific datasets to download (keys from DATASETS dict)')
    parser.add_argument('--force', action='store_true', help='Force re-download even if files exist')
    parser.add_argument('--discover', action='store_true', help='Discover dataset IDs via search')
    parser.add_argument('--output-dir', type=str, help='Output directory (default: ../raw)')
    parser.add_argument('--years', type=str, help='Filter by years: "2024,2025" or "2024-2025" (only for supported datasets)')
    args = parser.parse_args()

    # Parse years parameter
    filter_years = None
    if args.years:
        if '-' in args.years and ',' not in args.years:
            # Range format: "2024-2025"
            start, end = map(int, args.years.split('-'))
            filter_years = list(range(start, end + 1))
        else:
            # Comma format: "2024,2025"
            filter_years = [int(y.strip()) for y in args.years.split(',')]

    print("="*70)
    print("ARGENTINA ENERGY DATA - DOWNLOAD SCRIPT")
    print("="*70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Discovery mode
    if args.discover:
        discover_datasets()
        return

    # Setup output directory
    base_dir = Path(__file__).parent.parent
    output_dir = Path(args.output_dir) if args.output_dir else base_dir / 'raw'
    output_dir.mkdir(exist_ok=True, parents=True)

    print(f"Output directory: {output_dir}\n")

    # Disable SSL warnings (datos.energia.gob.ar has certificate issues)
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # Determine which datasets to download
    if args.datasets:
        datasets_to_download = {k: v for k, v in DATASETS.items() if k in args.datasets}
        if not datasets_to_download:
            print(f"✗ No valid datasets specified. Available: {', '.join(DATASETS.keys())}")
            return
    else:
        datasets_to_download = DATASETS

    print(f"Datasets to download: {len(datasets_to_download)}")
    if filter_years:
        print(f"Year filter: {filter_years}\n")
    else:
        print()

    # Download each dataset
    success_count = 0
    failed_datasets = []

    for key, info in datasets_to_download.items():
        # Check if this is a batch download (well production by year)
        if info.get('batch_download', False):
            # Use filter_years as year_range for batch download
            year_range = filter_years if filter_years else None
            num_success = download_well_production_by_year(info, output_dir, args.force, year_range)

            if num_success > 0:
                success_count += 1  # Count as one successful "dataset" even if multiple years
            else:
                failed_datasets.append(key)
        else:
            # Normal single-file download
            success = download_dataset(key, info, output_dir, args.force, filter_years)

            if success:
                success_count += 1
            else:
                failed_datasets.append(key)

        time.sleep(1)  # Rate limiting between downloads

    # Summary
    print(f"\n{'='*70}")
    print(f"DOWNLOAD SUMMARY")
    print(f"{'='*70}")
    print(f"Total datasets: {len(datasets_to_download)}")
    print(f"Successfully downloaded: {success_count}")
    print(f"Failed: {len(failed_datasets)}")

    if failed_datasets:
        print(f"\nFailed datasets:")
        for key in failed_datasets:
            print(f"  - {key}: {DATASETS[key]['name']}")
        print(f"\nTo discover resource IDs for failed datasets, run:")
        print(f"  pipenv run python 00_download_raw_data.py --discover")

    print(f"\nFinished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
