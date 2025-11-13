"""
Translate well production for specific years only
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from translate_all_raw_data import translate_year_suffixed_files, load_all_mappings

# Paths
base_dir = Path(__file__).parent.parent
raw_dir = base_dir / "raw"
translated_dir = raw_dir / "translated"
config_dir = base_dir / "config"

# Load mappings
mappings = load_all_mappings(config_dir)

# Specify years to translate
YEARS_TO_TRANSLATE = [2020, 2021, 2022, 2023, 2024]  # Change this list as needed
FULL_TRANSLATION = True  # Set to False for sample translation

print(f"Translating well production for years: {YEARS_TO_TRANSLATE}")
print(f"Full translation: {FULL_TRANSLATION}\n")

# Create pattern for specific years
for year in YEARS_TO_TRANSLATE:
    pattern = f"produccin-de-pozos-de-gas-y-petrleo-{year}.csv"
    print(f"\n{'='*70}")
    print(f"YEAR {year}")
    print(f"{'='*70}")
    
    translate_year_suffixed_files(
        raw_dir=raw_dir,
        translated_dir=translated_dir,
        mapping=mappings['well_production_mapping'],
        pattern=pattern,
        output_prefix="well_production",
        full_translation=FULL_TRANSLATION,
        max_rows_default=100000
    )

print("\n✅ Translation complete for specified years")
