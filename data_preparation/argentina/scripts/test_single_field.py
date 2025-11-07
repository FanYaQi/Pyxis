"""
Test Transformation Pipeline for Single Field

Tests the complete transformation pipeline on a single field (AAB)
to verify all transformations are working correctly.

Usage:
    python test_single_field.py
"""

import sys
from pathlib import Path

# Add utils to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
import numpy as np
import json
import importlib.util

# Import well count and geometry functions
spec = importlib.util.spec_from_file_location(
    "well_functions",
    Path(__file__).parent / "00a_add_well_counts_and_geometry.py"
)
well_functions = importlib.util.module_from_spec(spec)
spec.loader.exec_module(well_functions)

load_and_aggregate_well_counts = well_functions.load_and_aggregate_well_counts
load_and_aggregate_well_characteristics = well_functions.load_and_aggregate_well_characteristics
merge_well_counts = well_functions.merge_well_counts
merge_well_characteristics = well_functions.merge_well_characteristics


def test_field_aab():
    """Test pipeline on field AAB."""

    print("="*70)
    print("TESTING FIELD: AAB")
    print("="*70)

    base_dir = Path(__file__).parent.parent
    raw_dir = base_dir / "raw"

    # Load configuration
    config_file = base_dir / "config" / "opgee_calculation_params.json"
    with open(config_file, 'r') as f:
        config = json.load(f)

    year = 2025

    # ========================================================================
    # STEP 1: Load Oil Production for Field AAB
    # ========================================================================

    print("\n" + "="*70)
    print("STEP 1: Loading Oil Production Data for Field AAB")
    print("="*70)

    oil_file = raw_dir / "produccin-de-petrleo-por-yacimiento.csv"

    if not oil_file.exists():
        print(f"❌ File not found: {oil_file}")
        return

    # Read and filter
    oil_df = pd.read_csv(oil_file, encoding='utf-8')
    oil_df = oil_df[(oil_df['anio'] == year) & (oil_df['idareayacimiento'] == 'AAB')].copy()

    if len(oil_df) == 0:
        print("❌ No data found for field AAB in oil production file")
        return

    print(f"✅ Found {len(oil_df)} rows for field AAB in {year}")
    print(f"\nColumns: {list(oil_df.columns)}")

    # Show raw data
    print("\n--- RAW OIL DATA (LONG FORMAT) ---")
    print(oil_df[['idareayacimiento', 'areayacimiento', 'anio', 'mes', 'concepto', 'cantidad']].to_string())

    # Pivot to WIDE
    print("\n--- PIVOTING TO WIDE FORMAT ---")
    oil_wide = oil_df.pivot_table(
        index=['idareayacimiento', 'areayacimiento', 'anio', 'mes',
               'cuenca', 'provincia', 'ubicacion', 'empresa'],
        columns='concepto',
        values='cantidad',
        aggfunc='first'
    ).reset_index()

    print(f"After pivot: {len(oil_wide)} rows × {len(oil_wide.columns)} columns")
    print(f"\nPivoted columns (concepto values):")
    for col in oil_wide.columns[8:]:  # Skip index columns
        print(f"  - {col}")

    # Rename columns
    oil_wide.rename(columns={
        'idareayacimiento': 'field_id',
        'areayacimiento': 'name',
        'anio': 'year',
        'mes': 'month',
        'cuenca': 'basin',
        'provincia': 'province',
        'ubicacion': 'location',
        'empresa': 'company_name',
        'Producción Primaria (m3)': 'primary_prod_m3',
        'Producción Secundaria (m3)': 'secondary_prod_m3',
        'Producción por Recuperación Asistida (m3)': 'assisted_recovery_m3',
        'Producción No Convencional (m3)': 'unconventional_prod_m3',
        'Producción de Agua (m3)': 'water_prod_m3',
        'Inyección de Agua (m3)': 'water_injected_m3',
        'Densidad Media (Ton/m3)': 'density_ton_m3',
    }, inplace=True)

    # Fill NaN production with 0
    for col in ['primary_prod_m3', 'secondary_prod_m3', 'assisted_recovery_m3', 'unconventional_prod_m3']:
        if col in oil_wide.columns:
            oil_wide[col] = oil_wide[col].fillna(0)
        else:
            oil_wide[col] = 0

    # Calculate total oil production
    print("\n--- CALCULATING TOTAL OIL PRODUCTION (Many-to-One) ---")
    print("Formula: oil_prod_m3 = primary + secondary + assisted + unconventional")

    oil_wide['oil_prod_m3'] = (
        oil_wide['primary_prod_m3'] +
        oil_wide['secondary_prod_m3'] +
        oil_wide['assisted_recovery_m3'] +
        oil_wide['unconventional_prod_m3']
    )

    print(f"\nProduction breakdown for field AAB:")
    for month in sorted(oil_wide['month'].unique()):
        row = oil_wide[oil_wide['month'] == month].iloc[0]
        print(f"\nMonth {month}:")
        print(f"  Primary:         {row['primary_prod_m3']:>10.2f} m³")
        print(f"  Secondary:       {row['secondary_prod_m3']:>10.2f} m³")
        print(f"  Assisted:        {row['assisted_recovery_m3']:>10.2f} m³")
        print(f"  Unconventional:  {row['unconventional_prod_m3']:>10.2f} m³")
        print(f"  ─────────────────────────────")
        print(f"  TOTAL:           {row['oil_prod_m3']:>10.2f} m³")

    # ========================================================================
    # STEP 2: Load Gas Production for Field AAB
    # ========================================================================

    print("\n" + "="*70)
    print("STEP 2: Loading Gas Production Data for Field AAB")
    print("="*70)

    gas_file = raw_dir / "produccin-de-gas-por-yacimiento.csv"

    if not gas_file.exists():
        print(f"❌ File not found: {gas_file}")
        gas_wide = None
    else:
        gas_df = pd.read_csv(gas_file, encoding='utf-8')
        gas_df = gas_df[(gas_df['anio'] == year) & (gas_df['idareayacimiento'] == 'AAB')].copy()

        if len(gas_df) == 0:
            print("⚠️  No gas production data found for field AAB")
            print("   → Field AAB is an OIL-ONLY field")
            gas_wide = None
        else:
            print(f"✅ Found {len(gas_df)} rows for field AAB in gas file")

            # Show raw data
            print("\n--- RAW GAS DATA (LONG FORMAT) ---")
            print(gas_df[['idareayacimiento', 'areayacimiento', 'anio', 'mes', 'concepto', 'cantidad']].head(20).to_string())

            # Pivot to WIDE
            gas_wide = gas_df.pivot_table(
                index=['idareayacimiento', 'areayacimiento', 'anio', 'mes',
                       'cuenca', 'provincia', 'ubicacion', 'empresa'],
                columns='concepto',
                values='cantidad',
                aggfunc='first'
            ).reset_index()

            # Rename columns
            gas_wide.rename(columns={
                'idareayacimiento': 'field_id',
                'areayacimiento': 'name',
                'anio': 'year',
                'mes': 'month',
                'Gas de Alta Presión (Mm3)': 'gas_high_pressure_mm3',
                'Gas de Media Presión (Mm3)': 'gas_medium_pressure_mm3',
                'Gas de Baja Presión (Mm3)': 'gas_low_pressure_mm3',
                'Gas No Convencional (Mm3)': 'gas_unconventional_mm3',
                'Inyectado a Formación (Mm3)': 'gas_injected_mm3',
            }, inplace=True)

            # Calculate total gas
            for col in ['gas_high_pressure_mm3', 'gas_medium_pressure_mm3',
                       'gas_low_pressure_mm3', 'gas_unconventional_mm3']:
                if col in gas_wide.columns:
                    gas_wide[col] = gas_wide[col].fillna(0)
                else:
                    gas_wide[col] = 0

            gas_wide['gas_prod_mm3'] = (
                gas_wide['gas_high_pressure_mm3'] +
                gas_wide['gas_medium_pressure_mm3'] +
                gas_wide['gas_low_pressure_mm3'] +
                gas_wide['gas_unconventional_mm3']
            )

    # ========================================================================
    # STEP 3: Merge Oil and Gas
    # ========================================================================

    print("\n" + "="*70)
    print("STEP 3: Merging Oil and Gas Production")
    print("="*70)

    if gas_wide is None or len(gas_wide) == 0:
        print("\n⚠️  No gas data for AAB → Using oil data only")
        combined = oil_wide.copy()
        combined['gas_prod_mm3'] = 0
        combined['gas_injected_mm3'] = 0
        print("   Result: Field AAB classified as OIL FIELD")
    else:
        print("\nMerging oil + gas with OUTER join...")
        gas_cols = ['field_id', 'year', 'month', 'gas_prod_mm3', 'gas_injected_mm3']
        combined = oil_wide.merge(
            gas_wide[gas_cols],
            on=['field_id', 'year', 'month'],
            how='outer'
        )
        print(f"✅ Merged: {len(combined)} rows")

    # Fill NaN
    combined['oil_prod_m3'] = combined['oil_prod_m3'].fillna(0)
    combined['gas_prod_mm3'] = combined['gas_prod_mm3'].fillna(0)
    combined['water_prod_m3'] = combined.get('water_prod_m3', 0).fillna(0)
    combined['water_injected_m3'] = combined.get('water_injected_m3', 0).fillna(0)
    combined['gas_injected_mm3'] = combined.get('gas_injected_mm3', 0).fillna(0)

    # ========================================================================
    # STEP 4: Calculate API Gravity
    # ========================================================================

    print("\n" + "="*70)
    print("STEP 4: Calculating API Gravity (TIME-VARYING!)")
    print("="*70)

    print("\nFormula: API = (141.5 / density_ton_m3) - 131.5")

    if 'density_ton_m3' in combined.columns:
        combined['api'] = combined['density_ton_m3'].apply(
            lambda d: (141.5 / d) - 131.5 if d > 0 else np.nan
        )

        print("\nAPI Gravity by Month:")
        for month in sorted(combined['month'].unique()):
            row = combined[combined['month'] == month].iloc[0]
            density = row.get('density_ton_m3', np.nan)
            api = row.get('api', np.nan)
            print(f"  Month {month:2d}: Density = {density:.4f} ton/m³ → API = {api:.1f}°")
    else:
        print("⚠️  No density data, API = NaN")
        combined['api'] = np.nan

    # ========================================================================
    # STEP 5: Unit Conversions
    # ========================================================================

    print("\n" + "="*70)
    print("STEP 5: Unit Conversions")
    print("="*70)

    M3_TO_BBL = 6.28981
    MM3_TO_M3 = 1000000

    print(f"\n1. Oil: m³ → bbl (×{M3_TO_BBL})")
    combined['oil_prod'] = combined['oil_prod_m3'] * M3_TO_BBL

    print(f"2. Gas: Mm³ → m³ (×{MM3_TO_M3})")
    combined['gas_prod_m3'] = combined['gas_prod_mm3'] * MM3_TO_M3
    combined['gas_prod'] = combined['gas_prod_m3']

    print(f"3. Water: m³ → m³ (no conversion)")
    combined['water_prod'] = combined['water_prod_m3']
    combined['water_injected'] = combined['water_injected_m3']

    print(f"4. Gas injection: Mm³ → m³ (×{MM3_TO_M3})")
    combined['gas_injected_m3'] = combined['gas_injected_mm3'] * MM3_TO_M3
    combined['gas_injected'] = combined['gas_injected_m3']

    print("\nConverted Production Values (Month 1):")
    if len(combined) > 0:
        row = combined.iloc[0]
        print(f"  Oil:   {row['oil_prod_m3']:>12.2f} m³  →  {row['oil_prod']:>12.2f} bbl")
        print(f"  Gas:   {row['gas_prod_mm3']:>12.6f} Mm³ →  {row['gas_prod']:>12.2f} m³")
        print(f"  Water: {row['water_prod']:>12.2f} m³")

    # ========================================================================
    # STEP 6: Functional Unit Classification
    # ========================================================================

    print("\n" + "="*70)
    print("STEP 6: Functional Unit Classification")
    print("="*70)

    gor_threshold = config['functional_unit_classification']['gor_threshold_m3_m3']
    print(f"\nGOR Threshold: {gor_threshold} m³/m³ (10,000 scf/bbl)")

    def classify(row):
        if row['gas_prod'] == 0:
            return 'oil', 0
        elif row['oil_prod'] == 0:
            return 'gas', np.inf
        else:
            gor = row['gas_prod_m3'] / row['oil_prod_m3']
            return ('gas' if gor > gor_threshold else 'oil'), gor

    combined[['functional_unit', 'gor_calc']] = combined.apply(
        lambda row: pd.Series(classify(row)), axis=1
    )

    print("\nClassification Logic:")
    row = combined.iloc[0]
    if row['gas_prod'] == 0:
        print("  gas_prod = 0 → functional_unit = 'oil'")
    elif row['oil_prod'] == 0:
        print("  oil_prod = 0 → functional_unit = 'gas'")
    else:
        print(f"  gas_prod = {row['gas_prod_m3']:.2f} m³")
        print(f"  oil_prod = {row['oil_prod_m3']:.2f} m³")
        print(f"  GOR = {row['gor_calc']:.2f} m³/m³")
        if row['gor_calc'] > gor_threshold:
            print(f"  GOR > {gor_threshold} → functional_unit = 'gas'")
        else:
            print(f"  GOR ≤ {gor_threshold} → functional_unit = 'oil'")

    print(f"\n✅ Field AAB classified as: {combined.iloc[0]['functional_unit'].upper()} FIELD")

    # ========================================================================
    # STEP 7: Calculate Production Ratios
    # ========================================================================

    print("\n" + "="*70)
    print("STEP 7: Calculating Production Ratios")
    print("="*70)

    # GOR
    combined['gor'] = combined['gas_prod_m3'] / combined['oil_prod_m3']
    combined['gor'] = combined['gor'].replace([np.inf, -np.inf], 0)

    # WOR
    combined['wor'] = combined['water_prod'] / combined['oil_prod_m3']
    combined['wor'] = combined['wor'].replace([np.inf, -np.inf], 0)

    # WIR
    combined['wir'] = combined['water_injected'] / combined['oil_prod_m3']
    combined['wir'] = combined['wir'].replace([np.inf, -np.inf], 0)

    # GLIR
    combined['glir'] = combined['gas_injected'] / combined['oil_prod_m3']
    combined['glir'] = combined['glir'].replace([np.inf, -np.inf], 0)

    print("\nProduction Ratios (Month 1):")
    if len(combined) > 0:
        row = combined.iloc[0]
        print(f"  GOR (Gas-to-Oil):           {row['gor']:>10.2f} m³/m³")
        print(f"  WOR (Water-to-Oil):         {row['wor']:>10.2f} m³/m³")
        print(f"  WIR (Water Injection):      {row['wir']:>10.2f} m³/m³")
        print(f"  GLIR (Gas Lift Injection):  {row['glir']:>10.2f} m³/m³")

    # ========================================================================
    # STEP 8: Detect EOR Methods
    # ========================================================================

    print("\n" + "="*70)
    print("STEP 8: Detecting EOR Methods (One-to-Many)")
    print("="*70)

    combined['water_flooding'] = (
        (combined.get('secondary_prod_m3', 0) > 0) &
        (combined['water_injected'] > 0)
    ).astype(int)

    combined['natural_gas_reinjection'] = (
        (combined.get('secondary_prod_m3', 0) > 0) &
        (combined['gas_injected'] > 0)
    ).astype(int)

    combined['steam_flooding'] = (
        (combined.get('assisted_recovery_m3', 0) > 0) &
        (combined['wir'] > 5.0)
    ).astype(int)

    combined['gas_flooding'] = (
        (combined.get('assisted_recovery_m3', 0) > 0) &
        (combined['gas_injected'] > 0)
    ).astype(int)

    print("\nEOR Methods Detected:")
    row = combined.iloc[0]
    print(f"  Water Flooding:            {row['water_flooding']} (secondary + water inj)")
    print(f"  Natural Gas Reinjection:   {row['natural_gas_reinjection']} (secondary + gas inj)")
    print(f"  Steam Flooding:            {row['steam_flooding']} (assisted + WIR>5)")
    print(f"  Gas Flooding:              {row['gas_flooding']} (assisted + gas inj)")

    # ========================================================================
    # STEP 8a: Load and Merge Well Counts
    # ========================================================================

    print("\n" + "="*70)
    print("STEP 8a: Loading and Aggregating Well Counts")
    print("="*70)

    well_prod_file = raw_dir / "produccin-de-pozos-de-gas-y-petrleo-2025.csv"

    if well_prod_file.exists():
        well_counts = load_and_aggregate_well_counts(well_prod_file, year)
        if well_counts is not None:
            # Filter to field AAB
            well_counts_aab = well_counts[well_counts['field_id'] == 'AAB']

            if len(well_counts_aab) > 0:
                print(f"\n✅ Found well count data for field AAB")
                print(f"   Months with data: {len(well_counts_aab)}")

                # Merge with combined data
                combined = merge_well_counts(combined, well_counts)

                # Show well count statistics
                if len(combined) > 0:
                    row = combined.iloc[0]
                    print(f"\nWell Counts (Month 1):")
                    if 'num_prod_wells' in combined.columns:
                        print(f"  Producing wells:       {row.get('num_prod_wells', 0)}")
                        print(f"  Water injection wells: {row.get('num_water_inj_wells', 0)}")
                        print(f"  Gas injection wells:   {row.get('num_gas_inj_wells', 0)}")
                        print(f"  Downhole pump:         {row.get('downhole_pump', 0)} (binary flag)")
                        print(f"  Gas lifting:           {row.get('gas_lifting', 0)} (binary flag)")
            else:
                print(f"\n⚠️  No well count data for field AAB")
    else:
        print(f"\n⚠️  Well production file not found: {well_prod_file}")

    # ========================================================================
    # STEP 8b: Load and Merge Well Characteristics
    # ========================================================================

    print("\n" + "="*70)
    print("STEP 8b: Loading and Aggregating Well Characteristics")
    print("="*70)

    well_chars_file = raw_dir / "capitulo-iv-pozos.csv"

    if well_chars_file.exists():
        well_chars = load_and_aggregate_well_characteristics(well_chars_file)
        if well_chars is not None:
            # Filter to field AAB
            well_chars_aab = well_chars[well_chars['field_id'] == 'AAB']

            if len(well_chars_aab) > 0:
                print(f"\n✅ Found well characteristics for field AAB")
                print(f"   Average depth: {well_chars_aab.iloc[0].get('depth_avg', 'N/A')} m")

                # Merge with combined data
                combined = merge_well_characteristics(combined, well_chars)
            else:
                print(f"\n⚠️  No well characteristics for field AAB")
    else:
        print(f"\n⚠️  Well characteristics file not found: {well_chars_file}")

    # ========================================================================
    # STEP 9: Final Result
    # ========================================================================

    print("\n" + "="*70)
    print("FINAL RESULT FOR FIELD AAB")
    print("="*70)

    # Select key columns
    output_cols = [
        'field_id', 'name', 'year', 'month', 'basin', 'province',
        'functional_unit', 'oil_prod', 'gas_prod', 'water_prod',
        'api', 'gor', 'wor', 'wir', 'glir',
        'water_flooding', 'natural_gas_reinjection',
        'num_prod_wells', 'num_water_inj_wells', 'num_gas_inj_wells',
        'downhole_pump', 'gas_lifting', 'depth'
    ]

    available_cols = [col for col in output_cols if col in combined.columns]
    result = combined[available_cols].copy()

    print(f"\n{result.to_string()}")

    # Save to file
    output_file = base_dir / "output" / "test_field_AAB_result.csv"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_file, index=False)
    print(f"\n✅ Results saved to: {output_file}")

    print("\n" + "="*70)
    print("TEST COMPLETE")
    print("="*70)


if __name__ == "__main__":
    test_field_aab()
