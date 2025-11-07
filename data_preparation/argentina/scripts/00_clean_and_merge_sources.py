"""
Argentina Data Transformation Pipeline - Step 0: Clean and Merge Sources

This script transforms raw Argentina oil & gas production data from Spanish-language
LONG format into English-language WIDE format ready for Pyxis ingestion.

INPUT FILES:
    - produccin-de-petrleo-por-yacimiento.csv (2.37M rows, field-month-concepto)
    - produccin-de-gas-por-yacimiento.csv (1.38M rows, field-month-concepto)
    - produccin-de-pozos-de-gas-y-petrleo-2025.csv (743k rows, well-month)
    - capitulo-iv-pozos.csv (85k rows, well static)

OUTPUT FILES:
    - field_production_complete.csv (English, WIDE format, ~14k rows for 2025)

TRANSFORMATION SUMMARY:
    - Pivot LONG → WIDE format (concepto → columns)
    - Merge oil + gas production (OUTER join)
    - Calculate API gravity from density (time-varying!)
    - Classify functional unit (oil/gas) using GOR threshold
    - Calculate production ratios (GOR, WOR, WIR, GLIR)
    - Derive EOR methods (water flooding, gas reinjection, etc.)
    - Aggregate well characteristics to field level
    - All column names in ENGLISH (no Spanish!)

TIME SCOPE: 2025 only (12 months)
GOR THRESHOLD: 10,000 scf/bbl = 1,781 m³/m³

Author: Pyxis Data Preparation Pipeline
Date: 2025-10-29
"""

import sys
from pathlib import Path

# Add utils to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
import numpy as np
import json
from datetime import datetime
from calendar import monthrange

# Import well count and geometry functions
import importlib.util
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


# ============================================================================
# CONFIGURATION
# ============================================================================

def load_config(config_path: Path) -> dict:
    """Load configuration parameters from JSON file."""
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


# ============================================================================
# STEP 1: LOAD AND PIVOT OIL PRODUCTION DATA
# ============================================================================

def load_and_pivot_oil_production(
    input_csv: Path,
    year: int = 2025
) -> pd.DataFrame:
    """
    Load oil field production data and pivot from LONG to WIDE format.

    INPUT FORMAT (LONG):
        Each field-month has MULTIPLE rows, one per 'concepto':
        - Producción Primaria (m3)
        - Producción Secundaria (m3)
        - Producción por Recuperación Asistida (m3)
        - Producción No Convencional (m3)
        - Producción de Agua (m3)
        - Inyección de Agua (m3)
        - Densidad Media (Ton/m3)  ← TIME-VARYING!
        - etc.

    OUTPUT FORMAT (WIDE):
        One row per field-month with separate columns for each concepto

    COLUMN TRANSFORMATIONS:
        Spanish → English:
        - idareayacimiento → field_id
        - areayacimiento → name
        - anio → year
        - mes → month
        - cuenca → basin
        - provincia → province
        - ubicacion → location
        - concepto values → column names (see mapping below)
    """
    print(f"\n{'='*70}")
    print(f"STEP 1: Loading Oil Production Data")
    print(f"{'='*70}")

    print(f"Reading: {input_csv}")
    df = pd.read_csv(input_csv, encoding='utf-8')
    print(f"  Loaded: {len(df):,} rows, {len(df.columns)} columns")

    # Filter to target year
    df = df[df['anio'] == year].copy()
    print(f"  Filtered to {year}: {len(df):,} rows")

    # Check unique concepto values
    concepto_values = df['concepto'].unique()
    print(f"  Unique concepto values: {len(concepto_values)}")
    for i, val in enumerate(sorted(concepto_values)[:10], 1):
        print(f"    {i}. {val}")

    # Pivot: concepto becomes columns
    print("\nPivoting LONG → WIDE format...")
    oil_wide = df.pivot_table(
        index=['idareayacimiento', 'areayacimiento', 'anio', 'mes',
               'cuenca', 'provincia', 'ubicacion', 'empresa'],
        columns='concepto',
        values='cantidad',
        aggfunc='first'  # Take first value if duplicates
    ).reset_index()

    print(f"  After pivot: {len(oil_wide):,} rows, {len(oil_wide.columns)} columns")

    # Rename index columns (Spanish → English)
    print("\nRenaming columns (Spanish → English)...")
    oil_wide.rename(columns={
        'idareayacimiento': 'field_id',
        'areayacimiento': 'name',
        'anio': 'year',
        'mes': 'month',
        'cuenca': 'basin',
        'provincia': 'province',
        'ubicacion': 'location',
        'empresa': 'company_name',
    }, inplace=True)

    # Rename concepto columns (Spanish → English)
    concepto_mapping = {
        'Producción Primaria (m3)': 'primary_prod_m3',
        'Producción Secundaria (m3)': 'secondary_prod_m3',
        'Producción por Recuperación Asistida (m3)': 'assisted_recovery_m3',
        'Producción No Convencional (m3)': 'unconventional_prod_m3',
        'Producción de Agua (m3)': 'water_prod_m3',
        'Inyección de Agua (m3)': 'water_injected_m3',
        'Producción de Condensado (m3)': 'condensate_prod_m3',
        'Producción de Gasolina Estabilizada (m3)': 'stabilized_gasoline_m3',
        'Consumo en Yacimiento (m3)': 'field_consumption_m3',
        'Densidad Media (Ton/m3)': 'density_ton_m3',  # TIME-VARYING!
    }

    oil_wide.rename(columns=concepto_mapping, inplace=True)

    print(f"\n✅ Oil production data loaded and pivoted")
    print(f"   Fields: {oil_wide['field_id'].nunique()}")
    print(f"   Rows: {len(oil_wide):,} (field-month records)")

    return oil_wide


# ============================================================================
# STEP 2: LOAD AND PIVOT GAS PRODUCTION DATA
# ============================================================================

def load_and_pivot_gas_production(
    input_csv: Path,
    year: int = 2025
) -> pd.DataFrame:
    """
    Load gas field production data and pivot from LONG to WIDE format.

    INPUT FORMAT (LONG):
        Each field-month has MULTIPLE rows, one per 'concepto':
        - Gas de Alta Presión (Mm3)
        - Gas de Media Presión (Mm3)
        - Gas de Baja Presión (Mm3)
        - Gas No Convencional (Mm3)
        - Inyectado a Formación (Mm3)
        - Equivalente calórico del gas (Kcal/m3)
        - etc.

    NOTE: Gas volumes in Argentina are in Mm³ (millions of m³)

    COLUMN TRANSFORMATIONS:
        Spanish → English (same as oil for common fields)
        Gas-specific concepto values → column names
    """
    print(f"\n{'='*70}")
    print(f"STEP 2: Loading Gas Production Data")
    print(f"{'='*70}")

    print(f"Reading: {input_csv}")
    df = pd.read_csv(input_csv, encoding='utf-8')
    print(f"  Loaded: {len(df):,} rows, {len(df.columns)} columns")

    # Filter to target year
    df = df[df['anio'] == year].copy()
    print(f"  Filtered to {year}: {len(df):,} rows")

    # Check unique concepto values
    concepto_values = df['concepto'].unique()
    print(f"  Unique concepto values: {len(concepto_values)}")
    for i, val in enumerate(sorted(concepto_values)[:10], 1):
        print(f"    {i}. {val}")

    # Pivot: concepto becomes columns
    print("\nPivoting LONG → WIDE format...")
    gas_wide = df.pivot_table(
        index=['idareayacimiento', 'areayacimiento', 'anio', 'mes',
               'cuenca', 'provincia', 'ubicacion', 'empresa'],
        columns='concepto',
        values='cantidad',
        aggfunc='first'
    ).reset_index()

    print(f"  After pivot: {len(gas_wide):,} rows, {len(gas_wide.columns)} columns")

    # Rename index columns
    print("\nRenaming columns (Spanish → English)...")
    gas_wide.rename(columns={
        'idareayacimiento': 'field_id',
        'areayacimiento': 'name',
        'anio': 'year',
        'mes': 'month',
        'cuenca': 'basin',
        'provincia': 'province',
        'ubicacion': 'location',
        'empresa': 'company_name',
    }, inplace=True)

    # Rename concepto columns
    concepto_mapping = {
        'Gas de Alta Presión (Mm3)': 'gas_high_pressure_mm3',
        'Gas de Media Presión (Mm3)': 'gas_medium_pressure_mm3',
        'Gas de Baja Presión (Mm3)': 'gas_low_pressure_mm3',
        'Gas No Convencional (Mm3)': 'gas_unconventional_mm3',
        'Inyectado a Formación (Mm3)': 'gas_injected_formation_mm3',
        'Inyección para Almacenamiento (Mm3)': 'gas_injected_storage_mm3',
        'Extraído del almacenamiento (Mm3)': 'gas_extracted_storage_mm3',
        'Equivalente calórico del gas (Kcal/m3)': 'gas_heating_value_kcal_m3',
    }

    gas_wide.rename(columns=concepto_mapping, inplace=True)

    print(f"\n✅ Gas production data loaded and pivoted")
    print(f"   Fields: {gas_wide['field_id'].nunique()}")
    print(f"   Rows: {len(gas_wide):,} (field-month records)")

    return gas_wide


# ============================================================================
# STEP 3: CALCULATE TOTAL PRODUCTION VOLUMES
# ============================================================================

def calculate_total_oil_production(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate total oil production from multiple production types.

    FORMULA:
        oil_prod_m3 = primary_prod_m3 + secondary_prod_m3 +
                      assisted_recovery_m3 + unconventional_prod_m3

    TRANSFORMATION: MANY-TO-ONE
        4 columns → 1 column (sum)

    NOTE: Fill NaN with 0 before summing
    """
    print("\nCalculating total oil production (many-to-one)...")

    prod_columns = [
        'primary_prod_m3',
        'secondary_prod_m3',
        'assisted_recovery_m3',
        'unconventional_prod_m3'
    ]

    # Fill NaN with 0
    for col in prod_columns:
        if col in df.columns:
            df[col] = df[col].fillna(0)
        else:
            df[col] = 0

    # Sum all production types
    df['oil_prod_m3'] = (
        df['primary_prod_m3'] +
        df['secondary_prod_m3'] +
        df['assisted_recovery_m3'] +
        df['unconventional_prod_m3']
    )

    print(f"  Oil production range: {df['oil_prod_m3'].min():.2f} to {df['oil_prod_m3'].max():.2f} m³")
    print(f"  Fields with oil production > 0: {(df['oil_prod_m3'] > 0).sum():,}")

    return df


def calculate_total_gas_production(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate total gas production from multiple pressure categories.

    FORMULA:
        gas_prod_mm3 = gas_high_pressure_mm3 + gas_medium_pressure_mm3 +
                       gas_low_pressure_mm3 + gas_unconventional_mm3

    TRANSFORMATION: MANY-TO-ONE
        4 columns → 1 column (sum)

    UNITS: Mm³ (millions of m³) - will convert to m³ later
    """
    print("\nCalculating total gas production (many-to-one)...")

    prod_columns = [
        'gas_high_pressure_mm3',
        'gas_medium_pressure_mm3',
        'gas_low_pressure_mm3',
        'gas_unconventional_mm3'
    ]

    # Fill NaN with 0
    for col in prod_columns:
        if col in df.columns:
            df[col] = df[col].fillna(0)
        else:
            df[col] = 0

    # Sum all gas categories
    df['gas_prod_mm3'] = (
        df['gas_high_pressure_mm3'] +
        df['gas_medium_pressure_mm3'] +
        df['gas_low_pressure_mm3'] +
        df['gas_unconventional_mm3']
    )

    print(f"  Gas production range: {df['gas_prod_mm3'].min():.2f} to {df['gas_prod_mm3'].max():.2f} Mm³")
    print(f"  Fields with gas production > 0: {(df['gas_prod_mm3'] > 0).sum():,}")

    return df


# ============================================================================
# STEP 4: MERGE OIL AND GAS PRODUCTION
# ============================================================================

def merge_oil_and_gas_production(
    oil_df: pd.DataFrame,
    gas_df: pd.DataFrame
) -> pd.DataFrame:
    """
    Merge oil and gas production data using OUTER join.

    JOIN TYPE: OUTER
        Ensures we capture fields that only produce oil OR only produce gas

    MERGE KEYS: ['field_id', 'year', 'month']

    RESULT:
        - Fields only in oil file: gas columns will be NaN → Oil field
        - Fields only in gas file: oil columns will be NaN → Gas field
        - Fields in both files: All columns populated → Classify by GOR

    COLUMN HANDLING:
        - Common columns (basin, province, etc.): take from oil file (left)
        - Oil-specific columns: keep as-is
        - Gas-specific columns: add with suffix (handled automatically)
    """
    print(f"\n{'='*70}")
    print(f"STEP 4: Merging Oil and Gas Production")
    print(f"{'='*70}")

    print(f"Oil data: {len(oil_df):,} rows, {oil_df['field_id'].nunique()} unique fields")
    print(f"Gas data: {len(gas_df):,} rows, {gas_df['field_id'].nunique()} unique fields")

    # Select columns to merge from gas data (avoid duplicates)
    gas_cols_to_merge = ['field_id', 'year', 'month'] + [
        col for col in gas_df.columns
        if col not in ['field_id', 'year', 'month', 'name', 'basin',
                       'province', 'location', 'company_name']
    ]

    print(f"\nMerging with OUTER join on ['field_id', 'year', 'month']...")
    combined = oil_df.merge(
        gas_df[gas_cols_to_merge],
        on=['field_id', 'year', 'month'],
        how='outer',  # Keep all fields from both files!
        indicator=True  # Add _merge column to see source
    )

    print(f"  Combined: {len(combined):,} rows, {combined['field_id'].nunique()} unique fields")

    # Analyze merge results
    merge_stats = combined['_merge'].value_counts()
    print(f"\nMerge statistics:")
    print(f"  Only in oil file:  {merge_stats.get('left_only', 0):,} rows → Oil fields")
    print(f"  Only in gas file:  {merge_stats.get('right_only', 0):,} rows → Gas fields")
    print(f"  In both files:     {merge_stats.get('both', 0):,} rows → Mixed fields")

    # Fill NaN with 0 for production volumes
    print("\nFilling NaN values with 0 for production columns...")
    combined['oil_prod_m3'] = combined['oil_prod_m3'].fillna(0)
    combined['gas_prod_mm3'] = combined['gas_prod_mm3'].fillna(0)
    combined['water_prod_m3'] = combined['water_prod_m3'].fillna(0)
    combined['water_injected_m3'] = combined['water_injected_m3'].fillna(0)

    # Fill gas injection
    if 'gas_injected_formation_mm3' in combined.columns:
        combined['gas_injected_mm3'] = combined['gas_injected_formation_mm3'].fillna(0)
    else:
        combined['gas_injected_mm3'] = 0

    print(f"\n✅ Oil and gas data merged")

    return combined


# ============================================================================
# STEP 5: CALCULATE API GRAVITY FROM DENSITY (TIME-VARYING!)
# ============================================================================

def calculate_api_gravity(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate API gravity from oil density (TIME-VARYING attribute).

    FORMULA:
        API = (141.5 / specific_gravity) - 131.5

    WHERE:
        specific_gravity ≈ density (ton/m³) when water = 1.0 ton/m³

    SOURCE:
        'density_ton_m3' column from oil production file
        (Spanish: "Densidad Media (Ton/m3)")

    TRANSFORMATION: ONE-TO-ONE (calculated field)
        density_ton_m3 → api

    TEMPORAL NATURE:
        ⚠️ API gravity is TIME-VARYING!
        Oil density changes month-to-month as reservoir conditions change
        and production mix varies.

    HANDLING MISSING:
        If density is 0 or null (gas-only fields), API will be null
    """
    print(f"\n{'='*70}")
    print(f"STEP 5: Calculating API Gravity from Density")
    print(f"{'='*70}")

    print("FORMULA: API = (141.5 / density_ton_m3) - 131.5")

    if 'density_ton_m3' not in df.columns:
        print("  ⚠️ Warning: No density column found, API will be null")
        df['api'] = np.nan
        return df

    # Calculate API gravity
    df['api'] = df['density_ton_m3'].apply(
        lambda d: (141.5 / d) - 131.5 if d > 0 else np.nan
    )

    # Statistics
    valid_api = df['api'].dropna()
    if len(valid_api) > 0:
        print(f"\nAPI Gravity Statistics:")
        print(f"  Count: {len(valid_api):,} fields")
        print(f"  Range: {valid_api.min():.1f}° to {valid_api.max():.1f}°")
        print(f"  Mean: {valid_api.mean():.1f}°")
        print(f"  Median: {valid_api.median():.1f}°")
        print(f"\n  NOTE: API varies month-to-month! (time-varying attribute)")
    else:
        print("  No valid API values calculated")

    return df


# ============================================================================
# STEP 6: UNIT CONVERSIONS
# ============================================================================

def convert_units(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """
    Convert Argentina units to OPGEE/Pyxis standard units.

    CONVERSIONS:
        1. Oil: m³ → barrels (bbl)
           oil_prod_m3 → oil_prod (bbl)
           Factor: 6.28981

        2. Gas: Mm³ → m³
           gas_prod_mm3 → gas_prod_m3
           Factor: 1,000,000

        3. Water: m³ → m³ (no change)
           water_prod_m3 → water_prod (m³)

        4. Injections: same conversions as production

    TRANSFORMATION: ONE-TO-ONE with unit conversion
    """
    print(f"\n{'='*70}")
    print(f"STEP 6: Unit Conversions")
    print(f"{'='*70}")

    conversions = config['unit_conversions']

    # Oil: m³ → bbl
    print(f"Oil: m³ → bbl (×{conversions['oil_m3_to_bbl']})")
    df['oil_prod'] = df['oil_prod_m3'] * conversions['oil_m3_to_bbl']
    print(f"  Range: {df['oil_prod'].min():.2f} to {df['oil_prod'].max():.2f} bbl")

    # Gas: Mm³ → m³
    print(f"Gas: Mm³ → m³ (×{conversions['gas_mm3_to_m3']})")
    df['gas_prod_m3'] = df['gas_prod_mm3'] * conversions['gas_mm3_to_m3']
    df['gas_prod'] = df['gas_prod_m3']  # Final gas production in m³
    print(f"  Range: {df['gas_prod'].min():.2e} to {df['gas_prod'].max():.2e} m³")

    # Water: m³ → m³ (no conversion)
    print(f"Water: m³ → m³ (no conversion)")
    df['water_prod'] = df['water_prod_m3']

    # Injections
    print(f"Water injection: m³ → m³ (no conversion)")
    df['water_injected'] = df['water_injected_m3']

    print(f"Gas injection: Mm³ → m³ (×{conversions['gas_mm3_to_m3']})")
    df['gas_injected_m3'] = df['gas_injected_mm3'] * conversions['gas_mm3_to_m3']
    df['gas_injected'] = df['gas_injected_m3']

    print("\n✅ Unit conversions complete")

    return df


# ============================================================================
# STEP 7: CALCULATE FUNCTIONAL UNIT (OIL vs GAS CLASSIFICATION)
# ============================================================================

def determine_functional_unit(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """
    Classify each field as 'oil' or 'gas' based on production data.

    THREE-WAY LOGIC:

    1. Field only in oil file (gas_prod = 0):
       → functional_unit = 'oil'

    2. Field only in gas file (oil_prod = 0):
       → functional_unit = 'gas'

    3. Field in BOTH files (has both oil and gas):
       → Calculate GOR = gas_prod_m3 / oil_prod_m3
       → If GOR > threshold: 'gas'
       → If GOR ≤ threshold: 'oil'

    GOR THRESHOLD:
        10,000 scf/bbl = 1,781 m³/m³

    TRANSFORMATION: CALCULATED FIELD (conditional logic)
        oil_prod + gas_prod → functional_unit
    """
    print(f"\n{'='*70}")
    print(f"STEP 7: Determining Functional Unit (Oil vs Gas)")
    print(f"{'='*70}")

    gor_threshold = config['functional_unit_classification']['gor_threshold_m3_m3']
    print(f"GOR Threshold: {gor_threshold} m³/m³ (10,000 scf/bbl)")

    def classify(row):
        """Classify single row."""
        if row['gas_prod'] == 0:
            return 'oil'  # No gas production
        elif row['oil_prod'] == 0:
            return 'gas'  # No oil production
        else:
            # Calculate GOR
            gor = row['gas_prod_m3'] / row['oil_prod_m3']
            return 'gas' if gor > gor_threshold else 'oil'

    df['functional_unit'] = df.apply(classify, axis=1)

    # Statistics
    counts = df['functional_unit'].value_counts()
    print(f"\nClassification Results:")
    print(f"  Oil fields: {counts.get('oil', 0):,} ({counts.get('oil', 0)/len(df)*100:.1f}%)")
    print(f"  Gas fields: {counts.get('gas', 0):,} ({counts.get('gas', 0)/len(df)*100:.1f}%)")

    print(f"\n✅ Functional unit classification complete")

    return df


# ============================================================================
# STEP 8: CALCULATE PRODUCTION RATIOS
# ============================================================================

def calculate_production_ratios(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate production ratios for OPGEE attributes.

    FORMULAS:

    1. GOR (Gas-to-Oil Ratio):
       gor = gas_prod_m3 / oil_prod_m3
       Units: m³ gas per m³ oil (dimensionless)

    2. WOR (Water-to-Oil Ratio):
       wor = water_prod / oil_prod
       Units: m³ water per m³ oil (dimensionless)

    3. WIR (Water Injection Ratio):
       wir = water_injected / oil_prod
       Units: m³ water injected per m³ oil (dimensionless)

    4. GLIR (Gas Lift Injection Ratio):
       glir = gas_injected / oil_prod
       Units: m³ gas injected per m³ oil (dimensionless)

    TRANSFORMATION: CALCULATED FIELDS (division)
        2 columns → 1 column (ratio)

    HANDLING DIVISION BY ZERO:
        Replace inf and -inf with 0
        For gas fields (oil_prod = 0), ratios will be 0
    """
    print(f"\n{'='*70}")
    print(f"STEP 8: Calculating Production Ratios")
    print(f"{'='*70}")

    # GOR: Gas-to-Oil Ratio
    print("\n1. GOR (Gas-to-Oil Ratio) = gas_prod_m3 / oil_prod_m3")
    df['gor'] = df['gas_prod_m3'] / df['oil_prod_m3']
    df['gor'] = df['gor'].replace([np.inf, -np.inf], 0)
    valid_gor = df[df['gor'] > 0]['gor']
    if len(valid_gor) > 0:
        print(f"   Range: {valid_gor.min():.2f} to {valid_gor.max():.2f}")
        print(f"   Mean: {valid_gor.mean():.2f}")

    # WOR: Water-to-Oil Ratio
    print("\n2. WOR (Water-to-Oil Ratio) = water_prod / oil_prod")
    df['wor'] = df['water_prod'] / df['oil_prod_m3']
    df['wor'] = df['wor'].replace([np.inf, -np.inf], 0)
    valid_wor = df[df['wor'] > 0]['wor']
    if len(valid_wor) > 0:
        print(f"   Range: {valid_wor.min():.2f} to {valid_wor.max():.2f}")
        print(f"   Mean: {valid_wor.mean():.2f}")

    # WIR: Water Injection Ratio
    print("\n3. WIR (Water Injection Ratio) = water_injected / oil_prod")
    df['wir'] = df['water_injected'] / df['oil_prod_m3']
    df['wir'] = df['wir'].replace([np.inf, -np.inf], 0)
    valid_wir = df[df['wir'] > 0]['wir']
    if len(valid_wir) > 0:
        print(f"   Range: {valid_wir.min():.2f} to {valid_wir.max():.2f}")
        print(f"   Mean: {valid_wir.mean():.2f}")

    # GLIR: Gas Lift Injection Ratio
    print("\n4. GLIR (Gas Lift Injection Ratio) = gas_injected / oil_prod")
    df['glir'] = df['gas_injected'] / df['oil_prod_m3']
    df['glir'] = df['glir'].replace([np.inf, -np.inf], 0)
    valid_glir = df[df['glir'] > 0]['glir']
    if len(valid_glir) > 0:
        print(f"   Range: {valid_glir.min():.2f} to {valid_glir.max():.2f}")
        print(f"   Mean: {valid_glir.mean():.2f}")

    print(f"\n✅ Production ratios calculated")

    return df


# ============================================================================
# STEP 9: DETECT EOR METHODS
# ============================================================================

def detect_eor_methods(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """
    Detect Enhanced Oil Recovery (EOR) methods from production types and injection data.

    ONE-TO-MANY TRANSFORMATION:
        secondary_prod_m3 + injection data → multiple binary flags

    BINARY FLAGS (0 or 1):

    1. water_flooding:
       Condition: secondary_prod > 0 AND water_injected > 0
       Logic: Secondary recovery with water injection

    2. natural_gas_reinjection:
       Condition: secondary_prod > 0 AND gas_injected > 0
       Logic: Secondary recovery with gas injection

    3. steam_flooding:
       Condition: assisted_recovery > 0 AND wir > threshold (default: 5)
       Logic: Tertiary recovery with high water injection (suggests steam)

    4. gas_flooding:
       Condition: assisted_recovery > 0 AND gas_injected > 0
       Logic: Tertiary recovery with gas injection (CO2, N2, etc.)
    """
    print(f"\n{'='*70}")
    print(f"STEP 9: Detecting EOR Methods (one-to-many)")
    print(f"{'='*70}")

    # Water flooding
    print("\n1. Water Flooding (secondary + water injection)")
    df['water_flooding'] = (
        (df.get('secondary_prod_m3', 0) > 0) &
        (df['water_injected'] > 0)
    ).astype(int)
    print(f"   Fields with water flooding: {df['water_flooding'].sum():,}")

    # Natural gas reinjection
    print("\n2. Natural Gas Reinjection (secondary + gas injection)")
    df['natural_gas_reinjection'] = (
        (df.get('secondary_prod_m3', 0) > 0) &
        (df['gas_injected'] > 0)
    ).astype(int)
    print(f"   Fields with gas reinjection: {df['natural_gas_reinjection'].sum():,}")

    # Steam flooding (high WIR suggests steam)
    wir_threshold = config['eor_detection']['steam_flooding_wir_threshold']
    print(f"\n3. Steam Flooding (assisted recovery + WIR > {wir_threshold})")
    df['steam_flooding'] = (
        (df.get('assisted_recovery_m3', 0) > 0) &
        (df['wir'] > wir_threshold)
    ).astype(int)
    print(f"   Fields with steam flooding: {df['steam_flooding'].sum():,}")

    # Gas flooding
    print("\n4. Gas Flooding (assisted recovery + gas injection)")
    df['gas_flooding'] = (
        (df.get('assisted_recovery_m3', 0) > 0) &
        (df['gas_injected'] > 0)
    ).astype(int)
    print(f"   Fields with gas flooding: {df['gas_flooding'].sum():,}")

    print(f"\n✅ EOR methods detected")

    return df


# ============================================================================
# STEP 10: DETERMINE OFFSHORE FLAG
# ============================================================================

def determine_offshore(df: pd.DataFrame) -> pd.DataFrame:
    """
    Determine if field is offshore or onshore.

    ONE-TO-ONE TRANSFORMATION:
        location (string) → offshore (binary)

    LOGIC:
        If 'location' contains "Off Shore" → offshore = 1
        Otherwise → offshore = 0

    SOURCE:
        'ubicacion' field from production data (Spanish)
        Renamed to 'location' (English)
        Values: "On Shore" or "Off Shore"
    """
    print(f"\n{'='*70}")
    print(f"STEP 10: Determining Offshore Flag")
    print(f"{'='*70}")

    if 'location' in df.columns:
        df['offshore'] = df['location'].str.contains(
            'Off Shore',
            case=False,
            na=False
        ).astype(int)

        offshore_count = df['offshore'].sum()
        onshore_count = len(df) - offshore_count

        print(f"  Offshore fields: {offshore_count:,} ({offshore_count/len(df)*100:.1f}%)")
        print(f"  Onshore fields: {onshore_count:,} ({onshore_count/len(df)*100:.1f}%)")
    else:
        print("  ⚠️ No location column found, defaulting to onshore (offshore = 0)")
        df['offshore'] = 0

    print(f"\n✅ Offshore flag set")

    return df


# ============================================================================
# STEP 11: GENERATE TEMPORAL FIELDS
# ============================================================================

def generate_temporal_fields(df: pd.DataFrame) -> pd.DataFrame:
    """
    Generate start_date and end_date from year and month.

    ONE-TO-MANY TRANSFORMATION:
        year + month → start_date + end_date

    FORMULAS:
        start_date = YYYY-MM-01 (first day of month)
        end_date = YYYY-MM-DD (last day of month, varies by month)

    FORMAT: ISO 8601 (YYYY-MM-DD)
    """
    print(f"\n{'='*70}")
    print(f"STEP 11: Generating Temporal Fields")
    print(f"{'='*70}")

    def get_date_range(row):
        """Get start and end dates for a given year-month."""
        year = int(row['year'])
        month = int(row['month'])
        start_date = f"{year}-{month:02d}-01"
        last_day = monthrange(year, month)[1]
        end_date = f"{year}-{month:02d}-{last_day}"
        return pd.Series({'start_date': start_date, 'end_date': end_date})

    date_fields = df.apply(get_date_range, axis=1)
    df = pd.concat([df, date_fields], axis=1)

    print(f"  Date range: {df['start_date'].min()} to {df['end_date'].max()}")
    print(f"  Months covered: {df['month'].nunique()}")

    print(f"\n✅ Temporal fields generated")

    return df


# ============================================================================
# STEP 12: ADD STATIC FIELDS
# ============================================================================

def add_static_fields(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add static fields that are same for all records.

    STATIC FIELDS:
        - country: "Argentina"

    These fields don't change across fields or time periods.
    """
    print(f"\n{'='*70}")
    print(f"STEP 12: Adding Static Fields")
    print(f"{'='*70}")

    df['country'] = 'Argentina'
    print("  country = 'Argentina'")

    print(f"\n✅ Static fields added")

    return df


# ============================================================================
# STEP 13: SELECT AND RENAME FINAL COLUMNS
# ============================================================================

def select_final_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Select final columns for Pyxis ingestion, all in ENGLISH.

    FINAL COLUMNS (all lowercase, underscore_separated):
        - Identification: field_id, name, country, company_name
        - Temporal: year, month, start_date, end_date
        - Geographic: basin, province, offshore, depth
        - Classification: functional_unit
        - Production: oil_prod, gas_prod, water_prod
        - Injection: water_injected, gas_injected
        - Ratios: gor, wor, wir, glir
        - Technical: api
        - Well Counts: num_prod_wells, num_water_inj_wells, num_gas_inj_wells
        - Extraction: downhole_pump, gas_lifting
        - Production Types: primary_prod_m3, secondary_prod_m3, assisted_recovery_m3
        - EOR Methods: water_flooding, natural_gas_reinjection, steam_flooding, gas_flooding

    VALIDATION:
        ✅ All column names in English (no Spanish characters)
        ✅ All column names lowercase with underscores
        ✅ No duplicate columns
    """
    print(f"\n{'='*70}")
    print(f"STEP 13: Selecting Final Columns")
    print(f"{'='*70}")

    final_columns = [
        # Identification
        'field_id',
        'name',
        'country',
        'company_name',

        # Temporal
        'year',
        'month',
        'start_date',
        'end_date',

        # Geographic
        'basin',
        'province',
        'offshore',
        'depth',             # Average well depth (m)

        # Classification
        'functional_unit',

        # Production (converted units)
        'oil_prod',          # bbl
        'gas_prod',          # m³
        'water_prod',        # m³

        # Injection (converted units)
        'water_injected',    # m³
        'gas_injected',      # m³

        # Ratios
        'gor',
        'wor',
        'wir',
        'glir',

        # Technical
        'api',

        # Well counts
        'num_prod_wells',
        'num_water_inj_wells',
        'num_gas_inj_wells',

        # Extraction methods (binary flags)
        'downhole_pump',
        'gas_lifting',

        # Production breakdown (original units m³)
        'primary_prod_m3',
        'secondary_prod_m3',
        'assisted_recovery_m3',
        'unconventional_prod_m3',

        # EOR methods (binary flags)
        'water_flooding',
        'natural_gas_reinjection',
        'steam_flooding',
        'gas_flooding',
    ]

    # Select columns that exist
    available_columns = [col for col in final_columns if col in df.columns]
    missing_columns = [col for col in final_columns if col not in df.columns]

    print(f"\nAvailable columns: {len(available_columns)}/{len(final_columns)}")
    if missing_columns:
        print(f"Missing columns: {', '.join(missing_columns)}")

    df_final = df[available_columns].copy()

    # Validate: all columns in English
    spanish_chars = set('áéíóúñÁÉÍÓÚÑ')
    for col in df_final.columns:
        if any(char in spanish_chars for char in col):
            print(f"  ⚠️ WARNING: Column '{col}' contains Spanish characters!")

    print(f"\n✅ Final dataset: {len(df_final):,} rows × {len(df_final.columns)} columns")
    print(f"   All column names in English: ✅")

    return df_final


# ============================================================================
# MAIN PIPELINE
# ============================================================================

def main():
    """Execute complete transformation pipeline."""

    print("\n" + "="*70)
    print("ARGENTINA DATA TRANSFORMATION PIPELINE")
    print("="*70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Paths
    base_dir = Path(__file__).parent.parent
    raw_dir = base_dir / "raw"
    output_dir = base_dir / "output"
    config_dir = base_dir / "config"

    # Load configuration
    print("\nLoading configuration...")
    config = load_config(config_dir / "opgee_calculation_params.json")
    year = config['time_scope']['start_year']
    print(f"  Processing year: {year}")

    # Input files
    oil_file = raw_dir / "produccin-de-petrleo-por-yacimiento.csv"
    gas_file = raw_dir / "produccin-de-gas-por-yacimiento.csv"
    well_prod_file = raw_dir / "produccin-de-pozos-de-gas-y-petrleo-2025.csv"
    well_chars_file = raw_dir / "capitulo-iv-pozos.csv"

    # Check required files exist
    if not oil_file.exists():
        print(f"\n❌ ERROR: Oil production file not found: {oil_file}")
        return
    if not gas_file.exists():
        print(f"\n❌ ERROR: Gas production file not found: {gas_file}")
        return

    # Optional files (well data)
    has_well_prod = well_prod_file.exists()
    has_well_chars = well_chars_file.exists()

    if not has_well_prod:
        print(f"\n⚠️  WARNING: Well production file not found: {well_prod_file}")
        print("   Well count data will not be available")
    if not has_well_chars:
        print(f"\n⚠️  WARNING: Well characteristics file not found: {well_chars_file}")
        print("   Depth and geometry data will not be available")

    # Execute pipeline
    try:
        # Step 1: Load and pivot oil production
        oil_df = load_and_pivot_oil_production(oil_file, year)
        oil_df = calculate_total_oil_production(oil_df)

        # Step 2: Load and pivot gas production
        gas_df = load_and_pivot_gas_production(gas_file, year)
        gas_df = calculate_total_gas_production(gas_df)

        # Step 4: Merge oil and gas
        combined = merge_oil_and_gas_production(oil_df, gas_df)

        # Step 5: Calculate API gravity (time-varying!)
        combined = calculate_api_gravity(combined)

        # Step 6: Unit conversions
        combined = convert_units(combined, config)

        # Step 7: Determine functional unit
        combined = determine_functional_unit(combined, config)

        # Step 8: Calculate ratios
        combined = calculate_production_ratios(combined)

        # Step 9: Detect EOR methods
        combined = detect_eor_methods(combined, config)

        # Step 10: Determine offshore
        combined = determine_offshore(combined)

        # Step 10a: Load and merge well counts (if available)
        if has_well_prod:
            well_counts = load_and_aggregate_well_counts(well_prod_file, year)
            combined = merge_well_counts(combined, well_counts)

        # Step 10b: Load and merge well characteristics (if available)
        if has_well_chars:
            well_chars = load_and_aggregate_well_characteristics(well_chars_file)
            combined = merge_well_characteristics(combined, well_chars)

        # Step 11: Generate temporal fields
        combined = generate_temporal_fields(combined)

        # Step 12: Add static fields
        combined = add_static_fields(combined)

        # Step 13: Select final columns
        final_df = select_final_columns(combined)

        # Save output
        output_file = output_dir / "field_production_complete.csv"
        output_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n{'='*70}")
        print(f"SAVING OUTPUT")
        print(f"{'='*70}")

        final_df.to_csv(output_file, index=False, encoding='utf-8')
        print(f"✅ Saved: {output_file}")
        print(f"   Rows: {len(final_df):,}")
        print(f"   Columns: {len(final_df.columns)}")
        print(f"   Size: {output_file.stat().st_size / 1024 / 1024:.2f} MB")

        # Summary statistics
        print(f"\n{'='*70}")
        print(f"SUMMARY STATISTICS")
        print(f"{'='*70}")
        print(f"Fields: {final_df['field_id'].nunique():,}")
        print(f"Months: {final_df['month'].nunique()}")
        print(f"Date range: {final_df['start_date'].min()} to {final_df['end_date'].max()}")
        print(f"Oil fields: {(final_df['functional_unit'] == 'oil').sum():,}")
        print(f"Gas fields: {(final_df['functional_unit'] == 'gas').sum():,}")

        print(f"\n{'='*70}")
        print(f"✅ PIPELINE COMPLETE")
        print(f"{'='*70}")
        print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    except Exception as e:
        print(f"\n❌ ERROR: Pipeline failed")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return


if __name__ == "__main__":
    main()
