"""
Expanded Field Analysis - Gas, Conventional vs Unconventional, Advanced Metrics

This script expands the integration test to include:
1. Gas field production alongside oil
2. Conventional vs unconventional field comparison
3. Advanced calculated metrics (cost proxies, efficiency, intensity)
4. Production performance correlation with completion design
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json

# Paths
base_dir = Path(__file__).parent.parent
translated_dir = base_dir / "raw" / "translated"

print("\n" + "="*80)
print("EXPANDED FIELD ANALYSIS")
print("Gas + Conventional/Unconventional + Advanced Metrics")
print("="*80)

# ============================================================================
# 1. LOAD ALL DATA SOURCES
# ============================================================================

print("\n1. Loading data sources...")

# Fracture data
fracture_df = pd.read_csv(translated_dir / "fracture_completion_data_english.csv")
print(f"   ✓ Fracture data: {len(fracture_df):,} jobs")

# Field shapes & depth
field_shapes = pd.read_csv(translated_dir / "field_shapes_depth_english.csv")
print(f"   ✓ Field shapes: {len(field_shapes):,} fields")

# Oil production
oil_prod = pd.read_csv(translated_dir / "oil_field_production_english.csv")
print(f"   ✓ Oil production: {len(oil_prod):,} records")

# Gas production
gas_prod = pd.read_csv(translated_dir / "gas_field_production_english.csv")
print(f"   ✓ Gas production: {len(gas_prod):,} records")

# Well characteristics
well_char = pd.read_csv(translated_dir / "well_characteristics_english.csv")
print(f"   ✓ Well characteristics: {len(well_char):,} wells")

# ============================================================================
# 2. PREPARE FRACTURE DATA WITH ADVANCED METRICS
# ============================================================================

print("\n2. Calculating advanced fracture metrics...")

# Filter for quality data
fracture_clean = fracture_df[
    (fracture_df['horizontal_lateral_length_m'] > 0) &
    (fracture_df['fracture_stages_count'] > 0)
].copy()

print(f"   Filtered: {len(fracture_clean):,} jobs with complete data")

# Basic metrics
fracture_clean['total_proppant_tons'] = (
    fracture_clean['proppant_domestic_tons'] +
    fracture_clean['proppant_imported_tons']
)

fracture_clean['proppant_intensity_tons_per_m'] = (
    fracture_clean['total_proppant_tons'] /
    fracture_clean['horizontal_lateral_length_m']
)

fracture_clean['stage_spacing_m'] = (
    fracture_clean['horizontal_lateral_length_m'] /
    fracture_clean['fracture_stages_count']
)

fracture_clean['proppant_per_stage_tons'] = (
    fracture_clean['total_proppant_tons'] /
    fracture_clean['fracture_stages_count']
)

fracture_clean['water_per_stage_m3'] = (
    fracture_clean['frac_fluid_water_m3'] /
    fracture_clean['fracture_stages_count']
)

# NEW: Advanced metrics
print("   Calculating cost proxy metrics...")

# Proppant sourcing ratio
fracture_clean['proppant_imported_fraction'] = (
    fracture_clean['proppant_imported_tons'] /
    fracture_clean['total_proppant_tons'].replace(0, np.nan)
)

# Water intensity
fracture_clean['water_intensity_m3_per_m'] = (
    fracture_clean['frac_fluid_water_m3'] /
    fracture_clean['horizontal_lateral_length_m']
)

# Completion cost proxy ($/well estimate based on proppant, stages, water)
# Rough estimates: proppant $100/ton, stage $50k, water $5/m3, HP $50/hp-day
fracture_clean['completion_cost_proxy_usd'] = (
    (fracture_clean['total_proppant_tons'] * 100) +  # Proppant cost
    (fracture_clean['fracture_stages_count'] * 50000) +  # Stage cost
    (fracture_clean['frac_fluid_water_m3'] * 5) +  # Water cost
    (fracture_clean['frac_equipment_total_horsepower'] * 50 * 7)  # HP rental ~7 days
)

# Horsepower per stage (indicates job intensity)
fracture_clean['hp_per_stage'] = (
    fracture_clean['frac_equipment_total_horsepower'] /
    fracture_clean['fracture_stages_count']
)

# Completion intensity flag (very high intensity = >3 tons/m)
fracture_clean['very_high_intensity'] = (
    fracture_clean['proppant_intensity_tons_per_m'] > 3.0
)

print(f"   ✓ Calculated 10 advanced metrics")

# ============================================================================
# 3. AGGREGATE BY FIELD AND RESERVOIR TYPE
# ============================================================================

print("\n3. Aggregating by field and reservoir type...")

fracture_by_field = fracture_clean.groupby(['field_name', 'reservoir_type']).agg({
    'fracture_job_id': 'count',
    'well_id': 'nunique',

    # Design metrics
    'horizontal_lateral_length_m': 'mean',
    'fracture_stages_count': 'mean',
    'stage_spacing_m': 'mean',

    # Proppant metrics
    'total_proppant_tons': 'mean',
    'proppant_intensity_tons_per_m': 'mean',
    'proppant_per_stage_tons': 'mean',
    'proppant_imported_fraction': 'mean',

    # Fluid metrics
    'frac_fluid_water_m3': 'mean',
    'water_per_stage_m3': 'mean',
    'water_intensity_m3_per_m': 'mean',

    # Equipment metrics
    'max_treatment_pressure_psi': 'mean',
    'frac_equipment_total_horsepower': 'mean',
    'hp_per_stage': 'mean',

    # Cost proxy
    'completion_cost_proxy_usd': 'mean',

    # Intensity flags
    'very_high_intensity': 'mean',
}).round(2)

fracture_by_field.columns = [
    'well_count', 'unique_wells',
    'avg_lateral_m', 'avg_stages', 'avg_stage_spacing_m',
    'avg_proppant_tons', 'avg_proppant_intensity_tons_per_m', 'avg_proppant_per_stage_tons',
    'avg_proppant_import_fraction',
    'avg_water_m3', 'avg_water_per_stage_m3', 'avg_water_intensity_m3_per_m',
    'avg_pressure_psi', 'avg_hp', 'avg_hp_per_stage',
    'avg_completion_cost_usd',
    'very_high_intensity_fraction'
]

fracture_by_field = fracture_by_field.reset_index()

print(f"   Aggregated: {len(fracture_by_field)} field-reservoir combinations")

# ============================================================================
# 4. MERGE WITH DEPTH DATA
# ============================================================================

print("\n4. Merging with depth data...")

depth_data = field_shapes[['field_name', 'depth_avg_m', 'depth_min_m', 'depth_max_m']].copy()
depth_data['depth_range_m'] = depth_data['depth_max_m'] - depth_data['depth_min_m']

# Drilling cost proxy (rough: $150/m for vertical, $300/m for lateral)
# Assuming 80% vertical drilling to target depth
depth_data['drilling_cost_proxy_usd'] = (
    (depth_data['depth_avg_m'] * 150 * 0.8) +  # Vertical section
    (2500 * 300 * 0.2)  # Assume ~2500m lateral average
)

integrated = fracture_by_field.merge(depth_data, on='field_name', how='left')

print(f"   Merged: {len(integrated)} records with depth data")

# ============================================================================
# 5. GET PRODUCTION DATA (OIL + GAS)
# ============================================================================

print("\n5. Loading production data (recent 2 years)...")

# Oil production (unconventional)
recent_oil = oil_prod[
    (oil_prod['year'] >= 2023) &
    (oil_prod['concept'] == 'unconventional_production_m3')
].groupby('field_name').agg({
    'quantity': 'sum'
}).rename(columns={'quantity': 'oil_prod_2023plus_m3'})

# Gas production (unconventional)
recent_gas = gas_prod[
    (gas_prod['year'] >= 2023) &
    (gas_prod['concept'] == 'unconventional_gas_mm3')
].groupby('field_name').agg({
    'quantity': 'sum'
}).rename(columns={'quantity': 'gas_prod_2023plus_mm3'})

# Merge production
integrated = integrated.merge(recent_oil, left_on='field_name', right_index=True, how='left')
integrated = integrated.merge(recent_gas, left_on='field_name', right_index=True, how='left')

print(f"   Added oil production for {recent_oil.shape[0]} fields")
print(f"   Added gas production for {recent_gas.shape[0]} fields")

# ============================================================================
# 6. CALCULATE EFFICIENCY METRICS
# ============================================================================

print("\n6. Calculating efficiency metrics...")

# Production per proppant ton (oil)
integrated['oil_m3_per_proppant_ton'] = (
    integrated['oil_prod_2023plus_m3'] /
    (integrated['avg_proppant_tons'] * integrated['well_count'])
)

# Production per stage (oil)
integrated['oil_m3_per_stage'] = (
    integrated['oil_prod_2023plus_m3'] /
    (integrated['avg_stages'] * integrated['well_count'])
)

# Production per well
integrated['oil_m3_per_well'] = (
    integrated['oil_prod_2023plus_m3'] / integrated['well_count']
)

# Gas production per well
integrated['gas_mm3_per_well'] = (
    integrated['gas_prod_2023plus_mm3'] / integrated['well_count']
)

# Total well cost proxy (drilling + completion)
integrated['total_well_cost_proxy_usd'] = (
    integrated['drilling_cost_proxy_usd'] +
    integrated['avg_completion_cost_usd']
)

print(f"   ✓ Calculated 5 efficiency metrics")

# ============================================================================
# 7. SELECT TEST FIELDS FOR COMPARISON
# ============================================================================

print("\n7. Selecting test fields...")

# Get top unconventional fields
unconv = integrated[integrated['reservoir_type'] == 'unconventional'].copy()
unconv_sorted = unconv.sort_values('well_count', ascending=False)

# Get top 5 unconventional with oil production
top_unconv_oil = unconv_sorted[
    unconv_sorted['oil_prod_2023plus_m3'].notna()
].head(5)

# Get top 3 unconventional with gas production
top_unconv_gas = unconv_sorted[
    unconv_sorted['gas_prod_2023plus_mm3'].notna()
].head(3)

# Get conventional fields if any
conv = integrated[integrated['reservoir_type'] == 'conventional'].copy()
conv_sorted = conv.sort_values('well_count', ascending=False)
top_conv = conv_sorted.head(3) if len(conv) > 0 else pd.DataFrame()

print(f"   Selected {len(top_unconv_oil)} unconventional oil fields")
print(f"   Selected {len(top_unconv_gas)} unconventional gas fields")
print(f"   Selected {len(top_conv)} conventional fields")

# ============================================================================
# 8. DISPLAY RESULTS - UNCONVENTIONAL OIL FIELDS
# ============================================================================

print("\n" + "="*80)
print("UNCONVENTIONAL OIL FIELDS - TOP 5")
print("="*80)

for idx, row in top_unconv_oil.iterrows():
    print(f"\n{'─'*80}")
    print(f"FIELD: {row['field_name']}")
    print(f"TYPE: Unconventional Shale/Tight Oil")
    print(f"{'─'*80}")

    print("\n📊 ACTIVITY & SCALE:")
    print(f"  Wells completed:                   {row['well_count']:.0f}")
    print(f"  Unique wells:                      {row['unique_wells']:.0f}")

    print("\n🔧 COMPLETION DESIGN:")
    print(f"  Lateral length:                    {row['avg_lateral_m']:.0f} m")
    print(f"  Fracture stages:                   {row['avg_stages']:.1f}")
    print(f"  Stage spacing:                     {row['avg_stage_spacing_m']:.1f} m")

    print("\n🪨 PROPPANT METRICS:")
    print(f"  Total proppant per well:           {row['avg_proppant_tons']:.0f} tons")
    print(f"  Proppant intensity:                {row['avg_proppant_intensity_tons_per_m']:.2f} tons/m  ⭐")
    print(f"  Proppant per stage:                {row['avg_proppant_per_stage_tons']:.1f} tons")
    print(f"  Imported proppant fraction:        {row['avg_proppant_import_fraction']*100:.1f}%")

    print("\n💧 WATER METRICS:")
    print(f"  Total water per well:              {row['avg_water_m3']:.0f} m³")
    print(f"  Water per stage:                   {row['avg_water_per_stage_m3']:.0f} m³")
    print(f"  Water intensity:                   {row['avg_water_intensity_m3_per_m']:.1f} m³/m")

    print("\n⚙️  EQUIPMENT:")
    print(f"  Max pressure:                      {row['avg_pressure_psi']:.0f} psi")
    print(f"  Total horsepower:                  {row['avg_hp']:.0f} hp")
    print(f"  HP per stage:                      {row['avg_hp_per_stage']:.0f} hp")

    print("\n📏 RESERVOIR:")
    if pd.notna(row.get('depth_avg_m')):
        print(f"  Average depth:                     {row['depth_avg_m']:.0f} m")
        print(f"  Depth range:                       {row['depth_min_m']:.0f} - {row['depth_max_m']:.0f} m")
    else:
        print(f"  Depth data:                        Not available")

    print("\n💰 COST PROXIES:")
    print(f"  Drilling cost (proxy):             ${row['drilling_cost_proxy_usd']:,.0f}")
    print(f"  Completion cost (proxy):           ${row['avg_completion_cost_usd']:,.0f}")
    print(f"  Total well cost (proxy):           ${row['total_well_cost_proxy_usd']:,.0f}")

    print("\n🛢️  OIL PRODUCTION (2023+):")
    print(f"  Total field production:            {row['oil_prod_2023plus_m3']:,.0f} m³")
    print(f"  Production per well:               {row['oil_m3_per_well']:,.0f} m³/well")
    print(f"  Production per proppant ton:       {row['oil_m3_per_proppant_ton']:.2f} m³/ton")
    print(f"  Production per stage:              {row['oil_m3_per_stage']:.0f} m³/stage")

    print("\n🎯 COMPLETION QUALITY:")
    print(f"  Very high intensity (>3 tons/m):   {row['very_high_intensity_fraction']*100:.0f}%")

# ============================================================================
# 9. DISPLAY RESULTS - UNCONVENTIONAL GAS FIELDS
# ============================================================================

if len(top_unconv_gas) > 0:
    print("\n" + "="*80)
    print("UNCONVENTIONAL GAS FIELDS - TOP 3")
    print("="*80)

    for idx, row in top_unconv_gas.iterrows():
        print(f"\n{'─'*80}")
        print(f"FIELD: {row['field_name']}")
        print(f"TYPE: Unconventional Shale/Tight Gas")
        print(f"{'─'*80}")

        print("\n📊 ACTIVITY:")
        print(f"  Wells completed:                   {row['well_count']:.0f}")

        print("\n🔧 COMPLETION DESIGN:")
        print(f"  Lateral length:                    {row['avg_lateral_m']:.0f} m")
        print(f"  Fracture stages:                   {row['avg_stages']:.1f}")
        print(f"  Proppant intensity:                {row['avg_proppant_intensity_tons_per_m']:.2f} tons/m  ⭐")

        print("\n⛽ GAS PRODUCTION (2023+):")
        if pd.notna(row.get('gas_prod_2023plus_mm3')):
            print(f"  Total field production:            {row['gas_prod_2023plus_mm3']:,.1f} Mm³")
            print(f"  Production per well:               {row['gas_mm3_per_well']:,.1f} Mm³/well")
        else:
            print(f"  Gas production:                    Data not available in sample")

        print("\n💰 COST PROXY:")
        print(f"  Total well cost (proxy):           ${row['total_well_cost_proxy_usd']:,.0f}")

# ============================================================================
# 10. DISPLAY RESULTS - CONVENTIONAL FIELDS COMPARISON
# ============================================================================

if len(top_conv) > 0:
    print("\n" + "="*80)
    print("CONVENTIONAL FIELDS - FOR COMPARISON")
    print("="*80)

    for idx, row in top_conv.iterrows():
        print(f"\n{'─'*80}")
        print(f"FIELD: {row['field_name']}")
        print(f"TYPE: Conventional")
        print(f"{'─'*80}")

        print("\n📊 ACTIVITY:")
        print(f"  Wells completed:                   {row['well_count']:.0f}")

        print("\n🔧 COMPLETION DESIGN:")
        print(f"  Lateral length:                    {row['avg_lateral_m']:.0f} m")
        print(f"  Fracture stages:                   {row['avg_stages']:.1f}")
        print(f"  Proppant intensity:                {row['avg_proppant_intensity_tons_per_m']:.2f} tons/m")

        print("\n💡 NOTE: Much less intensive than unconventional completions")

# ============================================================================
# 11. COMPARATIVE STATISTICS
# ============================================================================

print("\n" + "="*80)
print("COMPARATIVE STATISTICS")
print("="*80)

if len(unconv) > 0:
    print("\n📊 UNCONVENTIONAL FIELDS (Average across all):")
    print(f"  Wells per field:                   {unconv['well_count'].mean():.1f}")
    print(f"  Lateral length:                    {unconv['avg_lateral_m'].mean():.0f} m")
    print(f"  Stages per well:                   {unconv['avg_stages'].mean():.1f}")
    print(f"  Proppant intensity:                {unconv['avg_proppant_intensity_tons_per_m'].mean():.2f} tons/m")
    print(f"  Completion cost (proxy):           ${unconv['avg_completion_cost_usd'].mean():,.0f}")
    print(f"  Total well cost (proxy):           ${unconv['total_well_cost_proxy_usd'].mean():,.0f}")

if len(conv) > 0:
    print("\n📊 CONVENTIONAL FIELDS (Average across all):")
    print(f"  Wells per field:                   {conv['well_count'].mean():.1f}")
    print(f"  Lateral length:                    {conv['avg_lateral_m'].mean():.0f} m")
    print(f"  Stages per well:                   {conv['avg_stages'].mean():.1f}")
    print(f"  Proppant intensity:                {conv['avg_proppant_intensity_tons_per_m'].mean():.2f} tons/m")
    print(f"  Completion cost (proxy):           ${conv['avg_completion_cost_usd'].mean():,.0f}")

    print("\n🔄 UNCONVENTIONAL VS CONVENTIONAL RATIO:")
    print(f"  Proppant intensity ratio:          {unconv['avg_proppant_intensity_tons_per_m'].mean() / conv['avg_proppant_intensity_tons_per_m'].mean():.1f}x")
    print(f"  Completion cost ratio:             {unconv['avg_completion_cost_usd'].mean() / conv['avg_completion_cost_usd'].mean():.1f}x")

# ============================================================================
# 12. SAVE RESULTS
# ============================================================================

print("\n" + "="*80)
print("SAVING RESULTS")
print("="*80)

output_file = translated_dir / "TEST_expanded_field_analysis.csv"
integrated.to_csv(output_file, index=False)

print(f"\n✅ Saved: {output_file.name}")
print(f"   Fields: {len(integrated)}")
print(f"   Metrics: {len(integrated.columns)}")

print("\n" + "="*80)
print("✅ EXPANDED ANALYSIS COMPLETE")
print("="*80)
print()
