"""
Comprehensive Raw Data Translation with O&G Domain Knowledge

This script translates ALL 12 raw Argentina data files from Spanish to English using
comprehensive mappings with oil & gas domain knowledge. It translates:
- Column names (Spanish → English with UNITS PRESERVED: m3, mm3, psi, hp, tons, etc.)
- Data values (Spanish → English with meaningful O&G terminology)

FILES TRANSLATED:
    1. Oil field production (monthly, by recovery type) - m3
    2. Gas field production (monthly, by pressure category) - Mm3
    3. Well production (monthly, by extraction method) - km3 for gas
    4. Well characteristics (static metadata) - meters
    5. Fracture/completion data (NEW - hydraulic fracturing details) - psi, hp, tons
    6. Field shapes & depth (NEW - GeoJSON boundaries, depth) - meters
    7. Daily oil production (average daily rates) - m3/day
    8. Daily gas production (average daily rates) - Mm3/day
    9. Field production by formation & well vintage (includes INJECTION data) - m3, km3
    10. Plant gas processing (includes FLARING data) - Mm3
    11. Historical gas wells pre-2009 (well counts by status)
    12. Historical oil wells pre-2009 (well counts by lift method)

MAPPINGS:
    Translation mappings are defined in config/translation_mappings/
    Each mapping file contains:
    - Column name translations (with units preserved)
    - Value translations for categorical fields (O&G domain knowledge)
    - Technical descriptions explaining O&G terminology
    - Industry benchmarks and typical value ranges

INPUT: Raw Spanish CSV files in raw/
OUTPUT: Translated English CSV files in raw/translated/

Author: Pyxis Data Preparation Pipeline
Date: 2025-10-31
Updated: 2025-10-31 (Added 6 new file types)
"""

import sys
from pathlib import Path

# Add utils to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
import json
import re
from datetime import datetime
from typing import Dict, Any


# ============================================================================
# CONFIGURATION
# ============================================================================

def load_mapping(mapping_file: Path) -> Dict[str, Any]:
    """Load a translation mapping JSON file."""
    with open(mapping_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_all_mappings(config_dir: Path) -> Dict[str, Dict]:
    """Load all translation mapping files."""
    mapping_dir = config_dir / "translation_mappings"

    mappings = {}
    for mapping_file in mapping_dir.glob("*.json"):
        mapping_name = mapping_file.stem
        mappings[mapping_name] = load_mapping(mapping_file)
        print(f"  ✓ Loaded: {mapping_name}")

    return mappings


# ============================================================================
# TRANSLATION FUNCTIONS
# ============================================================================

def translate_dataframe(
    df: pd.DataFrame,
    mapping: Dict[str, Any],
    file_name: str
) -> pd.DataFrame:
    """
    Translate a dataframe using the provided mapping.

    Args:
        df: DataFrame to translate
        mapping: Translation mapping dictionary
        file_name: Original file name (for logging)

    Returns:
        Translated DataFrame
    """

    print(f"\n  Translating columns...")

    # 1. Translate column names
    column_mappings = mapping.get('column_mappings', {})
    df_translated = df.rename(columns=column_mappings)

    translated_cols = sum(1 for col in df.columns if col in column_mappings)
    print(f"    Columns: {translated_cols}/{len(df.columns)} translated")

    # 2. Translate values in specific columns
    value_mappings = mapping.get('value_mappings', {})

    for column_english, value_map in value_mappings.items():
        if column_english in df_translated.columns:
            print(f"    Translating values in '{column_english}'...")

            # Count how many unique values we'll translate
            unique_before = df_translated[column_english].nunique()

            # Translate values
            df_translated[column_english] = df_translated[column_english].map(
                lambda x: value_map.get(x, x) if pd.notna(x) else x
            )

            unique_after = df_translated[column_english].nunique()
            print(f"      {unique_before} → {unique_after} unique values")

    return df_translated


def translate_file(
    input_file: Path,
    output_file: Path,
    mapping: Dict[str, Any],
    max_rows: int = None
):
    """
    Translate a single CSV file.

    Args:
        input_file: Path to input Spanish CSV
        output_file: Path to output English CSV
        mapping: Translation mapping
        max_rows: Optional limit for large files (None = full file)
    """

    print(f"\n{'='*70}")
    print(f"File: {input_file.name}")
    print(f"{'='*70}")

    if not input_file.exists():
        print(f"  ⚠️  File not found, skipping")
        return

    # Read file
    print(f"  Reading...")
    try:
        if max_rows:
            df = pd.read_csv(input_file, encoding='utf-8', nrows=max_rows, low_memory=False)
            print(f"    Loaded {len(df):,} rows (sample)")
        else:
            df = pd.read_csv(input_file, encoding='utf-8', low_memory=False)
            print(f"    Loaded {len(df):,} rows (FULL FILE)")
    except Exception as e:
        print(f"  ❌ Error reading file: {e}")
        return

    # Show original structure
    print(f"    Columns: {len(df.columns)}")
    print(f"    Memory: {df.memory_usage(deep=True).sum() / 1024 / 1024:.1f} MB")

    # Translate
    df_translated = translate_dataframe(df, mapping, input_file.name)

    # Save
    output_file.parent.mkdir(parents=True, exist_ok=True)
    df_translated.to_csv(output_file, index=False, encoding='utf-8')

    size_mb = output_file.stat().st_size / 1024 / 1024
    print(f"\n  ✅ Saved: {output_file.name}")
    print(f"     Size: {size_mb:.2f} MB")


def extract_year_from_filename(filename: str) -> str:
    """Extract year from filename like 'produccin-de-pozos-de-gas-y-petrleo-2025.csv'."""
    match = re.search(r'(\d{4})', filename)
    return match.group(1) if match else 'unknown'


def translate_year_suffixed_files(
    raw_dir: Path,
    translated_dir: Path,
    mapping: Dict[str, Any],
    pattern: str,
    output_prefix: str,
    full_translation: bool = False,
    max_rows_default: int = 100000
):
    """
    Translate all files matching a pattern with year suffixes (handles year-specific and year-range files).

    Args:
        raw_dir: Raw data directory
        translated_dir: Output directory
        mapping: Translation mapping
        pattern: Glob pattern to match files (e.g., "produccin-de-petrleo-por-yacimiento*.csv")
        output_prefix: Prefix for output files (e.g., "oil_field_production")
        full_translation: If True, translate full files. If False, use samples.
        max_rows_default: Default max rows for sampling
    """

    print(f"\n{'='*70}")
    print(f"{pattern.upper().replace('*.CSV', '')} (All Versions)")
    print(f"{'='*70}")

    # Find all files matching pattern
    matched_files = list(raw_dir.glob(pattern))

    if not matched_files:
        print(f"  ⚠️  No files matching pattern: {pattern}")
        return

    print(f"  Found {len(matched_files)} file(s)")

    for input_file in sorted(matched_files):
        # Extract year or year range from filename
        # Handles: filename.csv, filename_2024.csv, filename-2024.csv, filename_2024-2025.csv
        # Match either underscore or hyphen before year
        year_match = re.search(r'[-_](\d{4}(?:-\d{4})?)\.csv$', input_file.name)

        if year_match:
            year_suffix = year_match.group(1)
            output_name = f"{output_prefix}_{year_suffix}_english.csv"
        else:
            # No year suffix - use mapping's default output name
            output_name = mapping.get('output_file_name', f"{output_prefix}_english.csv")

        output_file = translated_dir / output_name

        # Use sample for large files unless full_translation requested
        max_rows = None if full_translation else max_rows_default

        translate_file(input_file, output_file, mapping, max_rows=max_rows)


def translate_well_production_files(
    raw_dir: Path,
    translated_dir: Path,
    mapping: Dict[str, Any],
    full_translation: bool = False
):
    """
    Translate all well production files (handles multiple years).

    Args:
        raw_dir: Raw data directory
        translated_dir: Output directory
        mapping: Well production mapping
        full_translation: If True, translate full files. If False, use samples.
    """
    translate_year_suffixed_files(
        raw_dir=raw_dir,
        translated_dir=translated_dir,
        mapping=mapping,
        pattern="produccin-de-pozos-de-gas-y-petrleo-*.csv",
        output_prefix="well_production",
        full_translation=full_translation,
        max_rows_default=100000
    )


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Translate all raw data files."""

    print("\n" + "="*70)
    print("COMPREHENSIVE RAW DATA TRANSLATION")
    print("Spanish → English with O&G Domain Knowledge")
    print("="*70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Paths
    base_dir = Path(__file__).parent.parent
    raw_dir = base_dir / "raw"
    translated_dir = raw_dir / "translated"
    config_dir = base_dir / "config"

    # Create output directory
    translated_dir.mkdir(parents=True, exist_ok=True)

    # Load all mappings
    print("Loading translation mappings...")
    mappings = load_all_mappings(config_dir)
    print(f"\n✓ Loaded {len(mappings)} mapping file(s)\n")

    # Translation settings
    # Set to True to translate FULL files (slow, large output)
    # Set to False to translate SAMPLES (fast, for testing)
    FULL_TRANSLATION = True  # Full translation enabled

    if FULL_TRANSLATION:
        print("⚠️  MODE: FULL TRANSLATION (this will take time and create large files)")
    else:
        print("ℹ️  MODE: SAMPLE TRANSLATION (faster, smaller files for testing)")

    # ========================================================================
    # 1. Oil Field Production (handles year-suffixed files)
    # ========================================================================

    if 'oil_field_production_mapping' in mappings:
        translate_year_suffixed_files(
            raw_dir=raw_dir,
            translated_dir=translated_dir,
            mapping=mappings['oil_field_production_mapping'],
            pattern="produccin-de-petrleo-por-yacimiento*.csv",
            output_prefix="oil_field_production",
            full_translation=FULL_TRANSLATION,
            max_rows_default=100000
        )

    # ========================================================================
    # 2. Gas Field Production (handles year-suffixed files)
    # ========================================================================

    if 'gas_field_production_mapping' in mappings:
        translate_year_suffixed_files(
            raw_dir=raw_dir,
            translated_dir=translated_dir,
            mapping=mappings['gas_field_production_mapping'],
            pattern="produccin-de-gas-por-yacimiento*.csv",
            output_prefix="gas_field_production",
            full_translation=FULL_TRANSLATION,
            max_rows_default=100000
        )

    # ========================================================================
    # 3. Well Production (All Years)
    # ========================================================================

    if 'well_production_mapping' in mappings:
        translate_well_production_files(
            raw_dir=raw_dir,
            translated_dir=translated_dir,
            mapping=mappings['well_production_mapping'],
            full_translation=FULL_TRANSLATION
        )

    # ========================================================================
    # 4. Well Characteristics
    # ========================================================================

    if 'well_characteristics_mapping' in mappings:
        mapping = mappings['well_characteristics_mapping']
        translate_file(
            input_file=raw_dir / "capitulo-iv-pozos.csv",
            output_file=translated_dir / mapping['output_file_name'],
            mapping=mapping,
            max_rows=None if FULL_TRANSLATION else 50000
        )

    # ========================================================================
    # 5. Fracture/Completion Data (NEW - HIGH PRIORITY)
    # ========================================================================

    if 'fracture_completion_mapping' in mappings:
        mapping = mappings['fracture_completion_mapping']
        translate_file(
            input_file=raw_dir / "datos-de-fractura-de-pozos-de-hidrocarburos-adjunto-iv-actualizacin-diaria.csv",
            output_file=translated_dir / mapping['output_file_name'],
            mapping=mapping,
            max_rows=None if FULL_TRANSLATION else 10000
        )

    # ========================================================================
    # 6. Field Shapes & Depth (NEW - HIGH PRIORITY)
    # ========================================================================

    if 'field_shapes_depth_mapping' in mappings:
        mapping = mappings['field_shapes_depth_mapping']
        translate_file(
            input_file=raw_dir / "produccin-hidrocarburos-yacimientos-segn-profundidad-promedio.csv",
            output_file=translated_dir / mapping['output_file_name'],
            mapping=mapping,
            max_rows=None  # Static data, small file - always translate fully
        )

    # ========================================================================
    # 7. Daily Oil Production
    # ========================================================================

    if 'daily_oil_production_mapping' in mappings:
        mapping = mappings['daily_oil_production_mapping']
        translate_file(
            input_file=raw_dir / "produccin-de-petrleo-promedio-diaria-por-yacimiento.csv",
            output_file=translated_dir / mapping['output_file_name'],
            mapping=mapping,
            max_rows=None if FULL_TRANSLATION else 50000
        )

    # ========================================================================
    # 8. Daily Gas Production
    # ========================================================================

    if 'daily_gas_production_mapping' in mappings:
        mapping = mappings['daily_gas_production_mapping']
        translate_file(
            input_file=raw_dir / "produccin-de-gas-promedio-diaria-por-yacimiento.csv",
            output_file=translated_dir / mapping['output_file_name'],
            mapping=mapping,
            max_rows=None if FULL_TRANSLATION else 50000
        )

    # ========================================================================
    # 9. Field Production by Formation & Well Vintage (NEW - INCLUDES INJECTION)
    # ========================================================================

    if 'field_production_by_formation_vintage_mapping' in mappings:
        mapping = mappings['field_production_by_formation_vintage_mapping']
        translate_file(
            input_file=raw_dir / "produccin-de-petrleo-y-gas-captulo-iv-por-yacimiento-y-antigedad-de-pozo-productivo.csv",
            output_file=translated_dir / mapping['output_file_name'],
            mapping=mapping,
            max_rows=None if FULL_TRANSLATION else 100000
        )

    # ========================================================================
    # 10. Plant Gas Processing (Includes FLARING data)
    # ========================================================================

    if 'plant_gas_processing_mapping' in mappings:
        mapping = mappings['plant_gas_processing_mapping']
        translate_file(
            input_file=raw_dir / "gas-recibido-retenido-aventado-por-plantas.csv",
            output_file=translated_dir / mapping['output_file_name'],
            mapping=mapping,
            max_rows=None if FULL_TRANSLATION else 10000
        )

    # ========================================================================
    # 11. Historical Gas Wells (Pre-2009) - OPTIONAL
    # ========================================================================

    if 'historical_gas_wells_mapping' in mappings:
        mapping = mappings['historical_gas_wells_mapping']
        translate_file(
            input_file=raw_dir / "pozos-productivos-de-gas-ant-2009.csv",
            output_file=translated_dir / mapping['output_file_name'],
            mapping=mapping,
            max_rows=None if FULL_TRANSLATION else 10000
        )

    # ========================================================================
    # 12. Historical Oil Wells (Pre-2009) - OPTIONAL
    # ========================================================================

    if 'historical_oil_wells_mapping' in mappings:
        mapping = mappings['historical_oil_wells_mapping']
        translate_file(
            input_file=raw_dir / "pozos-productivos-de-petrleo-ant-2009.csv",
            output_file=translated_dir / mapping['output_file_name'],
            mapping=mapping,
            max_rows=None if FULL_TRANSLATION else 10000
        )

    # ========================================================================
    # SUMMARY
    # ========================================================================

    print(f"\n{'='*70}")
    print(f"✅ TRANSLATION COMPLETE")
    print(f"{'='*70}")
    print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\nTranslated files location: {translated_dir}")

    # List generated files
    print(f"\nGenerated files:")
    translated_files = sorted(translated_dir.glob("*.csv"))
    for i, f in enumerate(translated_files, 1):
        size_mb = f.stat().st_size / 1024 / 1024
        print(f"  {i}. {f.name} ({size_mb:.2f} MB)")

    if not FULL_TRANSLATION:
        print(f"\n⚠️  NOTE: Files are SAMPLES for testing.")
        print(f"   Set FULL_TRANSLATION=True in script for complete translation.")

    print()


if __name__ == "__main__":
    main()
