"""
Generate Monthly Pyxis Field Data for Argentina

This script creates monthly field-level data suitable for Pyxis database ingestion.
Combines data from multiple sources to produce comprehensive field profiles.

Input Files (translated):
    - daily_oil_production_english.csv
    - daily_gas_production_english.csv
    - field_shapes_depth_english.csv
    - field_production_by_formation_vintage_english.csv
    - gas_field_production_english.csv
    - oil_field_production_english.csv
    - well_production_{year}_english.csv (year-specific)

Output:
    - argentina_pyxis_fields_YYYY.csv (full year, all 12 months)
    - argentina_pyxis_fields_YYYY_Q1.csv (quarter 1-4)
    - argentina_pyxis_fields_YYYY_H1.csv (half-year)
    - argentina_pyxis_fields_YYYY_M01.csv (single month)
    - argentina_pyxis_fields_YYYY_M01-M03.csv (month range)

Usage:
    cd data_preparation/argentina/scripts

    # Full year (output: argentina_pyxis_fields_2021.csv)
    pipenv run python 05_generate_pyxis_monthly.py --year 2021 --months 1-12

    # Quarter 1 (output: argentina_pyxis_fields_2021_Q1.csv)
    pipenv run python 05_generate_pyxis_monthly.py --year 2021 --months 1-3

    # First half (output: argentina_pyxis_fields_2021_H1.csv)
    pipenv run python 05_generate_pyxis_monthly.py --year 2021 --months 1-6

    # Single month (output: argentina_pyxis_fields_2021_M06.csv)
    pipenv run python 05_generate_pyxis_monthly.py --year 2021 --months 6

    # Custom range (output: argentina_pyxis_fields_2021_M01-M08.csv)
    pipenv run python 05_generate_pyxis_monthly.py --year 2021 --months 1-8
"""

import sys
from pathlib import Path
import argparse
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')


# ============================================================================
# CONFIGURATION
# ============================================================================

# Unit conversion constants
M3_TO_BBL = 6.28981
MM3_TO_SCF = 35314666.7  # 10^6 * 35.3147
KM3_TO_SCF = 35314.7      # 1000 * 35.3147
M_TO_FT = 3.28084
GOR_THRESHOLD_GAS_FIELD = 100000  # scf/bbl


# ============================================================================
# DATA LOADING FUNCTIONS
# ============================================================================

def load_translated_data(translated_dir: Path, year: int):
    """Load all translated data files for the specified year."""
    print("Loading translated data files...")

    data = {}

    # Daily production
    data['daily_oil'] = pd.read_csv(translated_dir / 'daily_oil_production_english.csv')
    data['daily_gas'] = pd.read_csv(translated_dir / 'daily_gas_production_english.csv')
    print(f"  ✓ Daily production: {len(data['daily_oil']):,} oil + {len(data['daily_gas']):,} gas records")

    # Field shapes and depth
    data['field_shapes'] = pd.read_csv(translated_dir / 'field_shapes_depth_english.csv')
    print(f"  ✓ Field shapes: {len(data['field_shapes']):,} fields")

    # Formation and vintage data
    data['formation_vintage'] = pd.read_csv(translated_dir / 'field_production_by_formation_vintage_english.csv')
    print(f"  ✓ Formation/vintage: {len(data['formation_vintage']):,} records")

    # Gas field production
    data['gas_field'] = pd.read_csv(translated_dir / 'gas_field_production_english.csv')
    print(f"  ✓ Gas field production: {len(data['gas_field']):,} records")

    # Oil field production
    data['oil_field'] = pd.read_csv(translated_dir / 'oil_field_production_english.csv')
    print(f"  ✓ Oil field production: {len(data['oil_field']):,} records")

    # Well production (year-specific)
    well_file = translated_dir / f'well_production_{year}_english.csv'
    if well_file.exists():
        data['well_prod'] = pd.read_csv(well_file)
        print(f"  ✓ Well production ({year}): {len(data['well_prod']):,} records")
    else:
        data['well_prod'] = None
        print(f"  ⚠ Well production file not found for {year}")

    return data


# ============================================================================
# FUNCTIONAL UNIT DETERMINATION
# ============================================================================

def determine_functional_unit(oil_m3_day, gas_mm3_day):
    """
    Determine if field is oil or gas based on production rates.

    Args:
        oil_m3_day: Oil production in m3/day
        gas_mm3_day: Gas production in Mm3/day (million m3)

    Returns:
        'oil' or 'gas'
    """
    # Handle missing/zero values
    oil = oil_m3_day if pd.notna(oil_m3_day) else 0
    gas = gas_mm3_day if pd.notna(gas_mm3_day) else 0

    # Pure gas field
    if oil == 0 and gas > 0:
        return 'gas'

    # Pure oil field
    if gas == 0 and oil > 0:
        return 'oil'

    # Both present - calculate GOR
    if oil > 0 and gas > 0:
        gor_scf_bbl = (gas * MM3_TO_SCF) / (oil * M3_TO_BBL)
        if gor_scf_bbl > GOR_THRESHOLD_GAS_FIELD:
            return 'gas'
        else:
            return 'oil'

    # Neither present - default to oil
    return 'oil'


def calculate_field_functional_unit(daily_oil, daily_gas, gas_field, formation_vintage, year, months):
    """
    Calculate functional unit for each field using vote-based approach.
    Uses gas_field_production as primary fallback when daily_gas lacks data for target year.

    Args:
        daily_oil: Daily oil production DataFrame
        daily_gas: Daily gas production DataFrame
        gas_field: Gas field production DataFrame (primary fallback)
        formation_vintage: Formation/vintage production DataFrame (secondary fallback)
        year: Target year
        months: List of months

    Returns:
        DataFrame with field_id and functional_unit
    """
    print(f"\nCalculating functional units for {year}...")

    # Filter to target year and months
    oil_filtered = daily_oil[(daily_oil['year'] == year) & (daily_oil['month'].isin(months))]
    gas_filtered = daily_gas[(daily_gas['year'] == year) & (daily_gas['month'].isin(months))]

    # Check if gas data available for target year
    if len(gas_filtered) == 0:
        print(f"  ⚠️  Daily gas data not available for {year}, using gas_field_production")

        # Use gas_field_production as primary fallback
        gas_field_filtered = gas_field[
            (gas_field['year'] == year) &
            (gas_field['month'].isin(months))
        ]

        # Sum gas production concepts
        gas_production_concepts = [
            'high_pressure_gas_mm3',
            'medium_pressure_gas_mm3',
            'low_pressure_gas_mm3',
            'unconventional_gas_mm3'
        ]

        gas_prod_filtered = gas_field_filtered[gas_field_filtered['concept'].isin(gas_production_concepts)]

        gas_from_gf = gas_prod_filtered.groupby(['field_id', 'year', 'month']).agg({
            'quantity': 'sum',
            'field_name': 'first'
        }).reset_index()

        # Convert monthly total (Mm3) to daily rate (Mm3/day): / 30 days
        gas_from_gf['gas_production_avg_daily_mm3'] = gas_from_gf['quantity'] / 30

        gas_filtered = gas_from_gf[['field_id', 'field_name', 'year', 'month', 'gas_production_avg_daily_mm3']]
        print(f"  ✓ Using gas data from gas_field_production: {len(gas_from_gf):,} field-month records")

    # Merge on field_id and month
    merged = pd.merge(
        oil_filtered[['field_id', 'field_name', 'year', 'month', 'oil_production_avg_daily_m3']],
        gas_filtered[['field_id', 'year', 'month', 'gas_production_avg_daily_mm3']],
        on=['field_id', 'year', 'month'],
        how='outer'
    )

    # Calculate monthly functional unit
    merged['monthly_type'] = merged.apply(
        lambda row: determine_functional_unit(
            row['oil_production_avg_daily_m3'],
            row['gas_production_avg_daily_mm3']
        ),
        axis=1
    )

    # Vote-based: mode of monthly classifications per field
    func_unit = merged.groupby('field_id').agg({
        'monthly_type': lambda x: x.mode()[0] if len(x.mode()) > 0 else 'oil',
        'field_name': 'first'
    }).reset_index()

    func_unit.columns = ['field_id', 'functional_unit', 'field_name']

    # Summary
    type_counts = func_unit['functional_unit'].value_counts()
    print(f"  Functional unit distribution:")
    for ftype, count in type_counts.items():
        print(f"    {ftype}: {count} fields ({count/len(func_unit)*100:.1f}%)")

    return func_unit[['field_id', 'functional_unit']]


# ============================================================================
# METRIC CALCULATION FUNCTIONS
# ============================================================================

def calculate_api_from_density(density_ton_m3):
    """
    Calculate API gravity from density.

    Formula: API = 141.5 / SG - 131.5
    where SG (specific gravity) = density_ton_m3 / 1.0

    Args:
        density_ton_m3: Density in ton/m3

    Returns:
        API gravity in degrees
    """
    if pd.isna(density_ton_m3) or density_ton_m3 <= 0:
        return None

    api = (141.5 / density_ton_m3) - 131.5
    return api if api > 0 else None


def calculate_monthly_metrics(data, year, month):
    """
    Calculate all metrics for a specific year-month.

    Args:
        data: Dictionary of loaded DataFrames
        year: Target year
        month: Target month

    Returns:
        DataFrame with monthly field metrics
    """
    print(f"\nProcessing {year}-{month:02d}...")

    # Initialize output DataFrame
    output = []

    # Get unique fields from daily oil production
    daily_oil_month = data['daily_oil'][(data['daily_oil']['year'] == year) &
                                         (data['daily_oil']['month'] == month)]
    daily_gas_month = data['daily_gas'][(data['daily_gas']['year'] == year) &
                                         (data['daily_gas']['month'] == month)]

    # Get all fields from either source
    all_fields = set(daily_oil_month['field_id'].unique()) | set(daily_gas_month['field_id'].unique())

    # ========================================================================
    # PRE-AGGREGATE DATA (performance optimization)
    # ========================================================================
    # Filter formation_vintage once for this month and aggregate by field
    formation_month_all = data['formation_vintage'][
        (data['formation_vintage']['year'] == year) &
        (data['formation_vintage']['month'] == month)
    ]

    formation_agg = formation_month_all.groupby('field_id').agg({
        'oil_production_m3': 'sum',
        'gas_production_km3': 'sum',
        'water_production_m3': 'sum',
        'water_injection_m3': 'sum',
        'gas_injection_km3': 'sum',
        'co2_injection_m3': 'sum',
        'well_vintage_year': 'min',
        'field_name': 'first'
    }).to_dict('index')

    # Pre-aggregate gas production from gas_field_production
    gas_field_month = data['gas_field'][
        (data['gas_field']['year'] == year) &
        (data['gas_field']['month'] == month)
    ]

    # Sum gas production concepts (exclude reinjection, storage, heating value)
    gas_production_concepts = [
        'high_pressure_gas_mm3',
        'medium_pressure_gas_mm3',
        'low_pressure_gas_mm3',
        'unconventional_gas_mm3'
    ]

    gas_prod_filtered = gas_field_month[gas_field_month['concept'].isin(gas_production_concepts)]
    gas_agg = gas_prod_filtered.groupby('field_id')['quantity'].sum().to_dict()

    # Convert field_shapes to dictionary for O(1) lookup (drop duplicates)
    shapes_dict = data['field_shapes'].drop_duplicates('field_id').set_index('field_id').to_dict('index')

    print(f"  Fields with data: {len(all_fields)}")

    for field_id in all_fields:
        field_data = {}
        field_data['field_id'] = field_id
        field_data['year'] = year
        field_data['month'] = month
        field_data['time_index'] = f"{year}-{month:02d}"
        field_data['country'] = 'Argentina'

        # Field name (from daily oil preferably)
        oil_field = daily_oil_month[daily_oil_month['field_id'] == field_id]
        gas_field = daily_gas_month[daily_gas_month['field_id'] == field_id]
        field_data['field_name'] = oil_field['field_name'].iloc[0] if len(oil_field) > 0 else (
            gas_field['field_name'].iloc[0] if len(gas_field) > 0 else field_id
        )

        # Province and basin
        field_data['province'] = oil_field['province'].iloc[0] if len(oil_field) > 0 else (
            gas_field['province'].iloc[0] if len(gas_field) > 0 else None
        )
        field_data['basin'] = oil_field['basin'].iloc[0] if len(oil_field) > 0 else (
            gas_field['basin'].iloc[0] if len(gas_field) > 0 else None
        )

        # ====================================================================
        # DEPTH (from pre-aggregated shapes_dict, geometry excluded per user request)
        # ====================================================================
        if field_id in shapes_dict:
            shape = shapes_dict[field_id]
            depth_m = shape.get('depth_avg_m')
            field_data['depth'] = depth_m * M_TO_FT if pd.notna(depth_m) else None
        else:
            field_data['depth'] = None

        # ====================================================================
        # FORMATION/VINTAGE DATA (from pre-aggregated formation_agg)
        # ====================================================================
        formation_data = formation_agg.get(field_id, {})

        # ====================================================================
        # PRODUCTION RATES (from daily files with formation_vintage fallback)
        # ====================================================================
        # Oil production (bbl/day)
        if len(oil_field) > 0:
            oil_m3_day = oil_field['oil_production_avg_daily_m3'].iloc[0]
            field_data['oil_prod'] = oil_m3_day * M3_TO_BBL if pd.notna(oil_m3_day) else None
        else:
            field_data['oil_prod'] = None

        # Gas production (scf/day)
        if len(gas_field) > 0:
            gas_mm3_day = gas_field['gas_production_avg_daily_mm3'].iloc[0]
            field_data['gas_prod'] = gas_mm3_day * MM3_TO_SCF if pd.notna(gas_mm3_day) else None
        else:
            # Fallback 1: use gas_field_production (monthly total in Mm3)
            gas_mm3_month = gas_agg.get(field_id, 0)
            if gas_mm3_month > 0:
                # Convert to scf/day: Mm3 * MM3_TO_SCF / 30 days
                field_data['gas_prod'] = (gas_mm3_month * MM3_TO_SCF) / 30
            else:
                # Fallback 2: use formation_vintage data
                total_gas_km3 = formation_data.get('gas_production_km3', 0)
                if total_gas_km3 > 0:
                    # Convert to scf/day: km3 * KM3_TO_SCF / 30 days
                    field_data['gas_prod'] = (total_gas_km3 * KM3_TO_SCF) / 30
                else:
                    field_data['gas_prod'] = None

        # ====================================================================
        # GOR (scf/bbl)
        # ====================================================================
        if field_data['oil_prod'] and field_data['gas_prod'] and field_data['oil_prod'] > 0:
            field_data['gor'] = field_data['gas_prod'] / field_data['oil_prod']
        else:
            field_data['gor'] = None

        # ====================================================================
        # WOR, WIR, INJECTION FLAGS (from formation_vintage)
        # ====================================================================
        if formation_data:
            # Get pre-aggregated totals
            total_oil = formation_data.get('oil_production_m3', 0)
            total_water_prod = formation_data.get('water_production_m3', 0)
            total_water_inj = formation_data.get('water_injection_m3', 0)
            total_gas_inj_km3 = formation_data.get('gas_injection_km3', 0)

            # WOR (bbl_water/bbl_oil)
            if total_oil > 0:
                field_data['wor'] = total_water_prod / total_oil
            else:
                field_data['wor'] = None

            # WIR (bbl_water/bbl_oil)
            if total_oil > 0:
                field_data['wir'] = total_water_inj / total_oil
            else:
                field_data['wir'] = None

            # GLIR (scf/bbl_liquid) - using gas injection
            if total_oil > 0 and total_gas_inj_km3 > 0:
                gas_inj_scf = total_gas_inj_km3 * KM3_TO_SCF
                oil_bbl = total_oil * M3_TO_BBL
                water_bbl = total_water_prod * M3_TO_BBL
                liquid_bbl = oil_bbl + water_bbl
                field_data['glir'] = gas_inj_scf / liquid_bbl if liquid_bbl > 0 else None
            else:
                field_data['glir'] = None

            # Injection flags
            field_data['water_flooding'] = total_water_inj > 0
            field_data['gas_flooding'] = total_gas_inj_km3 > 0

            # Well vintage year (earliest from aggregation)
            field_data['well_vintage_year'] = formation_data.get('well_vintage_year')
        else:
            field_data['wor'] = None
            field_data['wir'] = None
            field_data['glir'] = None
            field_data['water_flooding'] = False
            field_data['gas_flooding'] = False
            field_data['well_vintage_year'] = None

        # ====================================================================
        # WELL COUNTS (from well_production_2025 if available)
        # ====================================================================
        if data['well_prod'] is not None:
            well_month = data['well_prod'][
                (data['well_prod']['field_id'] == field_id) &
                (data['well_prod']['year'] == year) &
                (data['well_prod']['month'] == month)
            ]

            if len(well_month) > 0:
                # Producing wells (active status)
                active_wells = well_month[well_month['well_status'].str.contains('active|producing', case=False, na=False)]
                field_data['num_prod_wells'] = len(active_wells['well_id'].unique())

                # Water injection wells
                inj_wells = well_month[well_month['water_injection_m3'] > 0]
                field_data['num_water_inj_wells'] = len(inj_wells['well_id'].unique())

                # Extraction methods (pivot to boolean flags)
                extraction_methods = well_month['extraction_method'].value_counts()
                field_data['downhole_pump'] = 'mechanical_pump' in extraction_methods.index
                field_data['gas_lifting'] = 'gas_lift' in extraction_methods.index
            else:
                field_data['num_prod_wells'] = None
                field_data['num_water_inj_wells'] = None
                field_data['downhole_pump'] = None
                field_data['gas_lifting'] = None
        else:
            field_data['num_prod_wells'] = None
            field_data['num_water_inj_wells'] = None
            field_data['downhole_pump'] = None
            field_data['gas_lifting'] = None

        # ====================================================================
        # GAS REINJECTION (from gas_field_production)
        # ====================================================================
        gas_field_month = data['gas_field'][
            (data['gas_field']['field_id'] == field_id) &
            (data['gas_field']['year'] == year) &
            (data['gas_field']['month'] == month)
        ]

        if len(gas_field_month) > 0:
            # Pivot to get gas reinjection
            gas_reinj = gas_field_month[gas_field_month['concept'] == 'gas_reinjection_formation_mm3']['quantity'].sum()
            total_gas_prod = gas_field_month[
                gas_field_month['concept'].isin(['high_pressure_gas_mm3', 'medium_pressure_gas_mm3', 'low_pressure_gas_mm3'])
            ]['quantity'].sum()

            field_data['natural_gas_reinjection'] = gas_reinj > 0

            if total_gas_prod > 0 and gas_reinj > 0:
                field_data['fraction_remaining_gas_inj'] = gas_reinj / total_gas_prod
            else:
                field_data['fraction_remaining_gas_inj'] = None

            # Offshore flag
            location = gas_field_month['location'].iloc[0] if 'location' in gas_field_month.columns else None
            field_data['offshore'] = location == 'Offshore' if location else False
        else:
            field_data['natural_gas_reinjection'] = None
            field_data['fraction_remaining_gas_inj'] = None
            field_data['offshore'] = None

        # ====================================================================
        # API GRAVITY (from oil_field_production)
        # ====================================================================
        oil_field_month = data['oil_field'][
            (data['oil_field']['field_id'] == field_id) &
            (data['oil_field']['year'] == year) &
            (data['oil_field']['month'] == month)
        ]

        if len(oil_field_month) > 0:
            # Get oil density
            density_data = oil_field_month[oil_field_month['concept'] == 'oil_density_avg_ton_per_m3']
            if len(density_data) > 0:
                avg_density = density_data['quantity'].mean()
                field_data['api'] = calculate_api_from_density(avg_density)
            else:
                field_data['api'] = None
        else:
            field_data['api'] = None

        output.append(field_data)

    output_df = pd.DataFrame(output)
    print(f"  Generated {len(output_df)} field records")

    return output_df


# ============================================================================
# MAIN PIPELINE
# ============================================================================

def main():
    """Main pipeline execution."""
    parser = argparse.ArgumentParser(description='Generate monthly Pyxis field data for Argentina')
    parser.add_argument('--year', type=int, default=2025, help='Target year (default: 2025)')
    parser.add_argument('--months', type=str, default='1-8', help='Month range, e.g., "1-8" or "1,3,5" (default: 1-8)')
    args = parser.parse_args()

    # Parse months
    if '-' in args.months:
        start, end = map(int, args.months.split('-'))
        months = list(range(start, end + 1))
    else:
        months = [int(m) for m in args.months.split(',')]

    print("="*70)
    print("ARGENTINA → PYXIS MONTHLY FIELD DATA GENERATION")
    print("="*70)
    print(f"Target period: {args.year}, months: {months}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Paths
    base_dir = Path(__file__).parent.parent
    translated_dir = base_dir / 'raw' / 'translated'
    output_dir = base_dir / 'output'
    output_dir.mkdir(exist_ok=True)

    # Load data
    data = load_translated_data(translated_dir, args.year)

    # Calculate functional units (vote-based across all months)
    func_units = calculate_field_functional_unit(
        data['daily_oil'],
        data['daily_gas'],
        data['gas_field'],
        data['formation_vintage'],
        args.year,
        months
    )

    # Process each month
    all_monthly_data = []
    for month in months:
        monthly_df = calculate_monthly_metrics(data, args.year, month)
        all_monthly_data.append(monthly_df)

    # Combine all months
    combined_df = pd.concat(all_monthly_data, ignore_index=True)

    # Merge functional units
    combined_df = pd.merge(combined_df, func_units, on='field_id', how='left')

    # Reorder columns (geometry excluded per user request)
    column_order = [
        'field_id', 'field_name', 'country', 'year', 'month', 'time_index',
        'depth', 'well_vintage_year', 'functional_unit',
        'oil_prod', 'gas_prod', 'gor', 'wor', 'wir', 'glir',
        'num_prod_wells', 'num_water_inj_wells',
        'water_flooding', 'gas_flooding', 'natural_gas_reinjection',
        'downhole_pump', 'gas_lifting', 'offshore',
        'fraction_remaining_gas_inj', 'api', 'province', 'basin'
    ]

    combined_df = combined_df[column_order]

    # Save output with month range in filename
    if len(months) == 12 and months == list(range(1, 13)):
        # Full year
        month_suffix = ""
    elif len(months) == 1:
        # Single month
        month_suffix = f"_M{months[0]:02d}"
    elif months == list(range(min(months), max(months) + 1)):
        # Consecutive months (e.g., 1-3 for Q1, 1-6 for H1)
        if len(months) == 3:
            quarter = (min(months) - 1) // 3 + 1
            month_suffix = f"_Q{quarter}"
        elif len(months) == 6 and min(months) == 1:
            month_suffix = "_H1"
        elif len(months) == 6 and min(months) == 7:
            month_suffix = "_H2"
        else:
            month_suffix = f"_M{min(months):02d}-M{max(months):02d}"
    else:
        # Non-consecutive months
        month_suffix = "_M" + "-".join([f"{m:02d}" for m in sorted(months)])

    output_file = output_dir / f'argentina_pyxis_fields_{args.year}{month_suffix}.csv'
    combined_df.to_csv(output_file, index=False)

    # Summary
    print(f"\n{'='*70}")
    print(f"✅ PROCESSING COMPLETE")
    print(f"{'='*70}")
    print(f"Output file: {output_file}")
    print(f"Total records: {len(combined_df):,}")
    print(f"Unique fields: {combined_df['field_id'].nunique():,}")
    print(f"Months covered: {combined_df['month'].nunique()}")
    print(f"\nFunctional unit distribution:")
    for ftype, count in combined_df['functional_unit'].value_counts().items():
        print(f"  {ftype}: {count:,} records")

    print(f"\nData completeness:")
    total = len(combined_df)
    for col in ['oil_prod', 'gas_prod', 'gor', 'wor', 'api', 'num_prod_wells']:
        non_null = combined_df[col].notna().sum()
        print(f"  {col}: {non_null:,}/{total:,} ({non_null/total*100:.1f}%)")

    print(f"\nFinished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
