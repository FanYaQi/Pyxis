# Pyxis Data Preparation Pipeline

This directory contains data preparation pipelines for transforming country-specific raw data into Pyxis-compatible formats for ingestion.

## Overview

The data preparation pipeline:
1. Cleans and standardizes raw data from various sources
2. Aggregates data to appropriate granularity (field, well, etc.)
3. Enriches data with spatial information (geometry, H3 indices)
4. Converts units to OPGEE standards
5. Generates Pyxis-compatible CSV and configuration JSON files

## Structure

```
data_preparation/
├── README.md                    # This file
├── Pipfile                      # Isolated Python dependencies
├── .gitignore                   # Exclude raw data and outputs
├── utils/                       # Shared utilities
│   ├── h3_utils.py             # H3 spatial indexing
│   ├── geometry_utils.py       # Geometry conversions
│   └── pyxis_mappings.py       # OPGEE attribute mappings
└── argentina/                   # Argentina-specific pipeline
    ├── config/                  # Configuration files
    │   ├── column_mappings.json
    │   └── pyxis_config_template.json
    ├── scripts/                 # Processing scripts
    │   ├── 01_aggregate_wells_to_fields.py
    │   ├── 02_merge_with_geometry.py
    │   ├── 03_generate_pyxis_files.py
    │   └── run_pipeline.py
    ├── raw/                     # Place raw data files here (gitignored)
    └── output/                  # Generated output files (gitignored)
```

## Setup

### 1. Install Dependencies

This pipeline uses an **isolated pipenv environment** separate from the Pyxis backend:

```bash
cd data_preparation
pipenv install
```

### 2. Activate Environment

```bash
pipenv shell
```

Or run commands with `pipenv run`:

```bash
pipenv run python argentina/scripts/run_pipeline.py
```

## Usage: Argentina Pipeline

### Step 1: Prepare Raw Data

Place the following files in `argentina/raw/`:
- `well_prod_2025_cleaned.csv` - Monthly well production data (already translated from Spanish)
- `AR_field_shape_cleaned.csv` - Field geometry and metadata

### Step 2: Run Pipeline

Option A - Run complete pipeline:
```bash
cd argentina/scripts
pipenv run python run_pipeline.py
```

Option B - Run individual scripts:
```bash
cd argentina/scripts
pipenv run python 01_aggregate_wells_to_fields.py
pipenv run python 02_merge_with_geometry.py
pipenv run python 03_generate_pyxis_files.py
```

### Step 3: Review Outputs

Generated files in `argentina/output/`:
- `field_monthly_production.csv` - Aggregated field-level data
- `field_production_with_geometry.csv` - Merged with geometry
- `argentina_2025_pyxis_data.csv` - **Final Pyxis data CSV**
- `argentina_2025_pyxis_config.json` - **Pyxis configuration JSON**

### Step 4: Upload to Pyxis

Use the Pyxis API to upload the generated files:

```bash
# 1. Start Pyxis backend
cd ../backend
pipenv run uvicorn app.main:app --reload

# 2. Create data source (if not exists)
curl -X POST "http://localhost:8000/api/v1/data-sources/" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Argentina National Production Data",
    "description": "Monthly oil and gas production data from Argentina",
    "source_type": "government",
    "country": "Argentina"
  }'

# 3. Upload data entry
curl -X POST "http://localhost:8000/api/v1/data-entries/" \
  -F "source_id=<source_id_from_step_2>" \
  -F "granularity=field" \
  -F "alias=Argentina 2025 Production" \
  -F "data_file=@argentina/output/argentina_2025_pyxis_data.csv" \
  -F "config_file=@argentina/output/argentina_2025_pyxis_config.json"

# 4. Trigger processing
curl -X POST "http://localhost:8000/api/v1/data-entries/<data_entry_id>/process"
```

## Processing Details

### Script 1: Aggregate Wells to Fields
- Groups well-level data by field ID and month
- Sums production volumes (oil, gas, water)
- Counts wells per field
- Calculates ratios (GOR, WOR)
- Determines functional unit (oil vs gas field)

### Script 2: Merge with Geometry
- Joins production data with field geometries
- Converts GeoJSON to WKT format (Pyxis standard)
- Generates H3 spatial indices for field centroids
- Extracts centroid coordinates

### Script 3: Generate Pyxis Files
- Applies column mappings (Argentina → OPGEE attributes)
- Converts units:
  - Oil: m³ → barrels (×6.29)
  - Gas: km³ → m³ (×1e9)
- Generates temporal fields (start_date, end_date from year/month)
- Creates Pyxis configuration JSON with:
  - Data metadata
  - Spatial configuration
  - Temporal configuration
  - Column mappings

## Unit Conversions

| Attribute | Argentina Unit | OPGEE Unit | Conversion |
|-----------|---------------|------------|------------|
| Oil production | m³ | bbl | ×6.28981 |
| Gas production | km³ | m³ | ×1,000,000,000 |
| Water production | m³ | m³ | (no change) |
| Depth | m | m | (no change) |

## Adding New Countries

To add a new country pipeline:

1. Create country directory:
```bash
mkdir -p <country>/config <country>/scripts <country>/raw <country>/output
```

2. Create configuration files in `<country>/config/`:
   - `column_mappings.json` - Map country columns to OPGEE attributes

3. Create processing scripts in `<country>/scripts/`:
   - Customize based on data structure
   - Reuse utilities from `../utils/`

4. Update `.gitignore` if needed

5. Document in this README

## Dependencies

- **pandas**: Data manipulation
- **geopandas**: Geospatial data processing
- **h3**: H3 spatial indexing
- **shapely**: Geometry operations
- **pyproj**: Coordinate reference system transformations
- **python-dateutil**: Date handling

## Notes

- Raw data files are **gitignored** to avoid committing large files
- Output files are **gitignored** as they can be regenerated
- Configuration files **are tracked** in git
- Each country has an isolated pipeline but shares common utilities
- The pipenv environment is **separate from the backend** to avoid conflicts

## Troubleshooting

### Issue: Module not found
**Solution**: Make sure you're in the pipenv environment:
```bash
cd data_preparation
pipenv shell
```

### Issue: Input file not found
**Solution**: Check that raw data files are in `<country>/raw/` with correct names

### Issue: Column not found in CSV
**Solution**: Review `column_mappings.json` and ensure source columns exist in your data

### Issue: Unit conversion errors
**Solution**: Check for null/zero values in production columns

## Contact

For questions or issues, please refer to the main Pyxis repository documentation.
