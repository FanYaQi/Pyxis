"""
Argentina Data Preparation Pipeline Orchestrator

Runs all processing scripts in sequence to generate Pyxis ingestion files.

Workflow:
1. Translate all raw Spanish data to English (01_translate_all_raw_data.py)
2. Clean and merge translated production data (02_clean_and_merge_translated.py)
3. Create comprehensive field data with all sources (04_create_comprehensive_field_data.py)
4. Generate Pyxis-compatible CSV and config JSON (03_generate_pyxis_files.py)

Usage:
    cd data_preparation/argentina/scripts
    pipenv run python run_pipeline.py

Note: This pipeline uses the TRANSLATED data workflow (10 data sources)
"""

import sys
from pathlib import Path
import subprocess


def run_script(script_path: Path) -> bool:
    """
    Run a Python script and return success status.

    Args:
        script_path: Path to script to run

    Returns:
        True if successful, False otherwise
    """
    print("\n" + "="*70)
    print(f"Running: {script_path.name}")
    print("="*70)

    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            check=True,
            capture_output=False,
            text=True
        )
        print(f"✅ {script_path.name} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {script_path.name} failed with error")
        return False


def main():
    """Run the complete data preparation pipeline."""
    print("="*70)
    print("ARGENTINA DATA PREPARATION PIPELINE")
    print("Using Translated Data with All 10 Sources")
    print("="*70)

    base_dir = Path(__file__).parent

    # Define scripts in order (new translated workflow)
    scripts = [
        base_dir / "01_translate_all_raw_data.py",           # Translate all 10 files
        base_dir / "02_clean_and_merge_translated.py",       # Merge oil + gas production
        base_dir / "04_create_comprehensive_field_data.py",  # Add fracture, geometry, flaring
        # base_dir / "03_generate_pyxis_files.py",          # TODO: Update for comprehensive data
    ]

    # Check all scripts exist
    for script in scripts:
        if not script.exists():
            print(f"❌ Error: Script not found: {script}")
            sys.exit(1)

    # Run each script
    results = []
    for script in scripts:
        success = run_script(script)
        results.append((script.name, success))

        if not success:
            print("\n" + "="*70)
            print("❌ PIPELINE FAILED")
            print("="*70)
            print(f"Failed at: {script.name}")
            sys.exit(1)

    # Summary
    print("\n" + "="*70)
    print("✅ PIPELINE COMPLETED SUCCESSFULLY")
    print("="*70)
    print("\nScript Results:")
    for script_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {status} - {script_name}")

    print("\n" + "="*70)
    print("GENERATED FILES")
    print("="*70)
    print("\n1. Translated Data (raw/translated/):")
    print("   - 10 CSV files with English column names")
    print("   - Oil, gas, well production, well characteristics")
    print("   - Fracture data, field geometry, flaring data")
    print("   - Historical data (pre-2009)")

    print("\n2. Processed Data (output/):")
    print("   - field_production_complete.csv - Base production metrics")
    print("   - comprehensive_field_data.csv - ALL metrics integrated")

    print("\n3. Comprehensive Data Includes:")
    print("   ✓ Production (oil, gas, water)")
    print("   ✓ Well counts and characteristics")
    print("   ✓ Fracture/completion metrics (proppant, fluids, equipment)")
    print("   ✓ Field geometry and depth")
    print("   ✓ Flaring data for emissions")

    print("\n" + "="*70)
    print("NEXT STEPS")
    print("="*70)
    print("1. Review comprehensive_field_data.csv")
    print("2. Update 03_generate_pyxis_files.py to use comprehensive data")
    print("3. Generate final Pyxis ingestion files")


if __name__ == "__main__":
    main()
