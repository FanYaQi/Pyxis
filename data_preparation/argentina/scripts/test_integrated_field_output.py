"""
Integrated Field Output - Merge Fracture Data into Field Production

Combines field production data with fracture/completion metrics into single field-level output.
Focus on numerical metrics only - excludes descriptive text fields.

Output columns per field:
- Production: oil_prod_m3, gas_prod_mm3, water_prod_m3, gor, well_count
- Geometry: latitude, longitude, depth_avg_m, field_area_km2
- Fracture: proppant_tons, co2_m3, horsepower, pressure_psi, stages, lateral_m
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
print("INTEGRATED FIELD OUTPUT - Merging Fracture Data with Field Production")
print("="*80)

# ============================================================================
# 1. LOAD AND AGGREGATE PRODUCTION DATA
# ============================================================================

print("\n1. Loading production data...")

# Oil production
oil_prod = pd.read_csv(translated_dir / "oil_field_production_english.csv")

# Get total oil production by field (recent 2 years)
oil_by_field = oil_prod[
    (oil_prod['year'] >= 2023)
].groupby('field_name').agg({
    'quantity': 'sum'
}).rename(columns={'quantity': 'total_oil_prod_m3'})

print(f"   Oil production: {len(oil_by_field)} fields")

# Get oil production by concept (to calculate unconventional fraction)
oil_by_concept = oil_prod[
    (oil_prod['year'] >= 2023)
].pivot_table(
    values='quantity',
    index='field_name',
    columns='concept',
    aggfunc='sum',
    fill_value=0
)

# Calculate unconventional fraction
if 'unconventional_production_m3' in oil_by_concept.columns:
    oil_by_field['unconventional_oil_m3'] = oil_by_concept['unconventional_production_m3']
    oil_by_field['unconventional_fraction'] = (
        oil_by_concept['unconventional_production_m3'] /
        oil_by_concept.sum(axis=1)
    ).fillna(0)

# Get water production
if 'water_production_m3' in oil_by_concept.columns:
    oil_by_field['water_prod_m3'] = oil_by_concept['water_production_m3']

# Gas production
gas_prod = pd.read_csv(translated_dir / "gas_field_production_english.csv")

# Get total gas production by field
gas_by_field = gas_prod[
    (gas_prod['year'] >= 2023)
].groupby('field_name').agg({
    'quantity': 'sum'
}).rename(columns={'quantity': 'total_gas_prod_mm3'})

print(f"   Gas production: {len(gas_by_field)} fields")

# Merge oil and gas
production_data = oil_by_field.merge(
    gas_by_field,
    left_index=True,
    right_index=True,
    how='outer'
).fillna(0)

# Calculate GOR (Gas-Oil Ratio) - Mm3 gas per m3 oil
# Note: Need to convert units appropriately
production_data['gor'] = (
    production_data['total_gas_prod_mm3'] * 1000 /  # Convert Mm3 to m3
    production_data['total_oil_prod_m3'].replace(0, np.nan)
).fillna(0)

# Calculate water cut
if 'water_prod_m3' in production_data.columns:
    total_liquid = production_data['total_oil_prod_m3'] + production_data['water_prod_m3']
    production_data['water_cut_fraction'] = (
        production_data['water_prod_m3'] / total_liquid.replace(0, np.nan)
    ).fillna(0)

print(f"   Combined production data: {len(production_data)} fields")

# ============================================================================
# 2. GET ACTIVE WELL COUNT
# ============================================================================

print("\n2. Loading well data...")

well_prod = pd.read_csv(translated_dir / "well_production_2025_english.csv")

# Count active wells by field (wells with production or status = producing)
active_wells = well_prod[
    (well_prod['well_status'] == 'producing') |
    (well_prod['oil_production_m3'] > 0) |
    (well_prod['gas_production_km3'] > 0)
].groupby('field_name')['well_id'].nunique().rename('active_well_count')

production_data = production_data.merge(
    active_wells,
    left_index=True,
    right_index=True,
    how='left'
).fillna({'active_well_count': 0})

print(f"   Active wells added for {len(active_wells)} fields")

# ============================================================================
# 3. LOAD AND PROCESS GEOMETRY/DEPTH DATA
# ============================================================================

print("\n3. Loading field shapes and depth data...")

field_shapes = pd.read_csv(translated_dir / "field_shapes_depth_english.csv")

# Extract numerical geometry metrics
geometry_data = field_shapes[['field_name', 'depth_avg_m', 'depth_min_m', 'depth_max_m']].copy()

# Calculate depth range
geometry_data['depth_range_m'] = geometry_data['depth_max_m'] - geometry_data['depth_min_m']

# Extract centroid from GeoJSON (simple calculation without shapely)
print("   Extracting centroids from GeoJSON...")

centroids = []

for idx, row in field_shapes.iterrows():
    try:
        geom_dict = json.loads(row['field_boundary_geojson'])

        # Extract coordinates from MultiPolygon
        all_coords = []
        if geom_dict['type'] == 'MultiPolygon':
            for polygon in geom_dict['coordinates']:
                # polygon[0] is the outer ring
                all_coords.extend(polygon[0])
        elif geom_dict['type'] == 'Polygon':
            all_coords.extend(geom_dict['coordinates'][0])

        # Calculate simple centroid (average of all coordinates)
        if all_coords:
            lons = [coord[0] for coord in all_coords]
            lats = [coord[1] for coord in all_coords]
            centroid_lon = sum(lons) / len(lons)
            centroid_lat = sum(lats) / len(lats)

            centroids.append({'field_name': row['field_name'],
                             'centroid_longitude': centroid_lon,
                             'centroid_latitude': centroid_lat})
        else:
            centroids.append({'field_name': row['field_name'],
                             'centroid_longitude': np.nan,
                             'centroid_latitude': np.nan})

    except Exception as e:
        centroids.append({'field_name': row['field_name'],
                         'centroid_longitude': np.nan,
                         'centroid_latitude': np.nan})

centroid_df = pd.DataFrame(centroids)

# Merge geometry data
geometry_data = geometry_data.merge(centroid_df, on='field_name', how='left')
geometry_data = geometry_data.set_index('field_name')

print(f"   Geometry data processed for {len(geometry_data)} fields")

# ============================================================================
# 4. LOAD AND AGGREGATE FRACTURE DATA
# ============================================================================

print("\n4. Loading and aggregating fracture data...")

fracture_df = pd.read_csv(translated_dir / "fracture_completion_data_english.csv")

# Calculate total proppant
fracture_df['total_proppant_tons'] = (
    fracture_df['proppant_domestic_tons'] +
    fracture_df['proppant_imported_tons']
)

# Aggregate by field - focus on numerical metrics
fracture_by_field = fracture_df.groupby('field_name').agg({
    'fracture_job_id': 'count',  # Number of fracture jobs
    'well_id': 'nunique',  # Number of unique wells fractured

    # Proppant metrics (totals and averages)
    'total_proppant_tons': ['sum', 'mean'],
    'proppant_domestic_tons': 'sum',
    'proppant_imported_tons': 'sum',

    # Fluid metrics
    'frac_fluid_water_m3': ['sum', 'mean'],
    'frac_fluid_co2_m3': ['sum', 'mean'],

    # Design metrics
    'horizontal_lateral_length_m': 'mean',
    'fracture_stages_count': 'mean',

    # Equipment metrics
    'max_treatment_pressure_psi': 'mean',
    'frac_equipment_total_horsepower': 'mean',
}).round(2)

# Flatten column names
fracture_by_field.columns = [
    'fracture_job_count',
    'fractured_well_count',
    'total_proppant_tons_sum',
    'avg_proppant_tons_per_well',
    'total_proppant_domestic_tons',
    'total_proppant_imported_tons',
    'total_frac_water_m3',
    'avg_frac_water_m3_per_well',
    'total_co2_m3',
    'avg_co2_m3_per_well',
    'avg_lateral_length_m',
    'avg_fracture_stages',
    'avg_max_pressure_psi',
    'avg_frac_horsepower'
]

# Calculate additional metrics
fracture_by_field['proppant_intensity_tons_per_m'] = (
    fracture_by_field['avg_proppant_tons_per_well'] /
    fracture_by_field['avg_lateral_length_m']
).round(3)

fracture_by_field['stage_spacing_m'] = (
    fracture_by_field['avg_lateral_length_m'] /
    fracture_by_field['avg_fracture_stages']
).round(1)

print(f"   Fracture data aggregated for {len(fracture_by_field)} fields")

# ============================================================================
# 5. MERGE ALL DATA SOURCES
# ============================================================================

print("\n5. Merging all data sources into integrated field output...")

# Start with production data
integrated = production_data.copy()

# Merge geometry
integrated = integrated.merge(geometry_data, left_index=True, right_index=True, how='left')

# Merge fracture data
integrated = integrated.merge(fracture_by_field, left_index=True, right_index=True, how='left')

# Reset index to make field_name a column
integrated = integrated.reset_index().rename(columns={'index': 'field_name'})

# Reorder columns - most important metrics first
column_order = [
    'field_name',

    # Production metrics
    'total_oil_prod_m3',
    'total_gas_prod_mm3',
    'water_prod_m3',
    'gor',
    'water_cut_fraction',
    'unconventional_oil_m3',
    'unconventional_fraction',

    # Well counts
    'active_well_count',
    'fractured_well_count',
    'fracture_job_count',

    # Geometry
    'centroid_latitude',
    'centroid_longitude',
    'depth_avg_m',
    'depth_min_m',
    'depth_max_m',
    'depth_range_m',

    # Fracture - Proppant
    'total_proppant_tons_sum',
    'avg_proppant_tons_per_well',
    'proppant_intensity_tons_per_m',
    'total_proppant_domestic_tons',
    'total_proppant_imported_tons',

    # Fracture - Fluids
    'total_frac_water_m3',
    'avg_frac_water_m3_per_well',
    'total_co2_m3',
    'avg_co2_m3_per_well',

    # Fracture - Design
    'avg_lateral_length_m',
    'avg_fracture_stages',
    'stage_spacing_m',
    'avg_max_pressure_psi',
    'avg_frac_horsepower',
]

# Only keep columns that exist
existing_columns = [col for col in column_order if col in integrated.columns]
integrated = integrated[existing_columns]

print(f"\n✅ Integrated dataset created:")
print(f"   Fields: {len(integrated):,}")
print(f"   Metrics: {len(integrated.columns)}")

# ============================================================================
# 6. SELECT TEST FIELDS WITH GOOD DATA
# ============================================================================

print("\n6. Selecting test fields with complete data...")

# Filter for fields with:
# - Oil production
# - Fracture data
# - Geometry data
test_fields = integrated[
    (integrated['total_oil_prod_m3'] > 0) &
    (integrated['fractured_well_count'].notna()) &
    (integrated['fractured_well_count'] > 10) &  # At least 10 fractured wells
    (integrated['depth_avg_m'].notna())
].sort_values('total_oil_prod_m3', ascending=False).head(10)

print(f"   Selected {len(test_fields)} test fields with complete data")

# ============================================================================
# 7. DISPLAY TEST FIELDS
# ============================================================================

print("\n" + "="*80)
print("INTEGRATED FIELD DATA - TEST FIELDS")
print("="*80)

for idx, row in test_fields.iterrows():
    print(f"\n{'─'*80}")
    print(f"FIELD: {row['field_name']}")
    print(f"{'─'*80}")

    print("\n📊 PRODUCTION (2023+):")
    print(f"  Oil production:                    {row['total_oil_prod_m3']:,.0f} m³")
    print(f"  Gas production:                    {row['total_gas_prod_mm3']:,.1f} Mm³")
    if row.get('water_prod_m3', 0) > 0:
        print(f"  Water production:                  {row['water_prod_m3']:,.0f} m³")
    print(f"  GOR (gas-oil ratio):               {row['gor']:.2f} (m³ gas/m³ oil)")
    if 'water_cut_fraction' in row and row['water_cut_fraction'] > 0:
        print(f"  Water cut:                         {row['water_cut_fraction']*100:.1f}%")
    if 'unconventional_fraction' in row and row['unconventional_fraction'] > 0:
        print(f"  Unconventional fraction:           {row['unconventional_fraction']*100:.0f}%")

    print("\n🔢 WELL COUNT:")
    print(f"  Active wells:                      {row['active_well_count']:.0f}")
    print(f"  Fractured wells:                   {row['fractured_well_count']:.0f}")
    print(f"  Fracture jobs:                     {row['fracture_job_count']:.0f}")

    print("\n📍 GEOMETRY:")
    print(f"  Latitude:                          {row['centroid_latitude']:.4f}°")
    print(f"  Longitude:                         {row['centroid_longitude']:.4f}°")
    print(f"  Average depth:                     {row['depth_avg_m']:.0f} m")
    print(f"  Depth range:                       {row['depth_min_m']:.0f} - {row['depth_max_m']:.0f} m")

    print("\n🪨 FRACTURE - PROPPANT:")
    print(f"  Total proppant used (all wells):   {row['total_proppant_tons_sum']:,.0f} tons")
    print(f"  Avg proppant per well:             {row['avg_proppant_tons_per_well']:,.0f} tons")
    print(f"  Proppant intensity:                {row['proppant_intensity_tons_per_m']:.2f} tons/m")
    print(f"  Proppant onsite (domestic):        {row['total_proppant_domestic_tons']:,.0f} tons")
    print(f"  Proppant imported:                 {row['total_proppant_imported_tons']:,.0f} tons")

    print("\n💧 FRACTURE - FLUIDS:")
    print(f"  Total water used (all wells):      {row['total_frac_water_m3']:,.0f} m³")
    print(f"  Avg water per well:                {row['avg_frac_water_m3_per_well']:,.0f} m³")
    if row['total_co2_m3'] > 0:
        print(f"  Total CO2 used:                    {row['total_co2_m3']:,.0f} m³")
        print(f"  Avg CO2 per well:                  {row['avg_co2_m3_per_well']:,.0f} m³")
    else:
        print(f"  CO2 usage:                         None (water-based fracs)")

    print("\n⚙️  FRACTURE - EQUIPMENT & DESIGN:")
    print(f"  Avg lateral length:                {row['avg_lateral_length_m']:,.0f} m")
    print(f"  Avg fracture stages:               {row['avg_fracture_stages']:.1f}")
    print(f"  Stage spacing:                     {row['stage_spacing_m']:.1f} m")
    print(f"  Avg max pressure:                  {row['avg_max_pressure_psi']:,.0f} psi")
    print(f"  Avg fracture horsepower:           {row['avg_frac_horsepower']:,.0f} hp")

# ============================================================================
# 8. SAVE INTEGRATED OUTPUT
# ============================================================================

print("\n" + "="*80)
print("SAVING INTEGRATED OUTPUT")
print("="*80)

# Save full integrated dataset
full_output = output_dir / "integrated_field_data_with_fracture.csv"
integrated.to_csv(full_output, index=False)
print(f"\n✅ Full dataset saved: {full_output.name}")
print(f"   Fields: {len(integrated):,}")
print(f"   Columns: {len(integrated.columns)}")

# Save test fields
test_output = output_dir / "TEST_integrated_fields.csv"
test_fields.to_csv(test_output, index=False)
print(f"\n✅ Test fields saved: {test_output.name}")
print(f"   Fields: {len(test_fields)}")

print("\n" + "="*80)
print("✅ INTEGRATED FIELD OUTPUT COMPLETE")
print("="*80)
print(f"\nOutput location: {output_dir}")
print()
