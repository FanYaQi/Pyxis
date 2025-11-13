"""
Generate Combined Fracture and Well Characteristics Data

This script combines fracture completion data with well characteristics for
GHGfrack emissions calculations. It joins fracture_completion_data with
well_characteristics on well_id to create a comprehensive fracture dataset.

Input Files (translated):
    - fracture_completion_data_english.csv
    - well_characteristics_english.csv

Output:
    - argentina_fracture_well_combined.csv

Usage:
    cd data_preparation/argentina/scripts
    pipenv run python 06_generate_fracture_well_data.py
"""

import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
import warnings
warnings.filterwarnings('ignore')


# ============================================================================
# CONFIGURATION
# ============================================================================

# Unit conversion constants
M3_TO_BBL = 6.28981
M3_TO_GAL = 264.172
M_TO_FT = 3.28084
KG_TO_LB = 2.20462
TONS_TO_LB = 2204.62


# ============================================================================
# DATA LOADING
# ============================================================================

def load_data(translated_dir: Path):
    """Load fracture and well characteristics data."""
    print("Loading data files...")

    # Fracture completion data
    fracture = pd.read_csv(translated_dir / 'fracture_completion_data_english.csv')
    print(f"  ✓ Fracture data: {len(fracture):,} records")

    # Well characteristics
    wells = pd.read_csv(translated_dir / 'well_characteristics_english.csv')
    print(f"  ✓ Well characteristics: {len(wells):,} records")

    return fracture, wells


# ============================================================================
# DATA COMBINATION
# ============================================================================

def combine_fracture_well_data(fracture, wells):
    """
    Combine fracture completion data with well characteristics.

    Args:
        fracture: Fracture completion DataFrame
        wells: Well characteristics DataFrame

    Returns:
        Combined DataFrame with GHGfrack-relevant columns
    """
    print("\nCombining fracture and well data...")

    # Select relevant columns from wells
    well_cols = [
        'well_id',
        'field_code',
        'surface_elevation_m',
        'total_depth_m',
        'well_classification',
        'well_subclassification',
        'resource_type',
        'well_type'
    ]

    wells_subset = wells[well_cols].copy()

    # Join fracture with well characteristics on well_id
    combined = pd.merge(
        fracture,
        wells_subset,
        on='well_id',
        how='left',
        suffixes=('_frac', '_well')
    )

    print(f"  ✓ Combined records: {len(combined):,}")
    print(f"  ✓ Matched wells: {combined['total_depth_m'].notna().sum():,} ({combined['total_depth_m'].notna().mean()*100:.1f}%)")

    # Add field_id from field_code if available
    combined['field_id'] = combined['field_code'].fillna(combined['field_name'])

    # Convert units for GHGfrack
    print("\nConverting units for GHGfrack...")

    # Depth in feet
    combined['total_depth_ft'] = combined['total_depth_m'] * M_TO_FT
    combined['surface_elevation_ft'] = combined['surface_elevation_m'] * M_TO_FT
    combined['horizontal_lateral_length_ft'] = combined['horizontal_lateral_length_m'] * M_TO_FT

    # Proppant in pounds
    combined['proppant_domestic_lb'] = combined['proppant_domestic_tons'] * TONS_TO_LB
    combined['proppant_imported_lb'] = combined['proppant_imported_tons'] * TONS_TO_LB
    combined['proppant_total_lb'] = combined['proppant_domestic_lb'] + combined['proppant_imported_lb']

    # Fluid in gallons
    combined['frac_fluid_water_gal'] = combined['frac_fluid_water_m3'] * M3_TO_GAL
    combined['frac_fluid_co2_gal'] = combined['frac_fluid_co2_m3'] * M3_TO_GAL

    # Calculate intensity metrics
    combined['proppant_per_stage_lb'] = combined['proppant_total_lb'] / combined['fracture_stages_count']
    combined['fluid_per_stage_gal'] = combined['frac_fluid_water_gal'] / combined['fracture_stages_count']
    combined['proppant_per_lateral_ft_lb'] = combined['proppant_total_lb'] / combined['horizontal_lateral_length_ft']

    return combined


# ============================================================================
# OUTPUT PREPARATION
# ============================================================================

def prepare_output(combined):
    """Prepare final output with selected columns."""

    output_cols = [
        # Identifiers
        'fracture_job_id',
        'well_id',
        'well_name',
        'field_id',
        'field_name',
        'basin',
        'permit_area',

        # Formation & Reservoir
        'producing_formation',
        'reservoir_type',
        'reservoir_subtype',
        'resource_type',

        # Well Classification
        'well_classification',
        'well_subclassification',
        'well_type',

        # Completion Design
        'completion_type',
        'fracture_stages_count',
        'horizontal_lateral_length_m',
        'horizontal_lateral_length_ft',

        # Well Depth & Elevation
        'total_depth_m',
        'total_depth_ft',
        'surface_elevation_m',
        'surface_elevation_ft',

        # Proppant (original units - metric tons)
        'proppant_domestic_tons',
        'proppant_imported_tons',

        # Proppant (converted - pounds for GHGfrack)
        'proppant_domestic_lb',
        'proppant_imported_lb',
        'proppant_total_lb',

        # Frac Fluid (original - m3)
        'frac_fluid_water_m3',
        'frac_fluid_co2_m3',

        # Frac Fluid (converted - gallons for GHGfrack)
        'frac_fluid_water_gal',
        'frac_fluid_co2_gal',

        # Treatment Parameters
        'max_treatment_pressure_psi',
        'frac_equipment_total_horsepower',

        # Intensity Metrics (GHGfrack inputs)
        'proppant_per_stage_lb',
        'fluid_per_stage_gal',
        'proppant_per_lateral_ft_lb',

        # Timing
        'frac_start_date',
        'frac_end_date',
        'frac_start_year',
        'frac_start_month',

        # Metadata
        'reporting_company',
        'data_date'
    ]

    return combined[output_cols]


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main execution."""

    print("="*70)
    print("ARGENTINA FRACTURE + WELL CHARACTERISTICS COMBINATION")
    print("For GHGfrack Emissions Calculations")
    print("="*70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Paths
    base_dir = Path(__file__).parent.parent
    translated_dir = base_dir / 'raw' / 'translated'
    output_dir = base_dir / 'output'
    output_dir.mkdir(exist_ok=True)

    # Load data
    fracture, wells = load_data(translated_dir)

    # Combine data
    combined = combine_fracture_well_data(fracture, wells)

    # Prepare output
    output_df = prepare_output(combined)

    # Save output
    output_file = output_dir / 'argentina_fracture_well_combined.csv'
    output_df.to_csv(output_file, index=False)

    # Summary
    print(f"\n{'='*70}")
    print(f"✅ PROCESSING COMPLETE")
    print(f"{'='*70}")
    print(f"Output file: {output_file}")
    print(f"Total records: {len(output_df):,}")

    print(f"\nData completeness:")
    print(f"  Total depth: {output_df['total_depth_m'].notna().sum():,}/{len(output_df):,} ({output_df['total_depth_m'].notna().mean()*100:.1f}%)")
    print(f"  Well classification: {output_df['well_classification'].notna().sum():,}/{len(output_df):,} ({output_df['well_classification'].notna().mean()*100:.1f}%)")
    print(f"  Proppant data: {(output_df['proppant_total_lb']>0).sum():,}/{len(output_df):,} ({(output_df['proppant_total_lb']>0).mean()*100:.1f}%)")
    print(f"  Fluid data: {(output_df['frac_fluid_water_gal']>0).sum():,}/{len(output_df):,} ({(output_df['frac_fluid_water_gal']>0).mean()*100:.1f}%)")

    print(f"\nReservoir type distribution:")
    print(output_df['reservoir_type'].value_counts())

    print(f"\nCompletion type distribution:")
    print(output_df['completion_type'].value_counts())

    print(f"\nYear distribution:")
    print(output_df['frac_start_year'].value_counts().sort_index().tail(10))

    print(f"\nFinished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()


if __name__ == "__main__":
    main()
