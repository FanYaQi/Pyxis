# Backend Utility Scripts

This directory contains general-purpose utility scripts for database maintenance and API operations.

## Available Scripts

### `generate_opgee_csv.py`
Generates OPGEE-compatible CSV files for specified country/date ranges via the API.

**Usage:**
```bash
python generate_opgee_csv.py
```

## Guidelines

- **DO NOT** add country-specific scripts here - those belong in `data_preparation/<country>/scripts/`
- **DO NOT** add temporary test files here - use pytest in `tests/` instead
- **DO NOT** add one-off processing scripts - these should be deleted after use
- **DO** add reusable utilities that work across all countries/datasets
- **DO** document scripts with docstrings and update this README

## Country-Specific Scripts

For country-specific data processing and upload scripts, see:
- Argentina: `data_preparation/argentina/scripts/`
- Global sources: `data_preparation/global_sources/scripts/`
