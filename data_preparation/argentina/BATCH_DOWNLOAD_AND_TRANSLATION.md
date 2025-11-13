# Batch Download and Translation Guide

Guide for downloading well production data by year (2009-2025) and translating year-suffixed files.

## New Features

### 1. Well Production Batch Download (2009-2025)
Download individual year files for well production data instead of the massive combined file.

### 2. Year-Suffixed File Translation
Translation script automatically detects and translates files with year suffixes:
- `produccin-de-petrleo-por-yacimiento_2024-2025.csv` → `oil_field_production_2024-2025_english.csv`
- `produccin-de-pozos-de-gas-y-petrleo-2023.csv` → `well_production_2023_english.csv`

---

## Download Script Usage

### Download Well Production for Specific Years

```bash
cd scripts

# Download well production for 2020-2024
pipenv run python 00_download_raw_data.py \
  --datasets well_production_by_year \
  --years 2020-2024

# Download for specific years only
pipenv run python 00_download_raw_data.py \
  --datasets well_production_by_year \
  --years 2023,2024

# Download all available years (2009-2025)
pipenv run python 00_download_raw_data.py \
  --datasets well_production_by_year
```

### Download Oil/Gas Field Production with Year Filter

```bash
# Download oil field production for 2020-2025 only
pipenv run python 00_download_raw_data.py \
  --datasets oil_field \
  --years 2020-2025

# Download both oil and gas for specific years
pipenv run python 00_download_raw_data.py \
  --datasets oil_field gas_field \
  --years 2024,2025
```

### Combined Download Example

```bash
# Download oil/gas field (filtered) + well production (by year)
pipenv run python 00_download_raw_data.py \
  --datasets oil_field gas_field well_production_by_year \
  --years 2020-2024
```

---

## Output Files

### Well Production by Year
Files are named with year suffix:
- `produccin-de-pozos-de-gas-y-petrleo-2009.csv`
- `produccin-de-pozos-de-gas-y-petrleo-2010.csv`
- ...
- `produccin-de-pozos-de-gas-y-petrleo-2025.csv`

### Oil/Gas Field with Year Filter
Files include year range:
- `produccin-de-petrleo-por-yacimiento_2024-2025.csv` (filtered)
- `produccin-de-gas-por-yacimiento_2020-2024.csv` (filtered)

---

## Translation Script Usage

The translation script **automatically detects and translates** all year-suffixed files.

### Translate All Files (Including Year-Suffixed)

```bash
cd scripts
pipenv run python 01_translate_all_raw_data.py
```

This will automatically:
1. Find all `produccin-de-petrleo-por-yacimiento*.csv` files (with or without year suffix)
2. Find all `produccin-de-gas-por-yacimiento*.csv` files
3. Find all `produccin-de-pozos-de-gas-y-petrleo-*.csv` files
4. Translate each with preserved year suffix

### Translation Output Examples

#### Oil Field Production
- Input: `produccin-de-petrleo-por-yacimiento_2024-2025.csv`
- Output: `oil_field_production_2024-2025_english.csv`

- Input: `produccin-de-petrleo-por-yacimiento.csv` (no suffix)
- Output: `oil_field_production_english.csv` (default from mapping)

#### Gas Field Production
- Input: `produccin-de-gas-por-yacimiento_2020-2024.csv`
- Output: `gas_field_production_2020-2024_english.csv`

#### Well Production
- Input: `produccin-de-pozos-de-gas-y-petrleo-2023.csv`
- Output: `well_production_2023_english.csv`

- Input: `produccin-de-pozos-de-gas-y-petrleo-2024.csv`
- Output: `well_production_2024_english.csv`

---

## Complete Workflow Example

### Scenario: Process 2020-2024 Data

#### Step 1: Download Raw Data

```bash
cd data_preparation/argentina/scripts

# Download oil/gas field production (filtered)
pipenv run python 00_download_raw_data.py \
  --datasets oil_field gas_field \
  --years 2020-2024

# Download well production by year
pipenv run python 00_download_raw_data.py \
  --datasets well_production_by_year \
  --years 2020-2024
```

**Result**:
```
raw/
├── produccin-de-petrleo-por-yacimiento_2020-2024.csv
├── produccin-de-gas-por-yacimiento_2020-2024.csv
├── produccin-de-pozos-de-gas-y-petrleo-2020.csv
├── produccin-de-pozos-de-gas-y-petrleo-2021.csv
├── produccin-de-pozos-de-gas-y-petrleo-2022.csv
├── produccin-de-pozos-de-gas-y-petrleo-2023.csv
└── produccin-de-pozos-de-gas-y-petrleo-2024.csv
```

#### Step 2: Translate All Files

```bash
pipenv run python 01_translate_all_raw_data.py
```

**Result**:
```
raw/translated/
├── oil_field_production_2020-2024_english.csv
├── gas_field_production_2020-2024_english.csv
├── well_production_2020_english.csv
├── well_production_2021_english.csv
├── well_production_2022_english.csv
├── well_production_2023_english.csv
└── well_production_2024_english.csv
```

#### Step 3: Process with Pyxis Pipeline

```bash
pipenv run python 05_generate_pyxis_monthly.py --year 2024 --months 1-12
```

---

## Command Reference

### Download Script

```bash
--datasets well_production_by_year    # Batch download 2009-2025
--datasets oil_field                  # Oil field production
--datasets gas_field                  # Gas field production
--years 2020-2024                     # Year range (download/filter)
--years 2023,2024,2025                # Specific years
--force                               # Re-download existing files
```

### Translation Script

No changes needed! Automatically detects year-suffixed files.

```bash
pipenv run python 01_translate_all_raw_data.py
```

Set `FULL_TRANSLATION = True` in script for full translation (line 256).

---

## File Naming Conventions

### Raw Files (Spanish)
- **No suffix**: Original file from portal
  - `produccin-de-petrleo-por-yacimiento.csv`
- **Year suffix**: Filtered or year-specific file
  - `produccin-de-petrleo-por-yacimiento_2024-2025.csv` (filtered)
  - `produccin-de-pozos-de-gas-y-petrleo-2023.csv` (year-specific)

### Translated Files (English)
- **No suffix**: From original file
  - `oil_field_production_english.csv`
- **Year suffix preserved**: From year-suffixed file
  - `oil_field_production_2024-2025_english.csv`
  - `well_production_2023_english.csv`

---

## Benefits

### 1. Reduced Download Size
- **Full oil field file**: ~414 MB
- **2024-2025 only**: ~28 MB (93% reduction)

### 2. Faster Processing
- Translate only years needed
- Smaller files = faster pipeline

### 3. Historical Analysis
- Download specific years for retrospective studies
- Compare data across years

### 4. Flexible Workflows
- Mix full files and year-specific files
- Translation script handles both seamlessly

---

## Troubleshooting

### "No files matching pattern"
Check that files exist in `raw/` directory with correct naming:
```bash
ls raw/produccin-de-petrleo-por-yacimiento*.csv
ls raw/produccin-de-pozos-de-gas-y-petrleo-*.csv
```

### Year-Suffixed Translation Not Working
Ensure filename format is correct:
- ✅ `filename_2024.csv` or `filename_2024-2025.csv`
- ❌ `filename-2024.csv` or `filename.2024.csv`

### Batch Download Failed
Check specific year in output:
```
Failed years: 2015, 2016
```
Try downloading failed years individually with `--force`.

---

## Advanced Usage

### Download Only Missing Years

```bash
# Check what you have
ls raw/produccin-de-pozos-de-gas-y-petrleo-*.csv

# Download only missing years
pipenv run python 00_download_raw_data.py \
  --datasets well_production_by_year \
  --years 2009,2010,2011  # Only years not present
```

### Mix Full and Filtered Files

```bash
# Download full oil field (all years)
curl -O http://datos.energia.gob.ar/.../produccin-de-petrleo-por-yacimiento.csv

# Download filtered gas field (recent years only)
pipenv run python 00_download_raw_data.py \
  --datasets gas_field \
  --years 2020-2025

# Translation script handles both!
pipenv run python 01_translate_all_raw_data.py
```

---

**Last Updated**: November 12, 2025
**Status**: Production Ready
