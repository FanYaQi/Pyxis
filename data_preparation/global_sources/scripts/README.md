# Global Sources Data Download Scripts

This directory contains scripts for downloading data from various global sources including satellite methane data, commercial datasets, and third-party emissions databases.

## Available Scripts

### `download_imeo_data.py`
Downloads methane emissions data from IMEO (International Methane Emissions Observatory).

**Data Sources:**
- IMEO Emissions Database: Global methane emissions for oil & gas sector
- IMEO Facilities Database: Infrastructure and facility metadata

**Usage:**
```bash
# Download all global data
python download_imeo_data.py

# Download Argentina-specific data
python download_imeo_data.py --country ARG

# Download data for specific date range
python download_imeo_data.py --country ARG --start-date 2021-01-01 --end-date 2021-12-31

# Save as JSON instead of CSV
python download_imeo_data.py --format json
```

**Output:** Files saved to `data_preparation/global_sources/methane_raw_imeo/`

### `download_carbon_mapper_plumes.py`
Downloads methane plume detection data from Carbon Mapper satellite observations.

**Usage:**
```bash
python download_carbon_mapper_plumes.py
```

### `download_carbon_mapper_scenes.py`
Downloads Carbon Mapper scene metadata for coverage analysis.

### `extract_cd_fields.py`
Extracts and processes commercial dataset (CD) field data into Pyxis format.

**Usage:**
```bash
python extract_cd_fields.py
```

### `extract_gogi_fields.py`
Extracts and processes GOGI (Global Oil & Gas Intelligence) field data into Pyxis format.

**Usage:**
```bash
python extract_gogi_fields.py
```

### `upload_global_source_to_api.py`
Uploads processed global source data to the Pyxis API.

**Usage:**
```bash
# Upload CD data
python upload_global_source_to_api.py --source cd --country Argentina --email user@example.com --password xxx

# Upload GOGI data
python upload_global_source_to_api.py --source gogi --country Argentina --email user@example.com --password xxx
```

## Data Pipeline Workflow

### For Static Field Data (CD, GOGI)
1. **Extract**: Run `extract_cd_fields.py` or `extract_gogi_fields.py`
2. **Review**: Check output files in `output/argentina/`
3. **Upload**: Use `upload_global_source_to_api.py` to upload to Pyxis

### For Methane Emissions (IMEO, Carbon Mapper)
1. **Download**: Run download scripts to fetch raw data
2. **Process**: (Future) Transform to Pyxis format
3. **Integrate**: (Future) Match to existing fields via spatial join

## Output Directory Structure

```
global_sources/
├── scripts/                     # This directory
├── methane_raw_imeo/            # Raw IMEO methane data
├── flaring/                     # Carbon Mapper plume data
└── output/
    └── argentina/
        ├── argentina_pyxis_static_fields_cd.csv
        ├── argentina_pyxis_static_fields_cd_config.json
        ├── argentina_pyxis_static_fields_gogi.csv
        └── argentina_pyxis_static_fields_gogi_config.json
```

## API Keys and Authentication

- **IMEO**: API token configured in `download_imeo_data.py`
- **Carbon Mapper**: Uses public API (no auth required)
- **Pyxis Upload**: Requires user email/password

## Guidelines

- Store raw downloaded data in timestamped files
- Always include data provenance metadata
- Document data source URLs and access dates
- Use consistent naming: `{source}_{datatype}_{country}_{timestamp}.{ext}`
