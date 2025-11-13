# Download Script Usage Guide

Quick reference for using `00_download_raw_data.py` with year filtering.

## Basic Usage

### Download without filtering (full dataset)
```bash
cd scripts
pipenv run python 00_download_raw_data.py --datasets oil_field
```
**Output**: `produccin-de-petrleo-por-yacimiento.csv` (~414 MB)

### Download with year filtering
```bash
pipenv run python 00_download_raw_data.py --datasets oil_field --years 2024,2025
```
**Output**: `produccin-de-petrleo-por-yacimiento_2024-2025.csv` (much smaller)

### Download year range
```bash
pipenv run python 00_download_raw_data.py --datasets gas_field --years 2020-2025
```
**Output**: `produccin-de-gas-por-yacimiento_2020-2025.csv`

## Filename Convention

When using `--years` filter:
- **Without filter**: Original portal filename (e.g., `produccin-de-petrleo-por-yacimiento.csv`)
- **With filter**: Filename + year range (e.g., `produccin-de-petrleo-por-yacimiento_2024-2025.csv`)

Examples:
- `--years 2024`: → `filename_2024.csv`
- `--years 2024,2025`: → `filename_2024-2025.csv`
- `--years 2020-2025`: → `filename_2020-2025.csv`

## Available Datasets

### Supports Year Filtering ✅
These datasets have `supports_year_filter: True` and will be filtered by the `anio` (year) column:

1. **oil_field** - Oil field production
   - Original: `produccin-de-petrleo-por-yacimiento.csv`
   - Filtered: `produccin-de-petrleo-por-yacimiento_YYYY-YYYY.csv`

2. **gas_field** - Gas field production
   - Original: `produccin-de-gas-por-yacimiento.csv`
   - Filtered: `produccin-de-gas-por-yacimiento_YYYY-YYYY.csv`

### No Year Filtering ⚠️
These datasets will download the full file regardless of `--years` parameter:

- **well_production** - Well production (Capítulo IV)
- **well_characteristics** - Well characteristics
- **fracture_completion** - Fracture data
- Other datasets without the filter flag

## Command-Line Options

```bash
--datasets oil_field gas_field    # Specific datasets to download
--years 2024,2025                  # Year filter (comma or range)
--force                            # Re-download even if file exists
--discover                         # Search portal for dataset IDs
--output-dir /path/to/dir          # Custom output directory
```

## Examples

### Download oil + gas for 2024-2025
```bash
pipenv run python 00_download_raw_data.py \
  --datasets oil_field gas_field \
  --years 2024-2025
```

### Re-download with different year range
```bash
pipenv run python 00_download_raw_data.py \
  --datasets oil_field \
  --years 2023-2025 \
  --force
```

### Download single year
```bash
pipenv run python 00_download_raw_data.py \
  --datasets gas_field \
  --years 2025
```
**Output**: `produccin-de-gas-por-yacimiento_2025.csv`

## How Year Filtering Works

1. **Download**: Full CSV downloaded to temp file
2. **Filter**: Pandas reads CSV and filters by `anio` column
3. **Save**: Filtered data saved with year suffix in filename
4. **Cleanup**: Temp file deleted
5. **Report**: Shows original size → filtered size reduction

### Example Output
```
======================================================================
Dataset: Producción de petróleo por yacimiento
======================================================================
  Year filter enabled: [2024, 2025]
  Output file: produccin-de-petrleo-por-yacimiento_2024-2025.csv
  Using direct URL: http://datos.energia.gob.ar/...
  Downloading... 100.0% (414.2 MB)
  Filtering by years: [2024, 2025]
  Reading full file...
    Original: 2,456,789 rows (414.2 MB)
    Filtered: 168,432 rows (28.5 MB)
    Reduction: 93.1% fewer rows, 93.1% smaller
  ✓ Downloaded and filtered: produccin-de-petrleo-por-yacimiento_2024-2025.csv (28.5 MB)
```

## Troubleshooting

### "Year column 'anio' not found"
The dataset doesn't have a year column or uses a different name. The script will show available columns.

### File already exists
Use `--force` to re-download:
```bash
pipenv run python 00_download_raw_data.py --datasets oil_field --years 2024-2025 --force
```

### Year filter ignored
Check if dataset has `"supports_year_filter": True` in the script. If not, year filtering won't work.

### Download timeout
Large files (400+ MB) may take several minutes. The script has a 300-second (5 minute) timeout by default.

## Integration with Translation Pipeline

The filtered files work seamlessly with your existing translation pipeline:

1. **Download** filtered data:
   ```bash
   pipenv run python 00_download_raw_data.py --datasets oil_field --years 2024-2025
   ```

2. **Translate** using existing config:
   ```bash
   pipenv run python 01_translate_all_raw_data.py
   ```
   Your translation config will automatically find and process the filtered file.

3. **Process** as normal:
   ```bash
   pipenv run python 05_generate_pyxis_monthly.py --year 2025 --months 1-8
   ```

## Notes

- **Original filenames preserved**: Uses exact portal filenames for compatibility with translation configs
- **Year suffix only when filtering**: No suffix added if `--years` not specified
- **Automatic cleanup**: Temp files deleted after filtering
- **Statistics shown**: Always shows size reduction when filtering
- **Rate limiting**: 1 second delay between multiple dataset downloads

---

**Last Updated**: November 12, 2025
