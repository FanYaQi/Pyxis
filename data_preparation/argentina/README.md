# Argentina Oil & Gas Data Preparation Pipeline

Transform Argentina's raw oil & gas production data (Spanish) into Pyxis-compatible format (English with meaningful O&G terminology).

## Overview

This pipeline processes raw Argentina government data through two major steps:
1. **Translation** - Convert Spanish files to English with meaningful oil & gas terminology
2. **Transformation** - Aggregate, calculate metrics, and format for Pyxis ingestion

## Pipeline Workflow

```
┌─────────────────────────────────────────────────────────────┐
│                    STEP 1: TRANSLATION                       │
│                  (01_translate_all_raw_data.py)              │
└─────────────────────────────────────────────────────────────┘

┌──────────────────────┐                    ┌──────────────────────┐
│  Raw Spanish Files   │                    │  Translation         │
│  (raw/)              │──────────────────▶ │  Mappings            │
│                      │                    │  (config/            │
│ • produccin-de-      │                    │   translation_       │
│   petrleo...csv      │                    │   mappings/)         │
│ • produccin-de-      │                    │                      │
│   gas...csv          │                    │ • Column names       │
│ • produccin-de-      │                    │ • Concept values     │
│   pozos...csv        │                    │ • Well status        │
│ • capitulo-iv-       │                    │ • Extraction methods │
│   pozos.csv          │                    │ • O&G terminology    │
└──────────────────────┘                    └──────────────────────┘
           │                                           │
           │                                           │
           └───────────────┬───────────────────────────┘
                           │
                           ▼
              ┌─────────────────────────┐
              │  Translated English     │
              │  Files                  │
              │  (raw/translated/)      │
              │                         │
              │ • oil_field_production_ │
              │   english.csv           │
              │ • gas_field_production_ │
              │   english.csv           │
              │ • well_production_      │
              │   {year}_english.csv    │
              │ • well_characteristics_ │
              │   english.csv           │
              └─────────────────────────┘
                           │
                           │
┌──────────────────────────┼──────────────────────────────────────┐
│                    STEP 2: TRANSFORMATION                       │
│               (02_clean_and_merge_translated.py)                │
└─────────────────────────────────────────────────────────────────┘
                           │
                           ▼
              ┌────────────────────────────┐
              │  Process & Aggregate:      │
              │                            │
              │  1. Pivot LONG→WIDE        │
              │  2. Merge oil + gas        │
              │  3. Calculate API gravity  │
              │  4. Classify functional    │
              │     unit (oil/gas)         │
              │  5. Calculate ratios       │
              │     (GOR, WOR, WIR, GLIR)  │
              │  6. Detect EOR methods     │
              │  7. Aggregate well counts  │
              │  8. Add geometry & depth   │
              │  9. Generate temporal      │
              │     fields                 │
              └────────────────────────────┘
                           │
                           ▼
              ┌─────────────────────────────────┐
              │  Final Output for Pyxis         │
              │  (output/)                      │
              │                                 │
              │  field_production_complete.csv  │
              │  • Field-level monthly data     │
              │  • 44 columns                   │
              │  • English names                │
              │  • OPGEE-compatible units       │
              │  • Ready for Pyxis API          │
              └─────────────────────────────────┘
```

## Quick Start

### 1. Setup Environment

```bash
cd /path/to/Pyxis/data_preparation
pipenv install
pipenv shell
```

### 2. Copy Raw Data Files

Place these files in `argentina/raw/`:

```bash
cd argentina/raw

# Required files:
# - produccin-de-petrleo-por-yacimiento.csv  (oil field production)
# - produccin-de-gas-por-yacimiento.csv      (gas field production)
# - produccin-de-pozos-de-gas-y-petrleo-2025.csv  (well production)
# - capitulo-iv-pozos.csv  (well characteristics)
```

### 3. Run Translation (Step 1)

```bash
cd argentina/scripts
python 01_translate_all_raw_data.py
```

This creates translated English files in `raw/translated/`

**First run uses SAMPLES** (for testing). To translate FULL files:
- Edit `01_translate_all_raw_data.py`
- Set `FULL_TRANSLATION = True` (line ~195)
- Re-run

### 4. Run Transformation (Step 2)

```bash
python 02_clean_and_merge_translated.py
```

This generates: `output/field_production_complete.csv`

### 5. Review Output

```bash
head output/field_production_complete.csv
wc -l output/field_production_complete.csv
```

## Translation Mappings

Translation mappings are defined in `config/translation_mappings/`:

### oil_field_production_mapping.json
- **Column names**: Spanish → English
- **Concept values**: Meaningful O&G terminology
  - `Producción Primaria (m3)` → `primary_production`
  - `Producción Secundaria (m3)` → `secondary_production`
  - `Producción por Recuperación Asistida (m3)` → `tertiary_eor_production`
  - `Inyección de Agua (m3)` → `water_injection`
  - etc.

### gas_field_production_mapping.json
- **Gas concepts**:
  - `Gas de Alta Presión (Mm3)` → `high_pressure_gas`
  - `Gas de Baja Presión (Mm3)` → `low_pressure_gas`
  - `Inyectado a Formación (Mm3)` → `gas_reinjection_formation`
  - etc.

### well_production_mapping.json
- **Extraction methods**:
  - `Bombeo Mecánico` → `mechanical_pump`
  - `Bombeo Electrosumergible` → `electric_submersible_pump`
  - `Gas Lift` → `gas_lift`
  - etc.
- **Well status**:
  - `Extracción Efectiva` → `producing`
  - `En Inyección Efectiva de Agua` → `water_injection`
  - `Abandonado` → `abandoned`
  - etc.

### well_characteristics_mapping.json
- **Classification**:
  - `EXPLORACION` → `exploration`
  - `EXPLOTACION` → `production`
- **Resource type**:
  - `CONVENCIONAL` → `conventional`
  - `NO CONVENCIONAL` → `unconventional`

## Output Schema

### Final CSV Columns (44 total)

| Column | Unit | Description |
|--------|------|-------------|
| **Identification** |||
| field_id | - | Field identifier (e.g., "AAB") |
| name | - | Field name |
| country | - | "Argentina" |
| company_name | - | Operating company |
| **Temporal** |||
| year | - | Year (2025) |
| month | - | Month (1-12) |
| start_date | - | First day of month (YYYY-MM-DD) |
| end_date | - | Last day of month (YYYY-MM-DD) |
| **Geographic** |||
| basin | - | Sedimentary basin |
| province | - | Province name |
| offshore | 0/1 | Offshore flag |
| depth | m | Average well depth |
| **Classification** |||
| functional_unit | - | "oil" or "gas" (GOR-based) |
| **Production** |||
| oil_prod | bbl | Oil production (converted from m³) |
| gas_prod | m³ | Gas production (converted from Mm³) |
| water_prod | m³ | Water production |
| **Injection** |||
| water_injected | m³ | Water injection |
| gas_injected | m³ | Gas injection |
| **Ratios** |||
| gor | m³/m³ | Gas-to-oil ratio |
| wor | m³/m³ | Water-to-oil ratio |
| wir | m³/m³ | Water injection ratio |
| glir | m³/m³ | Gas lift injection ratio |
| **Technical** |||
| api | degrees | API gravity (time-varying!) |
| **Well Counts** |||
| num_prod_wells | - | Producing wells |
| num_water_inj_wells | - | Water injection wells |
| num_gas_inj_wells | - | Gas injection wells |
| **Extraction Methods** (binary flags) |||
| downhole_pump | 0/1 | Uses downhole pump |
| gas_lifting | 0/1 | Uses gas lift |
| **Production Types** (m³) |||
| primary_prod_m3 | m³ | Primary recovery |
| secondary_prod_m3 | m³ | Secondary recovery |
| assisted_recovery_m3 | m³ | Tertiary/EOR |
| unconventional_prod_m3 | m³ | Unconventional |
| **EOR Methods** (binary flags) |||
| water_flooding | 0/1 | Water flooding active |
| natural_gas_reinjection | 0/1 | Gas reinjection active |
| steam_flooding | 0/1 | Steam flooding active |
| gas_flooding | 0/1 | Gas flooding active |

## Key Transformations

### 1. Pivot LONG → WIDE
Argentina data has multiple rows per field-month (one per "concepto"):
```
field_id  month  concept              quantity
AAB       1      primary_production   991.70
AAB       1      water_injection      1576.00
AAB       1      oil_density_avg      0.90
```
→ Pivoted to one row:
```
field_id  month  primary_prod_m3  water_injected_m3  density_ton_m3
AAB       1      991.70           1576.00            0.90
```

### 2. Functional Unit Classification
Three-way logic:
- Field only produces oil (gas_prod = 0) → `oil`
- Field only produces gas (oil_prod = 0) → `gas`
- Field produces both → Calculate GOR:
  - GOR > 1,781 m³/m³ (10,000 scf/bbl) → `gas`
  - GOR ≤ 1,781 → `oil`

### 3. API Gravity Calculation (TIME-VARYING!)
```
API = (141.5 / density_ton_m3) - 131.5
```
Source: Monthly "Densidad Media" from field production data

### 4. Well Count Aggregation
From monthly well production data:
- Count wells by status (producing, injecting)
- Aggregate to field-month level
- Extract dominant extraction method

### 5. Unit Conversions
| From | To | Factor |
|------|-----|--------|
| Oil: m³ → bbl | m³ → bbl | ×6.28981 |
| Gas: Mm³ → m³ | Mm³ → m³ | ×1,000,000 |
| Water: m³ → m³ | - | (no change) |

## Data Sources

### Government of Argentina Open Data

All raw data from: https://datos.gob.ar/

**Field Production Files:**
- Oil: `produccin-de-petrleo-por-yacimiento.csv` (~2.4M rows, 414 MB)
- Gas: `produccin-de-gas-por-yacimiento.csv` (~1.4M rows, 247 MB)

**Well Data Files:**
- Monthly: `produccin-de-pozos-de-gas-y-petrleo-{year}.csv` (~743k rows, 224 MB)
- Static: `capitulo-iv-pozos.csv` (~85k rows, 32 MB)

## Testing

Test the pipeline on a single field:

```bash
python test_single_field.py
```

This runs the complete transformation on field **AAB** and generates:
- `output/test_field_AAB_result.csv` - Verify all transformations

## Troubleshooting

### Translation Issues

**Problem:** Some Spanish values not translated
**Solution:** Add missing translations to mapping files in `config/translation_mappings/`

**Problem:** Translation script fails on large files
**Solution:** Use sample mode first (`FULL_TRANSLATION = False`)

### Transformation Issues

**Problem:** Missing well count data
**Solution:** Ensure well production file exists in `raw/translated/`

**Problem:** Missing depth data
**Solution:** Ensure well characteristics file exists in `raw/translated/`

**Problem:** API gravity is null
**Solution:** Check that "Densidad Media" exists in oil production data

### Data Quality

**Expected behavior:**
- Some fields may not have well count data (normal)
- Some fields may not have depth data (normal)
- Gas fields will have null API gravity (expected)

## Configuration

### GOR Threshold

Adjust functional unit classification threshold:

Edit `config/opgee_calculation_params.json`:
```json
{
  "functional_unit_classification": {
    "gor_threshold_scf_bbl": 10000,
    "gor_threshold_m3_m3": 1781
  }
}
```

### EOR Detection

Adjust EOR method detection thresholds:
```json
{
  "eor_detection": {
    "steam_flooding_wir_threshold": 5.0
  }
}
```

## File Structure

```
argentina/
├── config/
│   ├── translation_mappings/
│   │   ├── oil_field_production_mapping.json
│   │   ├── gas_field_production_mapping.json
│   │   ├── well_production_mapping.json
│   │   └── well_characteristics_mapping.json
│   ├── opgee_calculation_params.json
│   └── DETAILED_TRANSFORMATION_GUIDE.md
├── raw/
│   ├── translated/  (generated by script 01)
│   └── *.csv  (place raw Spanish files here)
├── output/
│   └── field_production_complete.csv  (final output)
└── scripts/
    ├── 01_translate_all_raw_data.py  (Step 1)
    ├── 02_clean_and_merge_translated.py  (Step 2)
    ├── 00a_add_well_counts_and_geometry.py  (helper)
    └── test_single_field.py  (testing)
```

## Notes

- **Temporal Granularity**: Monthly field-level data
- **Time Period**: 2025 (configurable)
- **Spatial Coverage**: All producing fields in Argentina
- **Data Freshness**: Depends on government data update frequency
- **Language**: All output in English with O&G terminology
- **Units**: OPGEE-compatible (bbl, m³, degrees API, etc.)

## Future Enhancements

- [ ] Support for multiple years
- [ ] Automated data quality checks
- [ ] Geometry data integration
- [ ] H3 spatial indexing
- [ ] Direct API upload to Pyxis
- [ ] Historical trend analysis
- [ ] Data validation reports

## Support

For issues or questions:
1. Check logs for error messages
2. Review `COLUMN_TRANSFORMATION_SUMMARY.md` for transformation details
3. Check translation mappings for missing values
4. Test with single field using `test_single_field.py`
