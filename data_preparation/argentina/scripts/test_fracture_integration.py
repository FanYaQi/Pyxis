"""
Test Integration of Fracture/Completion Data with Field Metrics

This script tests merging fracture completion data with field production and depth
data, focusing on numerical metrics useful for analysis. Excludes descriptive text
fields like province, company names, etc.

Focus: Vaca Muerta shale fields with complete fracture data
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json

# Paths
base_dir = Path(__file__).parent.parent
translated_dir = base_dir / "raw" / "translated"

print("\n" + "="*80)
print("FRACTURE DATA INTEGRATION TEST")
print("="*80)

# ============================================================================
# 1. LOAD FRACTURE/COMPLETION DATA
# ============================================================================

print("\n1. Loading fracture/completion data...")
fracture_df = pd.read_csv(translated_dir / "fracture_completion_data_english.csv")

print(f"   Total fracture jobs: {len(fracture_df):,}")
print(f"   Columns: {len(fracture_df.columns)}")

# Filter for high-quality data (Vaca Muerta unconventional)
fracture_clean = fracture_df[
    (fracture_df['reservoir_type'] == 'unconventional') &
    (fracture_df['reservoir_subtype'] == 'shale') &
    (fracture_df['horizontal_lateral_length_m'] > 100) &  # Has lateral length
    (fracture_df['fracture_stages_count'] > 5)  # Multiple stages
].copy()

print(f"   Filtered to high-quality unconventional: {len(fracture_clean):,}")

# ============================================================================
# 2. CALCULATE KEY FRACTURE METRICS
# ============================================================================

print("\n2. Calculating fracture metrics...")

# Total proppant
fracture_clean['total_proppant_tons'] = (
    fracture_clean['proppant_domestic_tons'] +
    fracture_clean['proppant_imported_tons']
)

# Proppant intensity (KEY METRIC for completion quality)
fracture_clean['proppant_intensity_tons_per_m'] = (
    fracture_clean['total_proppant_tons'] /
    fracture_clean['horizontal_lateral_length_m']
)

# Proppant per stage
fracture_clean['proppant_per_stage_tons'] = (
    fracture_clean['total_proppant_tons'] /
    fracture_clean['fracture_stages_count']
)

# Stage spacing
fracture_clean['stage_spacing_m'] = (
    fracture_clean['horizontal_lateral_length_m'] /
    fracture_clean['fracture_stages_count']
)

# Water per stage
fracture_clean['water_per_stage_m3'] = (
    fracture_clean['frac_fluid_water_m3'] /
    fracture_clean['fracture_stages_count']
)

# High intensity completion flag (>0.5 tons/m is considered high intensity)
fracture_clean['high_intensity_completion'] = (
    fracture_clean['proppant_intensity_tons_per_m'] > 0.5
)

print(f"   Calculated metrics: proppant_intensity, stage_spacing, water_per_stage")

# ============================================================================
# 3. SELECT TEST FIELDS
# ============================================================================

print("\n3. Selecting test fields with best data...")

# Get fields with multiple wells completed (indicates active development)
field_well_counts = fracture_clean.groupby('field_name').size()
top_fields = field_well_counts[field_well_counts >= 3].sort_values(ascending=False).head(10)

print(f"\n   Top 10 fields by number of fracture jobs:")
for field, count in top_fields.items():
    print(f"     - {field}: {count} wells")

# Select 5 representative test fields
test_fields = list(top_fields.head(5).index)
print(f"\n   Selected {len(test_fields)} test fields for analysis")

# ============================================================================
# 4. AGGREGATE FRACTURE DATA BY FIELD
# ============================================================================

print("\n4. Aggregating fracture data by field...")

fracture_by_field = fracture_clean[
    fracture_clean['field_name'].isin(test_fields)
].groupby('field_name').agg({
    # Count metrics
    'fracture_job_id': 'count',  # Number of wells completed
    'well_id': 'nunique',  # Number of unique wells

    # Completion design metrics (averages)
    'horizontal_lateral_length_m': 'mean',
    'fracture_stages_count': 'mean',
    'total_proppant_tons': 'mean',
    'proppant_intensity_tons_per_m': 'mean',
    'proppant_per_stage_tons': 'mean',
    'stage_spacing_m': 'mean',

    # Fluid metrics
    'frac_fluid_water_m3': 'mean',
    'water_per_stage_m3': 'mean',

    # Equipment metrics
    'max_treatment_pressure_psi': 'mean',
    'frac_equipment_total_horsepower': 'mean',

    # Proppant sourcing
    'proppant_domestic_tons': 'mean',
    'proppant_imported_tons': 'mean',

    # Completion intensity
    'high_intensity_completion': 'mean',  # Fraction of high-intensity completions
}).round(2)

# Rename columns for clarity
fracture_by_field.columns = [
    'well_count',
    'unique_wells',
    'avg_lateral_length_m',
    'avg_stages_count',
    'avg_total_proppant_tons',
    'avg_proppant_intensity_tons_per_m',
    'avg_proppant_per_stage_tons',
    'avg_stage_spacing_m',
    'avg_frac_water_m3',
    'avg_water_per_stage_m3',
    'avg_max_pressure_psi',
    'avg_frac_horsepower',
    'avg_proppant_domestic_tons',
    'avg_proppant_imported_tons',
    'high_intensity_fraction'
]

print(f"   Aggregated data for {len(fracture_by_field)} fields")

# ============================================================================
# 5. LOAD FIELD SHAPES & DEPTH DATA
# ============================================================================

print("\n5. Loading field shapes & depth data...")
field_shapes = pd.read_csv(translated_dir / "field_shapes_depth_english.csv")

print(f"   Total fields with geometry: {len(field_shapes):,}")

# Extract only numerical depth data (exclude text fields)
depth_data = field_shapes[['field_name', 'depth_avg_m', 'depth_min_m', 'depth_max_m']].copy()

# Calculate depth range
depth_data['depth_range_m'] = depth_data['depth_max_m'] - depth_data['depth_min_m']

# ============================================================================
# 6. MERGE FRACTURE DATA WITH DEPTH DATA
# ============================================================================

print("\n6. Merging fracture data with depth data...")

integrated_data = fracture_by_field.merge(
    depth_data,
    left_index=True,  # field_name is index
    right_on='field_name',
    how='left'
)

integrated_data = integrated_data.set_index('field_name')

print(f"   Merged {len(integrated_data)} fields")

# ============================================================================
# 7. LOAD PRODUCTION DATA (if available)
# ============================================================================

print("\n7. Loading field production data (sample)...")
try:
    oil_prod = pd.read_csv(translated_dir / "oil_field_production_english.csv")

    # Get recent production for test fields
    recent_oil = oil_prod[
        (oil_prod['field_name'].isin(test_fields)) &
        (oil_prod['year'] >= 2023) &
        (oil_prod['concept'] == 'unconventional_production_m3')
    ].groupby('field_name').agg({
        'quantity': 'sum'
    }).rename(columns={'quantity': 'recent_oil_production_m3'})

    # Merge with integrated data
    integrated_data = integrated_data.merge(
        recent_oil,
        left_index=True,
        right_index=True,
        how='left'
    )

    print(f"   Added production data for {len(recent_oil)} fields")

except Exception as e:
    print(f"   ⚠️  Could not load production data: {e}")

# ============================================================================
# 8. DISPLAY RESULTS
# ============================================================================

print("\n" + "="*80)
print("INTEGRATED TEST FIELDS - NUMERICAL DATA ONLY")
print("="*80)

for field_name in integrated_data.index:
    print(f"\n{'─'*80}")
    print(f"FIELD: {field_name}")
    print(f"{'─'*80}")

    field_data = integrated_data.loc[field_name]

    print("\n📊 WELL COUNT & COMPLETION ACTIVITY:")
    print(f"  Well count (fracture jobs):        {field_data['well_count']:.0f}")
    print(f"  Unique wells:                      {field_data['unique_wells']:.0f}")

    print("\n🔧 COMPLETION DESIGN AVERAGES:")
    print(f"  Horizontal lateral length:         {field_data['avg_lateral_length_m']:.1f} m")
    print(f"  Fracture stages per well:          {field_data['avg_stages_count']:.1f}")
    print(f"  Stage spacing:                     {field_data['avg_stage_spacing_m']:.1f} m")

    print("\n🪨 PROPPANT METRICS:")
    print(f"  Total proppant per well:           {field_data['avg_total_proppant_tons']:.1f} tons")
    print(f"  Proppant intensity:                {field_data['avg_proppant_intensity_tons_per_m']:.2f} tons/m  ⭐ KEY METRIC")
    print(f"  Proppant per stage:                {field_data['avg_proppant_per_stage_tons']:.1f} tons")
    print(f"  Domestic proppant:                 {field_data['avg_proppant_domestic_tons']:.1f} tons")
    print(f"  Imported proppant:                 {field_data['avg_proppant_imported_tons']:.1f} tons")

    print("\n💧 FLUID METRICS:")
    print(f"  Total water per well:              {field_data['avg_frac_water_m3']:.1f} m³")
    print(f"  Water per stage:                   {field_data['avg_water_per_stage_m3']:.1f} m³")

    print("\n⚙️  EQUIPMENT & PRESSURE:")
    print(f"  Max treatment pressure:            {field_data['avg_max_pressure_psi']:.0f} psi")
    print(f"  Total hydraulic horsepower:        {field_data['avg_frac_horsepower']:.0f} hp")

    print("\n📏 RESERVOIR DEPTH:")
    if pd.notna(field_data.get('depth_avg_m')):
        print(f"  Average depth:                     {field_data['depth_avg_m']:.1f} m")
        print(f"  Minimum depth:                     {field_data['depth_min_m']:.1f} m")
        print(f"  Maximum depth:                     {field_data['depth_max_m']:.1f} m")
        print(f"  Depth range:                       {field_data['depth_range_m']:.1f} m")
    else:
        print(f"  Depth data:                        Not available")

    print("\n🎯 COMPLETION QUALITY:")
    print(f"  High-intensity completion rate:    {field_data['high_intensity_fraction']*100:.1f}%")

    if 'recent_oil_production_m3' in field_data and pd.notna(field_data['recent_oil_production_m3']):
        print("\n🛢️  RECENT PRODUCTION (2023+):")
        print(f"  Unconventional oil production:     {field_data['recent_oil_production_m3']:.1f} m³")

# ============================================================================
# 9. SAVE INTEGRATED DATA
# ============================================================================

print("\n" + "="*80)
print("SAVING INTEGRATED DATA")
print("="*80)

output_file = translated_dir / "TEST_integrated_fracture_field_data.csv"
integrated_data.to_csv(output_file)

print(f"\n✅ Saved integrated data to: {output_file.name}")
print(f"   Fields: {len(integrated_data)}")
print(f"   Metrics: {len(integrated_data.columns)}")

# ============================================================================
# 10. SUMMARY STATISTICS
# ============================================================================

print("\n" + "="*80)
print("SUMMARY STATISTICS (All Test Fields)")
print("="*80)

summary_stats = integrated_data[[
    'avg_lateral_length_m',
    'avg_stages_count',
    'avg_proppant_intensity_tons_per_m',
    'avg_stage_spacing_m',
    'avg_max_pressure_psi',
    'avg_frac_horsepower',
    'depth_avg_m'
]].describe().round(2)

print("\n", summary_stats)

print("\n" + "="*80)
print("✅ FRACTURE INTEGRATION TEST COMPLETE")
print("="*80)
print("\nKey Findings:")
print("  - Successfully merged fracture, depth, and production data")
print("  - All numerical metrics preserved and calculated")
print("  - Proppant intensity ranges from", end=" ")
print(f"{integrated_data['avg_proppant_intensity_tons_per_m'].min():.2f} to", end=" ")
print(f"{integrated_data['avg_proppant_intensity_tons_per_m'].max():.2f} tons/m")
print("  - Ready for pipeline integration")
print()
