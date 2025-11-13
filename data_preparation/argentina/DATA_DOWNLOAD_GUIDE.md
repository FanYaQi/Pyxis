# Argentina Energy Data Download Guide

This guide explains how to download raw data from Argentina's Ministry of Energy data portal using the provided download script.

## Quick Start

### 1. Install Dependencies
```bash
cd data_preparation
pipenv install requests
```

### 2. Download All Available Data
```bash
cd argentina/scripts
pipenv run python 00_download_raw_data.py
```

### 3. Download Specific Datasets
```bash
pipenv run python 00_download_raw_data.py --datasets well_production oil_field gas_field
```

## Data Source

**Portal**: [datos.energia.gob.ar](http://datos.energia.gob.ar)
**API**: CKAN 3.x
**API Docs**: http://datos.energia.gob.ar/acerca/ckan

## Available Datasets

The download script supports 12 datasets required for Pyxis data preparation:

### ✅ Confirmed Working

1. **well_production** - Producción de petróleo y gas por pozo (Capítulo IV)
   - Direct URL: Available
   - Resource ID: `cb5c0f04-7835-45cd-b982-3e25ca7d7751`
   - Output: `well_production_full.csv`
   - Size: ~200-500 MB
   - Description: Monthly well production by extraction method

### 🔍 Needs Discovery

The following datasets need their resource IDs discovered from the portal:

2. **oil_field** - Oil field production (monthly by recovery type)
3. **gas_field** - Gas field production (monthly by pressure category)
4. **well_characteristics** - Well characteristics (static metadata)
5. **fracture_completion** - Fracture completion (hydraulic fracturing details)
6. **field_shapes** - Field shapes & depth (GeoJSON boundaries)
7. **daily_oil** - Daily oil production (average daily rates)
8. **daily_gas** - Daily gas production (average daily rates)
9. **formation_vintage** - Field production by formation/vintage (includes injection)
10. **plant_gas** - Plant gas processing (includes flaring)
11. **historical_gas_wells** - Historical gas wells (pre-2009 well counts)
12. **historical_oil_wells** - Historical oil wells (pre-2009 well counts)

## Discovery Mode

To find resource IDs for datasets not yet configured:

```bash
pipenv run python 00_download_raw_data.py --discover
```

This will search the data portal for relevant datasets and display:
- Dataset ID (package ID)
- Dataset name
- Resource IDs for each file (CSV, SHP, etc.)
- Resource names and formats

### Example Discovery Output

```
Searching for datasets: 'producción petróleo yacimiento'
  ✓ Found 3 datasets

  [1] Producción de hidrocarburos - Yacimientos
      ID: 7378520e-4d10-48a9-92e9-7e20e69a8277
      Name: produccion-hidrocarburos-yacimientos
      Resources: 2
        - Producción Hidrocarburos Yacimientos (CSV)
          Resource ID: 6130ac5d-e78e-4aef-9925-030db6434c56
```

## Finding Resource IDs Manually

### Method 1: Web Browser

1. Go to [datos.energia.gob.ar](http://datos.energia.gob.ar)
2. Search for dataset (e.g., "producción petróleo yacimiento")
3. Click on dataset
4. Right-click "Download" button → Copy link
5. Extract resource ID from URL:
   ```
   http://datos.energia.gob.ar/dataset/.../resource/[RESOURCE_ID]/download/file.csv
   ```

### Method 2: CKAN API

Use the package_show API endpoint:

```bash
curl "http://datos.energia.gob.ar/api/3/action/package_show?id=produccion-hidrocarburos-yacimientos" | jq '.result.resources[] | {name, id, url}'
```

Example response:
```json
{
  "name": "Producción Hidrocarburos Yacimientos",
  "id": "6130ac5d-e78e-4aef-9925-030db6434c56",
  "url": "http://datos.energia.gob.ar/.../download/file.csv"
}
```

## Updating the Script

Once you find resource IDs, update `00_download_raw_data.py`:

```python
"oil_field": {
    "name": "Producción de petróleo por yacimiento",
    "package_id": "7378520e-4d10-48a9-92e9-7e20e69a8277",
    "resource_id": "6130ac5d-e78e-4aef-9925-030db6434c56",
    "direct_url": "http://datos.energia.gob.ar/.../download/file.csv",
    "output_file": "oil_field_production.csv",
    "description": "Oil field production - monthly by recovery type"
},
```

## Command-Line Options

```bash
# Download all datasets
pipenv run python 00_download_raw_data.py

# Download specific datasets
pipenv run python 00_download_raw_data.py --datasets well_production oil_field

# Force re-download even if files exist
pipenv run python 00_download_raw_data.py --force

# Specify custom output directory
pipenv run python 00_download_raw_data.py --output-dir /path/to/output

# Discovery mode - search for dataset IDs
pipenv run python 00_download_raw_data.py --discover

# Combine options
pipenv run python 00_download_raw_data.py --datasets well_production --force --output-dir ../raw
```

## Common Datasets on Portal

Based on discovery, here are the main datasets available:

### 1. Well Production (Capítulo IV)
- **Package**: `produccion-de-petroleo-y-gas-por-pozo`
- **Resource ID**: `cb5c0f04-7835-45cd-b982-3e25ca7d7751`
- **File**: `capitulo-iv-pozos.csv`
- **Contents**: Monthly production by well, field, concession, province
- **Columns**: Oil (m³), Gas (Miles de m³), Water (m³), extraction method

### 2. Field Production (Hydrocarburos Yacimientos)
- **Package**: `produccion-hidrocarburos-yacimientos`
- **Resource ID**: `6130ac5d-e78e-4aef-9925-030db6434c56`
- **File**: CSV format
- **Contents**: Aggregated production by field
- **Note**: May combine oil and gas data

### 3. Field Production by Depth
- **Package**: `produccion-hidrocarburos-yacimientos-segun-profundidad-promedio`
- **Resource ID**: `3f13c499-cb5a-4998-a87a-c87d8367caec`
- **File**: CSV format
- **Contents**: Production by field with average depth
- **Bonus**: Includes depth information

## Troubleshooting

### SSL Certificate Error

The datos.energia.gob.ar portal has SSL certificate issues. The script automatically disables SSL verification:

```python
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
```

If you see warnings, they are expected and can be ignored.

### Download Timeout

Large files may timeout. Increase timeout in the script:

```python
def download_file(url, output_path, chunk_size=8192):
    response = requests.get(url, stream=True, timeout=600, verify=False)  # 10 min timeout
```

### Rate Limiting

The script includes 1-second delays between downloads. If you get rate-limited:

```python
time.sleep(2)  # Increase delay to 2 seconds
```

### File Not Found (404)

Some datasets may be moved or renamed. Use discovery mode to find updated resource IDs:

```bash
pipenv run python 00_download_raw_data.py --discover
```

### Dataset Not Available via API

Some datasets may not be available via direct download. Manual options:

1. **Web Download**: Use browser to download from datos.energia.gob.ar
2. **OData Endpoint**: Some datasets have OData endpoints:
   ```
   http://datos.energia.gob.ar/datastore/odata3.0/[RESOURCE_ID]
   ```
3. **Contact Portal**: Email: datos@energia.gob.ar

## Known Dataset Mappings (from existing raw/ files)

If you have existing files in `raw/`, here's what they correspond to:

| Your File | Portal Dataset | Likely Resource |
|-----------|----------------|-----------------|
| `producción-de-petróleo-por-yacimiento.csv` | oil_field | TBD |
| `producción-de-gas-por-yacimiento.csv` | gas_field | TBD |
| `producción-de-pozos-YYYY.csv` | well_production | cb5c0f04-... |
| `características-de-pozos.csv` | well_characteristics | TBD |
| `completamiento-fractura-hidráulica.csv` | fracture_completion | TBD |
| `áreas-de-yacimientos.csv` | field_shapes | TBD |
| `producción-diaria-petróleo.csv` | daily_oil | TBD |
| `producción-diaria-gas.csv` | daily_gas | TBD |
| `producción-por-formación-añada.csv` | formation_vintage | TBD |
| `procesamiento-gas-plantas.csv` | plant_gas | TBD |
| `pozos-gas-históricos.csv` | historical_gas_wells | TBD |
| `pozos-petróleo-históricos.csv` | historical_oil_wells | TBD |

## Alternative: Using the Portal Website

If API access is problematic, download manually:

1. Visit [datos.energia.gob.ar](http://datos.energia.gob.ar)
2. Search for each dataset
3. Download CSV files
4. Save to `data_preparation/argentina/raw/`
5. Rename to match expected filenames (see table above)

## Next Steps After Download

Once you have the raw data downloaded:

1. **Translate data** (Spanish → English):
   ```bash
   cd scripts
   pipenv run python 01_translate_all_raw_data.py
   ```

2. **Generate Pyxis fields**:
   ```bash
   pipenv run python 05_generate_pyxis_monthly.py --year 2025 --months 1-8
   ```

3. **Generate fracture well data**:
   ```bash
   pipenv run python 06_generate_fracture_well_data.py
   ```

## API Rate Limits

**datos.energia.gob.ar** CKAN API:
- **No authentication required** for public datasets
- **Rate limit**: Not explicitly documented, but reasonable (1 req/sec recommended)
- **File size limits**: None observed
- **Availability**: 24/7 (subject to maintenance)

## Additional Resources

- **CKAN API Docs**: https://docs.ckan.org/en/latest/api/
- **Portal Contact**: datos@energia.gob.ar
- **Portal GitHub**: https://github.com/datosenergia
- **Example Repo**: https://github.com/datosenergia/produccion-de-petroleo-y-gas-por-pozo

## Script Maintenance

To update resource IDs as they change:

1. Run discovery mode quarterly:
   ```bash
   pipenv run python 00_download_raw_data.py --discover > dataset_discovery.txt
   ```

2. Compare with previous discovery output

3. Update DATASETS dictionary in `00_download_raw_data.py`

4. Test with `--datasets [key]` before running full download

---

**Last Updated**: November 12, 2025
**Maintainer**: Pyxis Team
**Issues**: Report at repository issues page
