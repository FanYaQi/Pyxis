# Argentina Oil & Gas Data Preparation for Pyxis

**Status**: ✅ Production Ready  
**Last Updated**: November 7, 2025

---

## Overview

Complete data preparation pipeline for Argentina oil and gas data, ready for Pyxis platform integration and OPGEE emissions modeling. Includes translation of 12 Spanish government datasets, automated data processing pipelines, and comprehensive quality assurance.

---

## Quick Start

### Generate Monthly Pyxis Field Data
```bash
cd scripts
pipenv run python 05_generate_pyxis_monthly.py --year 2025 --months 1-8
```

### Generate Fracture Well Combined Data
```bash
cd scripts
pipenv run python 06_generate_fracture_well_data.py
```

### Generate Summary Statistics & Plots
```bash
cd scripts
pipenv run python 07_generate_summary_plots.py
```

---

## Project Structure

```
argentina/
│
├── README.md                           # This file
├── PIPELINE_SUMMARY.md                 # Comprehensive technical documentation
│
├── raw/                                # Original Spanish data
│   ├── [12 Spanish CSV files]         # ~550 MB
│   └── translated/                     # Translated English data
│       └── [12 English CSV files]      # ~550 MB
│
├── config/                             # Configuration & mappings
│   ├── translation_mappings/
│   │   └── [12 JSON files]            # Translation logic
│   ├── argentina_pyxis_mapping.xlsx   # Mapping documentation (8 sheets)
│   └── mapping_instruction.md         # Mapping instructions
│
├── scripts/                            # Processing pipelines
│   ├── 01_translate_all_raw_data.py   # Translation (443 lines)
│   ├── 05_generate_pyxis_monthly.py   # Pyxis fields (617 lines)
│   ├── 06_generate_fracture_well_data.py  # Fracture data (260 lines)
│   └── 07_generate_summary_plots.py   # Statistics & plots (400+ lines)
│
└── output/                             # Generated outputs
    ├── argentina_pyxis_fields_2025.csv         # 22 MB, 3,793 records
    ├── argentina_fracture_well_combined.csv    # 1.9 MB, 4,313 records
    ├── SUMMARY_STATISTICS.txt                  # Detailed text statistics
    └── plots/
        ├── pyxis_fields_summary.png            # 650 KB, 9-panel figure
        └── fracture_well_summary.png           # 667 KB, 9-panel figure
```

---

## Output Files

### 1. argentina_pyxis_fields_2025.csv

**Purpose**: Monthly field-level data for Pyxis database and OPGEE modeling

**Specifications**:
- **Size**: 22 MB
- **Records**: 3,793 (1,267 unique fields × 3 months)
- **Columns**: 27
- **Date Range**: 2025-01 to 2025-03

**Key Metrics**:
- Oil production: 100% coverage (bbl/day)
- Gas production: 39.4% coverage (scf/day) 
- Gas fields: 36.7% (1,391 records from 465 fields)
- Oil fields: 63.3% (2,402 records from 802 fields)
- API gravity: 36.4% coverage
- Well counts: 91.9% coverage

**OPGEE Readiness**: 70-75% of critical inputs available

### 2. argentina_fracture_well_combined.csv

**Purpose**: Fracture completion data for GHGfrack emissions calculations

**Specifications**:
- **Size**: 1.9 MB
- **Records**: 4,313 fracture jobs
- **Columns**: 42
- **Date Range**: 2006-2025

**Key Metrics**:
- Unconventional: 78.9% (3,405 jobs)
- 100% well matching rate
- Avg stages: 25 (unconventional)
- Avg lateral: 4,820 ft (unconventional)
- Avg proppant: 12.1 million lb (unconventional)

---

## Key Features

### 🎯 Gas Production Data Resolution
- **Problem**: Daily gas data unavailable for 2025
- **Solution**: Dual-fallback system (gas_field_production → formation_vintage)
- **Result**: Gas field identification improved from 9.4% to 36.7% (4x improvement)

### ⚡ Performance Optimization
- Pre-aggregation of 480K formation/vintage records
- O(1) dictionary lookups for field shapes
- Processing time: ~9 minutes for 3 months

### 📊 Vote-Based Classification
- GOR threshold: 100,000 scf/bbl
- Monthly classifications aggregated by MODE
- Robust handling of seasonal variations

### 🔧 Unit Conversions
- Oil: m³ → bbl (×6.28981)
- Gas: Mm³ → scf (×35,314,666.7), km³ → scf (×35,314.7)
- Depth: m → ft (×3.28084)
- Proppant: tons → lb (×2,204.62)
- Fluid: m³ → gal (×264.172)

---

## Data Sources

All data from Argentina Ministry of Energy: [datos.energia.gob.ar](https://datos.energia.gob.ar)

### Input Files (12 Spanish CSV files):

1. **Oil field production** (2.4M records) - Monthly by recovery type
2. **Gas field production** (1.4M records) - Monthly by pressure category
3. **Well production** (743K records) - Monthly by extraction method
4. **Well characteristics** (85K records) - Static metadata
5. **Fracture completion** (4.3K records) - Hydraulic fracturing details
6. **Field shapes & depth** (738 records) - GeoJSON boundaries
7. **Daily oil production** (256K records) - Average daily rates
8. **Daily gas production** (227K records) - Average daily rates
9. **Field production by formation/vintage** (480K records) - Includes injection
10. **Plant gas processing** (80K records) - Includes flaring
11. **Historical gas wells** (15K records) - Pre-2009 well counts
12. **Historical oil wells** (12K records) - Pre-2009 well counts

---

## Statistics Highlights

### Pyxis Fields (2025 Q1)
- **Top Oil Producer**: LOMA CAMPANA-LLL (67,432 bbl/day)
- **Top Gas Producer**: FORTIN DE PIEDRA (944 Bscf/day)
- **Basin Distribution**: 52.6% NEUQUINA, 22.1% AUSTRAL, 13.5% GOLFO SAN JORGE
- **Production Methods**: 16.1% water flooding, 39.5% downhole pump, 4.2% gas lifting

### Fracture Wells (2006-2025)
- **Most Active Field**: LOMA CAMPANA-LLL (591 jobs)
- **Annual Peak**: 2023 (373 jobs)
- **Completion Types**: 52% plug-and-perf, 45% perforation only
- **Unconventional Intensity**: 376K lb proppant/stage, 257K gal fluid/stage

---

## Data Quality

### Strengths ✅
- High completeness on oil production, field IDs, well counts (90-100%)
- 100% fracture well matching
- Comprehensive basin coverage (9 basins)
- Recent data availability (2025 YTD)
- Both conventional and unconventional wells

### Limitations ⚠️
- Gas production: 60.6% missing (limited to gas_field_production coverage)
- API gravity: 63.6% missing (depends on density data availability)
- Geometry: Excluded per user request
- Daily gas cutoff: 2024-03 (requires fallback for 2025)

---

## Next Steps

### Immediate
- [x] Ingest Pyxis fields into database
- [x] Use fracture data for GHGfrack modeling
- [x] Run OPGEE with 70-75% input coverage

### Short Term
- [ ] Process 2024 well production data
- [ ] Generate Q2-Q4 2025 when available
- [ ] Validate against national statistics

### Medium Term
- [ ] Build formation → API correlation model
- [ ] Add decline curve analysis
- [ ] Process historical data (2006-2023)

### Long Term
- [ ] Automate monthly data updates
- [ ] Basin-level aggregations
- [ ] Time-series emissions tracking

---

## Documentation

- **PIPELINE_SUMMARY.md** - Comprehensive technical documentation (9 sections)
- **SUMMARY_STATISTICS.txt** - Detailed statistics for both outputs
- **argentina_pyxis_mapping.xlsx** - Mapping documentation (8 sheets)
- **plots/** - Visual summaries (9-panel figures)

---

## Technical Contact

**Generated by**: Claude Code  
**Project**: Pyxis - GIS-based oil & gas emissions monitoring  
**Python Version**: 3.11+  
**Key Dependencies**: pandas, numpy, (matplotlib, seaborn for plots)

---

## License

Data source: Argentina Ministry of Energy (public domain)  
Pipeline code: Pyxis Project

---

*Last generated: November 7, 2025*
