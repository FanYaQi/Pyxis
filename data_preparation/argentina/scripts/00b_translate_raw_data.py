"""
Translate Raw Data Files for Verification

This script creates English-translated versions of the raw Spanish CSV files
for verification purposes. The translated files are saved in raw/translated/
directory with _english suffix.

INPUT: Raw Spanish CSV files in raw/ directory
OUTPUT: Translated CSV files in raw/translated/ directory

Purpose: Help verify data by providing English column headers
"""

import sys
from pathlib import Path

# Add utils to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
from datetime import datetime


# ============================================================================
# COLUMN TRANSLATION MAPPINGS
# ============================================================================

# Field production files (oil and gas)
FIELD_PRODUCTION_TRANSLATION = {
    'indice_tiempo': 'time_index',
    'anio': 'year',
    'mes': 'month',
    'idempresa': 'company_id',
    'empresa': 'company_name',
    'idareapermisoconcesion': 'permit_area_id',
    'areapermisoconcesion': 'permit_area_name',
    'idareayacimiento': 'field_id',
    'areayacimiento': 'field_name',
    'idcuenca': 'basin_id',
    'cuenca': 'basin',
    'idprovincia': 'province_id',
    'provincia': 'province',
    'idubicacion': 'location_id',
    'ubicacion': 'location',
    'idconcepto': 'concept_id',
    'concepto': 'concept',
    'cantidad': 'quantity',
    'observaciones': 'notes',
    'desc_mes': 'month_description',
    'fecha_data': 'data_date',
}

# Well production file
WELL_PRODUCTION_TRANSLATION = {
    'indice_tiempo': 'time_index',
    'anio': 'year',
    'mes': 'month',
    'idempresa': 'company_id',
    'empresa': 'company_name',
    'idareapermisoconcesion': 'permit_area_id',
    'areapermisoconcesion': 'permit_area_name',
    'idareayacimiento': 'field_id',
    'areayacimiento': 'field_name',
    'idcuenca': 'basin_id',
    'cuenca': 'basin',
    'idprovincia': 'province_id',
    'provincia': 'province',
    'idubicacion': 'location_id',
    'ubicacion': 'location',
    'idpozo': 'well_id',
    'sigla': 'well_name',
    'tipopozo': 'well_type',
    'tipoestado': 'well_status',
    'tipoextraccion': 'extraction_method',
    'prod_pet': 'oil_prod_m3',
    'prod_gas': 'gas_prod_km3',
    'prod_agua': 'water_prod_m3',
    'iny_agua': 'water_injected_m3',
    'iny_gas': 'gas_injected_km3',
    'iny_co2': 'co2_injected_km3',
    'iny_otro': 'other_injected_km3',
    'observaciones': 'notes',
    'desc_mes': 'month_description',
    'fecha_data': 'data_date',
}

# Well characteristics file
WELL_CHARACTERISTICS_TRANSLATION = {
    'idpozo': 'well_id',
    'sigla': 'well_name',
    'cod_yacimiento': 'field_code',
    'idareayacimiento': 'field_id',
    'yacimiento': 'field_name',
    'cuenca': 'basin',
    'provincia': 'province',
    'areapermisoconcesion': 'permit_area',
    'profundidad': 'depth_m',
    'tipopozo': 'well_type',
    'tipoestado': 'well_status',
    'formacion': 'formation',
    'sub_tipo_recurso': 'resource_subtype',
    'empresa': 'company_name',
    'coord_x': 'coord_x',
    'coord_y': 'coord_y',
    'geojson': 'geometry',
}


# ============================================================================
# TRANSLATION FUNCTIONS
# ============================================================================

def translate_file(
    input_file: Path,
    output_file: Path,
    translation_map: dict,
    sample_rows: int = None
):
    """
    Translate a CSV file from Spanish to English column headers.

    Args:
        input_file: Path to input CSV file (Spanish)
        output_file: Path to output CSV file (English)
        translation_map: Dictionary mapping Spanish column names to English
        sample_rows: If provided, only translate first N rows (for large files)
    """
    print(f"\n{'='*70}")
    print(f"Translating: {input_file.name}")
    print(f"{'='*70}")

    if not input_file.exists():
        print(f"  ⚠️  File not found, skipping")
        return

    # Read file (with row limit for large files)
    print(f"  Reading file...")
    if sample_rows:
        df = pd.read_csv(input_file, encoding='utf-8', nrows=sample_rows)
        print(f"  Loaded first {len(df):,} rows (sample)")
    else:
        df = pd.read_csv(input_file, encoding='utf-8')
        print(f"  Loaded {len(df):,} rows (full file)")

    # Show original columns
    print(f"\n  Original columns ({len(df.columns)}):")
    for col in list(df.columns)[:5]:
        print(f"    - {col}")
    if len(df.columns) > 5:
        print(f"    ... and {len(df.columns) - 5} more")

    # Translate column names
    print(f"\n  Translating column names...")
    df_translated = df.rename(columns=translation_map)

    # Show translated columns
    print(f"\n  Translated columns ({len(df_translated.columns)}):")
    for col in list(df_translated.columns)[:5]:
        print(f"    - {col}")
    if len(df_translated.columns) > 5:
        print(f"    ... and {len(df_translated.columns) - 5} more")

    # Count translations
    translated_count = sum(1 for col in df.columns if col in translation_map)
    print(f"\n  Columns translated: {translated_count}/{len(df.columns)}")

    # Save
    output_file.parent.mkdir(parents=True, exist_ok=True)
    df_translated.to_csv(output_file, index=False, encoding='utf-8')

    size_mb = output_file.stat().st_size / 1024 / 1024
    print(f"\n  ✅ Saved: {output_file.name}")
    print(f"     Size: {size_mb:.2f} MB")


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Translate all raw data files."""

    print("\n" + "="*70)
    print("TRANSLATING RAW DATA FILES FOR VERIFICATION")
    print("="*70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Paths
    base_dir = Path(__file__).parent.parent
    raw_dir = base_dir / "raw"
    translated_dir = raw_dir / "translated"

    # Create translated directory
    translated_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nOutput directory: {translated_dir}")

    # ========================================================================
    # 1. Translate Oil Field Production
    # ========================================================================

    translate_file(
        input_file=raw_dir / "produccin-de-petrleo-por-yacimiento.csv",
        output_file=translated_dir / "oil_field_production_english.csv",
        translation_map=FIELD_PRODUCTION_TRANSLATION,
        sample_rows=50000  # Sample for large file
    )

    # ========================================================================
    # 2. Translate Gas Field Production
    # ========================================================================

    translate_file(
        input_file=raw_dir / "produccin-de-gas-por-yacimiento.csv",
        output_file=translated_dir / "gas_field_production_english.csv",
        translation_map=FIELD_PRODUCTION_TRANSLATION,
        sample_rows=50000  # Sample for large file
    )

    # ========================================================================
    # 3. Translate Well Production
    # ========================================================================

    translate_file(
        input_file=raw_dir / "produccin-de-pozos-de-gas-y-petrleo-2025.csv",
        output_file=translated_dir / "well_production_2025_english.csv",
        translation_map=WELL_PRODUCTION_TRANSLATION,
        sample_rows=10000  # Sample for large file
    )

    # ========================================================================
    # 4. Translate Well Characteristics
    # ========================================================================

    translate_file(
        input_file=raw_dir / "capitulo-iv-pozos.csv",
        output_file=translated_dir / "well_characteristics_english.csv",
        translation_map=WELL_CHARACTERISTICS_TRANSLATION,
        sample_rows=10000  # Sample for large file
    )

    print(f"\n{'='*70}")
    print(f"✅ TRANSLATION COMPLETE")
    print(f"{'='*70}")
    print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\nTranslated files saved in: {translated_dir}")
    print("\nNOTE: Large files were sampled to reduce size.")
    print("      Full data is used in the main pipeline.\n")


if __name__ == "__main__":
    main()
