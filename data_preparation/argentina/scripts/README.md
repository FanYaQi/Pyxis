# Argentina Data Processing Scripts

This directory contains scripts for processing Argentina oil and gas field data through the complete pipeline from raw data download to Pyxis format generation and API upload.

## Pipeline Overview

```
Raw Data → Translation → Cleaning → Merging → Field Aggregation → Pyxis Format → API Upload
```

## Pipeline Scripts (Run in Order)

### 1. Data Download & Translation
- **`00_download_raw_data.py`** - Download raw data from Argentina government sources
- **`01_translate_all_raw_data.py`** - Translate Spanish field names and metadata to English

### 2. Data Cleaning & Merging
- **`00_clean_and_merge_sources.py`** - Clean and merge oil/gas production data
- **`02_clean_and_merge_translated.py`** - Merge translated production datasets
- **`00a_add_well_counts_and_geometry.py`** - Add well counts and spatial geometry
- **`02_merge_with_geometry.py`** - Merge production data with field geometries

### 3. Field Aggregation & Enhancement
- **`01_aggregate_wells_to_fields.py`** - Aggregate well-level data to field-level
- **`04_create_comprehensive_field_data.py`** - Create comprehensive field dataset with all attributes
- **`06_generate_fracture_well_data.py`** - Generate fracture/completion data

### 4. Pyxis Format Generation
- **`03_generate_pyxis_files.py`** - Generate Pyxis-compatible CSV + config JSON
- **`06_generate_static_pyxis_file.py`** - Generate static field attributes in Pyxis format
- **`05_generate_pyxis_monthly.py`** - Generate monthly time-series in Pyxis format

### 5. Visualization & Analysis
- **`07_generate_summary_plots.py`** - Generate summary statistics and plots

### 6. API Upload & Processing
- **`upload_argentina_data.py`** - **Main upload script** - Automated batch upload and processing
- **`07_upload_static_to_api.py`** - Upload static field data to Pyxis API
- **`08_upload_monthly_to_api.py`** - Upload monthly time-series to Pyxis API

### 7. Database Maintenance
- **`fix_argentina_geometries.py`** - Fix geometry projection issues in database

## Automation Scripts

### `run_pipeline.py`
Runs the complete pipeline from raw data to Pyxis files.

**Usage:**
```bash
python run_pipeline.py
```

### `upload_argentina_data.py` ⭐ RECOMMENDED
**End-to-end upload and batch processing script** using the new batch processing API.

**Features:**
- Logs in and gets authentication token
- Creates data sources with quality scores (Argentina Gov, CD, GOGI)
- Uploads all Argentina data entries (static + time-series)
- Batch processes static data in quality order (Gov → CD → GOGI)
- Batch processes time-series with source-based matching
- Prints detailed processing results and statistics

**Usage:**
```bash
python upload_argentina_data.py --email yaqif@stanford.edu --password yaqiyaqi
```

**What it uploads:**
1. Gov Static (2009-2024) - 1,550 fields
2. CD Static - Commercial dataset
3. GOGI Static - Third-party dataset
4. Time-Series 2021 - 1,294 monthly records
5. Time-Series 2025 Q1 - 3,793 monthly records

## Input Data Structure

```
argentina/
├── raw_data/                    # Raw government data (Spanish)
├── translated/                  # Translated data (English)
├── output/
│   ├── argentina_pyxis_static_fields.csv
│   ├── argentina_pyxis_static_fields_config.json
│   ├── argentina_pyxis_fields_2021.csv
│   └── argentina_pyxis_fields_2025_Q1.csv
└── scripts/                     # This directory
```

## Output Files

### Static Field Data
- `argentina_pyxis_static_fields.csv` - Static attributes for all fields
- `argentina_pyxis_static_fields_config.json` - Configuration mapping

### Time-Series Data
- `argentina_pyxis_fields_2021.csv` - Monthly production data for 2021
- `argentina_pyxis_fields_2025_Q1.csv` - Monthly production data for 2025 Q1

## Key Attributes Captured

**Static Attributes:**
- Field identification (name, country, field_id)
- Geospatial data (geometry, coordinates, H3 index)
- Reservoir properties (depth, age, API gravity, temperature, pressure)
- Production methods (downhole pump, water/gas flooding, gas lifting)
- Gas composition (N2, CO2, CH4, H2S)
- OPGEE-compatible attributes (65+ fields)

**Time-Series Attributes:**
- Monthly production (oil, gas)
- Production ratios (GOR, WOR, WIR, GLIR)
- Well counts (producing wells, water injection wells)
- Operational parameters

## Data Sources

1. **Argentina Government** - Secretary of Energy (SEE)
   - Quality score: 4.5/5
   - Coverage: 2009-2024
   - Attributes: Production, wells, reservoir properties

2. **Commercial Dataset (CD)**
   - Quality score: 3.5/5
   - Coverage: Comprehensive field attributes

3. **GOGI** - Global Oil & Gas Intelligence
   - Quality score: 3.0/5
   - Coverage: Basic field metadata

## Guidelines

- Run pipeline scripts in numerical order (00 → 01 → 02 → ...)
- Always check output files before uploading to API
- Use `upload_argentina_data.py` for production uploads (preferred)
- Use individual upload scripts (07, 08) for testing specific datasets
- Keep data provenance metadata in config JSON files
