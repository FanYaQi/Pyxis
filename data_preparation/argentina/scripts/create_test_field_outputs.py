"""
Create Separate Test Field Outputs

Creates two test field CSV files:
1. Gas production fields - fields with significant gas production
2. Fracture-intensive fields - unconventional fields with complete fracture data
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json

# Paths
base_dir = Path(__file__).parent.parent
translated_dir = base_dir / "raw" / "translated"
output_dir = base_dir / "output"
output_dir.mkdir(exist_ok=True)

print("\n" + "="*80)
print("CREATING SPECIALIZED TEST FIELD OUTPUTS")
print("="*80)

# ============================================================================
# LOAD DATA
# ============================================================================

print("\n1. Loading data sources...")

# Gas production
gas_prod = pd.read_csv(translated_dir / "gas_field_production_english.csv")
print(f"   ✓ Gas production: {len(gas_prod):,} records")

# Oil production
oil_prod = pd.read_csv(translated_dir / "oil_field_production_english.csv")
print(f"   ✓ Oil production: {len(oil_prod):,} records")

# Fracture data
fracture_df = pd.read_csv(translated_dir / "fracture_completion_data_english.csv")
print(f"   ✓ Fracture data: {len(fracture_df):,} jobs")

# Field shapes
field_shapes = pd.read_csv(translated_dir / "field_shapes_depth_english.csv")
print(f"   ✓ Field shapes: {len(field_shapes):,} fields")

# Well production
well_prod = pd.read_csv(translated_dir / "well_production_2025_english.csv")
print(f"   ✓ Well production: {len(well_prod):,} records")

# ============================================================================
# PART 1: GAS PRODUCTION FIELDS
# ============================================================================

print("\n" + "="*80)
print("PART 1: GAS PRODUCTION FIELDS")
print("="*80)

# Aggregate gas production by field (all concepts)
gas_by_field_all = gas_prod[
    gas_prod['year'] >= 2023
].groupby('field_name').agg({
    'quantity': 'sum'
}).rename(columns={'quantity': 'total_gas_prod_mm3'})

print(f"\n   Gas production data: {len(gas_by_field_all)} fields")

# Get gas by concept for detailed breakdown
gas_by_concept = gas_prod[
    gas_prod['year'] >= 2023
].pivot_table(
    values='quantity',
    index='field_name',
    columns='concept',
    aggfunc='sum',
    fill_value=0
)

# Add concept columns
gas_fields = gas_by_field_all.copy()

if 'high_pressure_gas_mm3' in gas_by_concept.columns:
    gas_fields['high_pressure_gas_mm3'] = gas_by_concept['high_pressure_gas_mm3']
if 'medium_pressure_gas_mm3' in gas_by_concept.columns:
    gas_fields['medium_pressure_gas_mm3'] = gas_by_concept['medium_pressure_gas_mm3']
if 'low_pressure_gas_mm3' in gas_by_concept.columns:
    gas_fields['low_pressure_gas_mm3'] = gas_by_concept['low_pressure_gas_mm3']
if 'unconventional_gas_mm3' in gas_by_concept.columns:
    gas_fields['unconventional_gas_mm3'] = gas_by_concept['unconventional_gas_mm3']
if 'gas_reinjection_formation_mm3' in gas_by_concept.columns:
    gas_fields['gas_reinjection_mm3'] = gas_by_concept['gas_reinjection_formation_mm3']

# Get oil production for gas fields
oil_by_field = oil_prod[
    oil_prod['year'] >= 2023
].groupby('field_name').agg({
    'quantity': 'sum'
}).rename(columns={'quantity': 'total_oil_prod_m3'})

gas_fields = gas_fields.merge(oil_by_field, left_index=True, right_index=True, how='left').fillna(0)

# Calculate GOR
gas_fields['gor'] = (
    gas_fields['total_gas_prod_mm3'] * 1000 /
    gas_fields['total_oil_prod_m3'].replace(0, np.nan)
).fillna(np.inf)

# Get active well count
active_wells = well_prod.groupby('field_name')['well_id'].nunique().rename('active_well_count')
gas_fields = gas_fields.merge(active_wells, left_index=True, right_index=True, how='left').fillna(0)

# Get geometry data
def extract_centroid(geojson_str):
    try:
        geom_dict = json.loads(geojson_str)
        all_coords = []
        if geom_dict['type'] == 'MultiPolygon':
            for polygon in geom_dict['coordinates']:
                all_coords.extend(polygon[0])
        elif geom_dict['type'] == 'Polygon':
            all_coords.extend(geom_dict['coordinates'][0])
        if all_coords:
            lons = [coord[0] for coord in all_coords]
            lats = [coord[1] for coord in all_coords]
            return sum(lons)/len(lons), sum(lats)/len(lats)
    except:
        pass
    return np.nan, np.nan

field_shapes['centroid_lon'], field_shapes['centroid_lat'] = zip(*field_shapes['field_boundary_geojson'].apply(extract_centroid))

geometry_cols = field_shapes[['field_name', 'centroid_lat', 'centroid_lon',
                               'depth_avg_m', 'depth_min_m', 'depth_max_m']].copy()
geometry_cols = geometry_cols.set_index('field_name')

gas_fields = gas_fields.merge(geometry_cols, left_index=True, right_index=True, how='left')

# Select top 10 gas fields
gas_fields = gas_fields.reset_index()
gas_fields = gas_fields.sort_values('total_gas_prod_mm3', ascending=False).head(10)

print(f"\n   Selected top 10 gas fields:")
for idx, row in gas_fields.iterrows():
    print(f"     {row['field_name']}: {row['total_gas_prod_mm3']:.1f} Mm³")

# Reorder columns
gas_output_cols = [
    'field_name',
    'total_gas_prod_mm3',
    'high_pressure_gas_mm3',
    'medium_pressure_gas_mm3',
    'low_pressure_gas_mm3',
    'unconventional_gas_mm3',
    'gas_reinjection_mm3',
    'total_oil_prod_m3',
    'gor',
    'active_well_count',
    'centroid_lat',
    'centroid_lon',
    'depth_avg_m',
    'depth_min_m',
    'depth_max_m',
]

existing_cols = [col for col in gas_output_cols if col in gas_fields.columns]
gas_fields_output = gas_fields[existing_cols]

# Save
gas_output_file = output_dir / "TEST_gas_production_fields.csv"
gas_fields_output.to_csv(gas_output_file, index=False)

print(f"\n✅ Gas fields output saved: {gas_output_file.name}")
print(f"   Fields: {len(gas_fields_output)}")
print(f"   Columns: {len(gas_fields_output.columns)}")

# ============================================================================
# PART 2: FRACTURE-INTENSIVE FIELDS
# ============================================================================

print("\n" + "="*80)
print("PART 2: FRACTURE-INTENSIVE UNCONVENTIONAL FIELDS")
print("="*80)

# Calculate fracture metrics
fracture_df['total_proppant_tons'] = (
    fracture_df['proppant_domestic_tons'] +
    fracture_df['proppant_imported_tons']
)

# Filter for high-quality unconventional fracture data
fracture_quality = fracture_df[
    (fracture_df['reservoir_type'] == 'unconventional') &
    (fracture_df['horizontal_lateral_length_m'] > 500) &  # Horizontal wells
    (fracture_df['fracture_stages_count'] >= 10) &  # Multi-stage
    (fracture_df['total_proppant_tons'] > 1000)  # Significant proppant
].copy()

print(f"\n   High-quality unconventional fracture jobs: {len(fracture_quality)}")

# Aggregate by field
frac_by_field = fracture_quality.groupby('field_name').agg({
    'fracture_job_id': 'count',
    'well_id': 'nunique',

    # Proppant
    'total_proppant_tons': ['sum', 'mean'],
    'proppant_domestic_tons': 'sum',
    'proppant_imported_tons': 'sum',

    # Fluids
    'frac_fluid_water_m3': ['sum', 'mean'],
    'frac_fluid_co2_m3': ['sum', 'mean'],

    # Design
    'horizontal_lateral_length_m': 'mean',
    'fracture_stages_count': 'mean',

    # Equipment
    'max_treatment_pressure_psi': 'mean',
    'frac_equipment_total_horsepower': 'mean',

    # Formation
    'producing_formation': lambda x: x.mode()[0] if len(x.mode()) > 0 else '',
    'reservoir_subtype': lambda x: x.mode()[0] if len(x.mode()) > 0 else '',
}).round(2)

# Flatten columns
frac_by_field.columns = [
    'fracture_job_count',
    'fractured_well_count',
    'total_proppant_tons',
    'avg_proppant_per_well_tons',
    'total_proppant_domestic_tons',
    'total_proppant_imported_tons',
    'total_frac_water_m3',
    'avg_frac_water_per_well_m3',
    'total_co2_m3',
    'avg_co2_per_well_m3',
    'avg_lateral_length_m',
    'avg_fracture_stages',
    'avg_max_pressure_psi',
    'avg_frac_horsepower',
    'primary_formation',
    'reservoir_subtype',
]

# Calculate additional metrics
frac_by_field['proppant_intensity_tons_per_m'] = (
    frac_by_field['avg_proppant_per_well_tons'] /
    frac_by_field['avg_lateral_length_m']
).round(3)

frac_by_field['stage_spacing_m'] = (
    frac_by_field['avg_lateral_length_m'] /
    frac_by_field['avg_fracture_stages']
).round(1)

frac_by_field['proppant_import_fraction'] = (
    frac_by_field['total_proppant_imported_tons'] /
    frac_by_field['total_proppant_tons']
).round(3)

# Get production data
oil_by_field = oil_prod[
    (oil_prod['year'] >= 2023) &
    (oil_prod['concept'] == 'unconventional_production_m3')
].groupby('field_name').agg({
    'quantity': 'sum'
}).rename(columns={'quantity': 'unconventional_oil_prod_m3'})

frac_by_field = frac_by_field.merge(oil_by_field, left_index=True, right_index=True, how='left')

# Get active wells
frac_by_field = frac_by_field.merge(active_wells, left_index=True, right_index=True, how='left')

# Get geometry
frac_by_field = frac_by_field.merge(geometry_cols, left_index=True, right_index=True, how='left')

# Calculate production efficiency
frac_by_field['oil_m3_per_proppant_ton'] = (
    frac_by_field['unconventional_oil_prod_m3'] /
    frac_by_field['total_proppant_tons']
).round(3)

# Select top 10 by fracture job count
frac_by_field = frac_by_field.reset_index()
frac_by_field = frac_by_field.sort_values('fracture_job_count', ascending=False).head(10)

print(f"\n   Selected top 10 fracture-intensive fields:")
for idx, row in frac_by_field.iterrows():
    print(f"     {row['field_name']}: {row['fracture_job_count']:.0f} jobs, " +
          f"{row['proppant_intensity_tons_per_m']:.2f} tons/m")

# Reorder columns for output
frac_output_cols = [
    'field_name',

    # Production
    'unconventional_oil_prod_m3',
    'active_well_count',
    'oil_m3_per_proppant_ton',

    # Well counts
    'fractured_well_count',
    'fracture_job_count',

    # Formation
    'primary_formation',
    'reservoir_subtype',

    # Geometry
    'centroid_lat',
    'centroid_lon',
    'depth_avg_m',
    'depth_min_m',
    'depth_max_m',

    # Proppant
    'total_proppant_tons',
    'avg_proppant_per_well_tons',
    'proppant_intensity_tons_per_m',
    'total_proppant_domestic_tons',
    'total_proppant_imported_tons',
    'proppant_import_fraction',

    # Fluids
    'total_frac_water_m3',
    'avg_frac_water_per_well_m3',
    'total_co2_m3',
    'avg_co2_per_well_m3',

    # Design
    'avg_lateral_length_m',
    'avg_fracture_stages',
    'stage_spacing_m',

    # Equipment
    'avg_max_pressure_psi',
    'avg_frac_horsepower',
]

existing_frac_cols = [col for col in frac_output_cols if col in frac_by_field.columns]
frac_fields_output = frac_by_field[existing_frac_cols]

# Save
frac_output_file = output_dir / "TEST_fracture_intensive_fields.csv"
frac_fields_output.to_csv(frac_output_file, index=False)

print(f"\n✅ Fracture fields output saved: {frac_output_file.name}")
print(f"   Fields: {len(frac_fields_output)}")
print(f"   Columns: {len(frac_fields_output.columns)}")

# ============================================================================
# DISPLAY SUMMARIES
# ============================================================================

print("\n" + "="*80)
print("GAS PRODUCTION FIELDS - SUMMARY")
print("="*80)

for idx, row in gas_fields_output.iterrows():
    print(f"\n{row['field_name']}")
    print(f"  Gas production: {row['total_gas_prod_mm3']:,.1f} Mm³")
    if 'high_pressure_gas_mm3' in row:
        print(f"    High pressure: {row.get('high_pressure_gas_mm3', 0):,.1f} Mm³")
        print(f"    Medium pressure: {row.get('medium_pressure_gas_mm3', 0):,.1f} Mm³")
        print(f"    Low pressure: {row.get('low_pressure_gas_mm3', 0):,.1f} Mm³")
    if row.get('total_oil_prod_m3', 0) > 0:
        print(f"  Oil production: {row['total_oil_prod_m3']:,.0f} m³")
        if np.isfinite(row['gor']):
            print(f"  GOR: {row['gor']:.2f}")
    print(f"  Active wells: {row.get('active_well_count', 0):.0f}")
    if pd.notna(row.get('depth_avg_m')):
        print(f"  Depth: {row['depth_avg_m']:.0f}m")
    if pd.notna(row.get('centroid_lat')):
        print(f"  Location: {row['centroid_lat']:.4f}°, {row['centroid_lon']:.4f}°")

print("\n" + "="*80)
print("FRACTURE-INTENSIVE FIELDS - SUMMARY")
print("="*80)

for idx, row in frac_fields_output.iterrows():
    print(f"\n{row['field_name']}")
    print(f"  Formation: {row.get('primary_formation', 'N/A')} ({row.get('reservoir_subtype', 'N/A')})")
    if pd.notna(row.get('unconventional_oil_prod_m3')):
        print(f"  Oil production: {row['unconventional_oil_prod_m3']:,.0f} m³")
    print(f"  Fractured wells: {row['fractured_well_count']:.0f} ({row['fracture_job_count']:.0f} jobs)")
    print(f"  Active wells: {row.get('active_well_count', 0):.0f}")
    print(f"\n  Completion Design:")
    print(f"    Lateral length: {row['avg_lateral_length_m']:.0f} m")
    print(f"    Fracture stages: {row['avg_fracture_stages']:.1f}")
    print(f"    Stage spacing: {row['stage_spacing_m']:.1f} m")
    print(f"\n  Proppant:")
    print(f"    Total: {row['total_proppant_tons']:,.0f} tons")
    print(f"    Per well: {row['avg_proppant_per_well_tons']:,.0f} tons")
    print(f"    Intensity: {row['proppant_intensity_tons_per_m']:.2f} tons/m ⭐")
    print(f"    Import fraction: {row['proppant_import_fraction']*100:.1f}%")
    print(f"\n  Equipment:")
    print(f"    Pressure: {row['avg_max_pressure_psi']:,.0f} psi")
    print(f"    Horsepower: {row['avg_frac_horsepower']:,.0f} hp")
    if pd.notna(row.get('oil_m3_per_proppant_ton')) and row['oil_m3_per_proppant_ton'] > 0:
        print(f"\n  Efficiency: {row['oil_m3_per_proppant_ton']:.3f} m³ oil per ton proppant")

print("\n" + "="*80)
print("✅ TEST OUTPUTS COMPLETE")
print("="*80)
print(f"\nCreated 2 specialized test files:")
print(f"  1. {gas_output_file.name} - {len(gas_fields_output)} gas fields")
print(f"  2. {frac_output_file.name} - {len(frac_fields_output)} fracture fields")
print(f"\nOutput location: {output_dir}")
print()
