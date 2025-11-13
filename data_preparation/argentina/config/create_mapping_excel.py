"""
Create comprehensive Argentina → Pyxis mapping documentation in Excel format
Multiple sheets with mapping tables, unit conversions, and notes
"""

import pandas as pd
from pathlib import Path

# Output path
output_file = Path(__file__).parent / "argentina_pyxis_mapping.xlsx"

# ============================================================================
# SHEET 1: Main Pyxis Field Mapping (Monthly Output)
# ============================================================================

main_mapping = pd.DataFrame({
    'Pyxis Column': [
        'field_id', 'field_name', 'country', 'year', 'month', 'time_index',
        'geometry', 'depth', 'well_vintage_year',
        'functional_unit', 'oil_prod', 'gas_prod', 'num_prod_wells',
        'gor', 'wor', 'wir', 'glir', 'water_flooding', 'gas_flooding',
        'natural_gas_reinjection', 'downhole_pump', 'gas_lifting',
        'offshore', 'num_water_inj_wells', 'fraction_remaining_gas_inj',
        'api', 'province', 'basin'
    ],
    'Primary Source File': [
        'daily_oil_production', 'daily_oil_production', 'HARDCODE', 'TIME_PERIOD', 'TIME_PERIOD', 'TIME_PERIOD',
        'field_shapes_depth', 'field_shapes_depth', 'field_production_by_formation_vintage',
        'daily_oil/gas_production', 'daily_oil_production', 'daily_gas_production', 'well_production_2025',
        'daily_oil/gas_production', 'field_production_by_formation_vintage', 'field_production_by_formation_vintage',
        'well_production_2025', 'field_production_by_formation_vintage', 'field_production_by_formation_vintage',
        'gas_field_production', 'well_production_2025', 'well_production_2025',
        'gas/oil_field_production', 'well_production_2025', 'gas_field_production',
        'oil_field_production', 'daily_oil_production', 'daily_oil_production'
    ],
    'Calculation/Extraction': [
        'Direct: field_id', 'Direct: field_name', '"Argentina"', 'Input parameter', 'Input parameter', 'YYYY-MM',
        'Direct: field_boundary_geojson', 'depth_avg_m * 3.28084', 'MIN(well_vintage_year)',
        'Vote-based on monthly GOR (see Sheet 2)', 'AVG(oil_production_avg_daily_m3) * 6.28981',
        'AVG(gas_production_avg_daily_mm3) * 10^6 * 35.3147', 'COUNT(DISTINCT well_id WHERE active)',
        '(gas_Mm3 * 10^6 * 35.3147) / (oil_m3 * 6.28981)', 'SUM(water_prod_m3) / SUM(oil_prod_m3)',
        'SUM(water_inj_m3) / SUM(oil_prod_m3)', 'SUM(gas_inj_km3 * 1000 * 35.3147) / SUM(oil_m3 * 6.28981)',
        'ANY(water_injection_m3 > 0)', 'ANY(gas_injection_km3 > 0)',
        'Pivot: gas_reinjection_formation_mm3 > 0', 'Pivot: COUNT(extraction_method=mechanical_pump) > 0',
        'Pivot: COUNT(extraction_method=gas_lift) > 0',
        'location = "Offshore"', 'COUNT(DISTINCT well_id WHERE water_injection_m3 > 0)',
        'gas_reinjection_mm3 / total_gas_production_mm3',
        'AVG(oil_density_avg_ton_per_m3) THEN: 141.5/density - 131.5', 'Direct: province', 'Direct: basin'
    ],
    'Alternative Sources': [
        'All files', 'All files', '-', '-', '-', '-',
        '-', 'Can calc weighted avg by formation from vintage file', 'Can use MIN(year) from daily files',
        'well_production has well_type field', 'field_production_by_formation_vintage (aggregate)',
        'field_production_by_formation_vintage (aggregate)', 'historical files for pre-2009',
        'field_production_by_formation_vintage', 'well_production_2025', 'well_production_2025',
        'field_production_by_formation_vintage', 'well_production_2025', 'well_production_2025',
        'field_production_by_formation_vintage', 'historical_oil_wells', 'historical_oil_wells',
        'historical files', '-', '-',
        'Can estimate from formation type', '-', '-'
    ],
    'Unit Conversion': [
        '-', '-', '-', '-', '-', '-',
        'GeoJSON WKT', 'm → ft: ×3.28084', 'year (integer)',
        '"oil" or "gas"', 'm3/day → bbl/day: ×6.28981', 'Mm3/day → scf/day: ×10^6×35.3147', 'count',
        'Mm3/m3 → scf/bbl', 'm3/m3 (same)', 'm3/m3 (same)', 'km3/m3 → scf/bbl',
        'boolean', 'boolean',
        'boolean', 'boolean', 'boolean',
        'boolean', 'count', 'fraction 0-1',
        'ton/m3 → degrees API', '-', '-'
    ],
    'Notes': [
        'Primary key with year-month', 'String identifier', 'Fixed value', 'Filter parameter', 'Filter parameter', 'ISO format',
        'Polygon or MultiPolygon - Pyxis will calculate centroid', 'OPGEE requires feet', 'Store vintage year - Pyxis calculates age',
        'Determines OPGEE pathway', 'OPGEE: bbl/day', 'OPGEE: scf/day', 'Producing wells only',
        'OPGEE: scf/bbl - critical param', 'OPGEE: bbl_water/bbl_oil', 'OPGEE: bbl_water/bbl_oil', 'OPGEE: scf/bbl_liquid',
        'Indicates secondary recovery', 'Indicates tertiary recovery',
        'OPGEE boolean', 'OPGEE boolean', 'OPGEE boolean',
        'OPGEE boolean', 'Injection wells count', 'OPGEE: fraction',
        'Calculate from density: API = 141.5/density - 131.5', 'Useful for regional analysis', 'Useful for regional analysis'
    ]
})

# ============================================================================
# SHEET 2: Unit Conversions & Confirmations
# ============================================================================

unit_conversions = pd.DataFrame({
    'Source Unit': ['m3 (oil)', 'm3/day (oil)', 'Mm3 (gas)', 'Mm3/day (gas)', 'km3 (gas)',
                    'km3/day (gas)', 'meters', 'ton/m3 (density)', 'kcal/m3'],
    'Target Unit': ['bbl', 'bbl/day', 'scf', 'scf/day', 'scf', 'scf/day', 'feet', 'degrees API', 'BTU/scf'],
    'Conversion Factor': ['×6.28981', '×6.28981', '×35,314,666.7', '×35,314,666.7', '×35,314.7',
                          '×35,314.7', '×3.28084', '141.5/density - 131.5', '×0.001055×(10^6/35.3147)'],
    'Formula': ['bbl = m3 × 6.28981', 'bbl/day = m3/day × 6.28981',
                'scf = Mm3 × 10^6 × 35.3147', 'scf/day = Mm3/day × 10^6 × 35.3147',
                'scf = km3 × 1000 × 35.3147', 'scf/day = km3/day × 1000 × 35.3147',
                'ft = m × 3.28084', 'API = 141.5/SG - 131.5 where SG=ton/m3',
                'BTU/scf = (kcal/m3 × 0.001055 × 10^6) / 35.3147'],
    'Example': ['100 m3 = 628.98 bbl', '100 m3/day = 628.98 bbl/day',
                '1 Mm3 = 35,314,667 scf', '1 Mm3/day = 35,314,667 scf/day',
                '1 km3 = 35,314.7 scf', '1 km3/day = 35,314.7 scf/day',
                '100 m = 328.08 ft', '0.85 ton/m3 ≈ 35° API',
                '9000 kcal/m3 ≈ 269 BTU/scf'],
    'Files Using This Unit': [
        'all production files', 'daily_oil_production',
        'daily_gas_production, gas_field_production', 'daily_gas_production',
        'field_production_by_formation_vintage, well_production_2025',
        'field_production_by_formation_vintage',
        'field_shapes_depth, well_characteristics',
        'oil_field_production (concept: oil_density_avg_ton_per_m3)',
        'gas_field_production'
    ]
})

unit_confirmation = pd.DataFrame({
    'Unit Symbol': ['Mm3', 'km3', 'm3'],
    'Meaning': ['Million cubic meters (10^6 m3)', 'Thousand cubic meters (10^3 m3)', 'Cubic meters'],
    '2019 Analysis': [
        'field_formation_vintage: 29.98 Mm3 oil',
        'Used for gas in formation/well files',
        'Used for oil production'
    ],
    'External Reference': ['Argentina 2019: 29.5 Mm3 ✓ MATCHES', '-', '-'],
    'Confirmed': ['YES - Mm3 = million m3', 'YES - km3 = thousand m3', 'YES - base unit']
})

# ============================================================================
# SHEET 3: Functional Unit Determination Logic
# ============================================================================

functional_unit_logic = pd.DataFrame({
    'Step': [1, 2, 3, 4, 5, 6, 7],
    'Process': [
        'Load monthly data',
        'Calculate monthly GOR',
        'Apply classification rules',
        'Vote across months',
        'Cross-validate',
        'Handle edge cases',
        'Assign final type'
    ],
    'Formula/Rule': [
        'For each field-month in target year',
        'GOR_scf_bbl = (gas_Mm3/day × 10^6 × 35.3147) / (oil_m3/day × 6.28981)',
        'IF oil=0 AND gas>0: "gas"; IF gas=0 AND oil>0: "oil"; IF GOR>100000: "gas"; ELSE: "oil"',
        'functional_unit = MODE(monthly_classifications)',
        'Check well_production_2025.well_type distribution for field',
        'IF no gas data: "oil"; IF no oil data: "gas"; IF tie: use GOR threshold',
        'Assign majority vote result to field'
    ],
    'Threshold': ['-', '-', '100,000 scf/bbl', '>50% of months', '>70% agreement', '-', '-'],
    'Alternative Method': [
        '-', '-', 'Use well_type from well_production', 'Use annual avg GOR', '-', '-',
        'Default to "oil" if uncertain'
    ],
    'Notes': [
        'Recommend using 2025 data for consistency',
        'Handle division by zero (oil=0)',
        'GOR threshold based on US conventions (gas field >100k scf/bbl)',
        'Most robust approach for varying production',
        'Useful for fields with incomplete monthly data',
        'Some fields switch between oil/gas seasonally',
        'OPGEE requires "oil" or "gas" designation'
    ]
})

# ============================================================================
# SHEET 4: Supplementary Files Mapping
# ============================================================================

fracture_mapping = pd.DataFrame({
    'Output Column': ['well_id', 'field_id', 'field_name', 'fracture_date', 'formation_name',
                      'proppant_mass_tons', 'fluid_volume_m3', 'pumping_pressure_psi',
                      'completion_type', 'reservoir_type', 'stages_count'],
    'Source File': ['fracture_completion', 'well_characteristics', 'well_characteristics',
                    'fracture_completion', 'fracture_completion',
                    'fracture_completion', 'fracture_completion', 'fracture_completion',
                    'fracture_completion', 'fracture_completion', 'fracture_completion'],
    'Source Column': ['well_id', 'field_id', 'field_name', 'fracture_date', 'formation_name',
                      'proppant_mass_tons', 'fluid_volume_m3', 'pumping_pressure_psi',
                      'completion_type', 'reservoir_type', 'stages_count'],
    'Join Logic': ['-', 'JOIN well_characteristics ON well_id', 'JOIN well_characteristics ON well_id',
                   '-', '-', '-', '-', '-', '-', '-', '-'],
    'Purpose': ['Primary key', 'Link to field', 'Field name', 'Timing', 'Reservoir',
                'GHGfrack input', 'GHGfrack input', 'GHGfrack input',
                'Completion tech', 'Conventional/Unconventional', 'Frac stages']
})

historical_wells = pd.DataFrame({
    'Output Column': ['field_name', 'location', 'year', 'gas_wells_active', 'gas_wells_shut_in',
                      'oil_wells_gas_lift', 'oil_wells_mech_pump', 'well_type'],
    'Source File': ['historical_gas/oil_wells', 'historical_gas/oil_wells', 'historical_gas/oil_wells',
                    'historical_gas_wells', 'historical_gas_wells', 'historical_oil_wells',
                    'historical_oil_wells', 'historical_gas/oil_wells'],
    'Aggregation': ['Direct', 'Direct', 'Direct', 'Pivot: status=active_production',
                    'Pivot: status=shut_in_reserve', 'Pivot: method=gas_lift',
                    'Pivot: method=mechanical_pump', 'Direct'],
    'Time Period': ['1999-2009', '1999-2009', '1999-2009', '1999-2009', '1999-2009',
                    '1999-2009', '1999-2009', '1999-2009'],
    'Use Case': ['Historical context', 'Onshore/offshore', 'Time series', 'Well counts pre-2009',
                 'Shut-in reserves', 'Lift method', 'Lift method', 'Gas vs oil wells'],
    'Limitation': ['No field_id', 'Can approximate lat/lon', 'Too old for main output',
                   'Pre-2009 only', 'Pre-2009 only', 'Pre-2009 only', 'Pre-2009 only',
                   'Pre-2009 only']
})

# ============================================================================
# SHEET 5: File Usage Priority & Coverage
# ============================================================================

file_usage = pd.DataFrame({
    'File Name': [
        'daily_oil_production', 'daily_gas_production', 'field_shapes_depth',
        'field_production_by_formation_vintage', 'fracture_completion_data',
        'gas_field_production', 'oil_field_production', 'plant_gas_processing',
        'well_characteristics', 'well_production_2025', 'historical_gas_wells',
        'historical_oil_wells'
    ],
    'Priority': ['HIGH', 'HIGH', 'HIGH', 'CRITICAL', 'MEDIUM', 'HIGH', 'MEDIUM',
                 'LOW', 'MEDIUM', 'HIGH', 'LOW', 'LOW'],
    'Time Coverage': ['2009-2024', '2009-2024', 'Static', '2010-2025', 'Static',
                      '2009-2022', '2019-2025', 'Unknown', 'Static', 'Monthly 2025',
                      '1999-2009', '1999-2009'],
    'Primary Use': [
        'oil_prod rate', 'gas_prod rate, GOR', 'Geometry, depth, lat/lon',
        'WOR, WIR, injection flags, age, formation data', 'GHGfrack standalone',
        'Gas reinjection, heating value, pressure breakdown', 'Recovery type breakdown',
        'Flaring data (future)', 'Join key for fracture data', 'Well counts, extraction methods',
        'Historical well status', 'Historical lift methods'
    ],
    'Key Limitations': [
        'Daily avg only, no 2025', 'Daily avg only, ends 2024', 'No time dimension',
        'Most complete but complex', 'No direct field_id', 'Ends 2022',
        'Overlaps with other files', 'Not for main output', 'Large file',
        'Only 2025 loaded', 'No field_id, old', 'No field_id, old'
    ],
    'Rows': ['256,472', '227,236', '738', '480,280', '4,313', '1,383,561',
             '2,376,999', '12,186', '85,118', '743,186', '261,336', '239,186'],
    'For Pyxis Monthly Output': ['✓ Primary', '✓ Primary', '✓ Static join', '✓ Primary',
                                  '✗ Standalone', '✓ Primary', '○ Backup', '✗ Future',
                                  '○ Lookup', '✓ Primary', '✗ Too old', '✗ Too old']
})

# ============================================================================
# SHEET 6: Data Not Yet Extracted
# ============================================================================

unused_data = pd.DataFrame({
    'File': [
        'gas_field_production', 'gas_field_production', 'gas_field_production',
        'gas_field_production', 'well_production_2025', 'well_production_2025',
        'field_production_by_formation_vintage', 'field_production_by_formation_vintage',
        'oil_field_production', 'field_shapes_depth', 'plant_gas_processing',
        'well_characteristics', 'well_characteristics'
    ],
    'Column/Data': [
        'gas_heating_value_kcal_per_m3', 'high/medium/low pressure breakdown',
        'unconventional_gas_mm3', 'gas_injection/extraction_storage_mm3',
        'tef (time efficiency factor)', 'productive_life_days',
        'formation_name', 'well_vintage_year',
        'concept (recovery type)', 'depth_min_m, depth_max_m',
        'flared gas volumes', 'surface_elevation_m', 'well_classification'
    ],
    'Potential Use': [
        'Calculate gas energy content (BTU)', 'Understand pressure regimes',
        'Flag Vaca Muerta production', 'Track seasonal storage operations',
        'Field uptime/efficiency analysis', 'Decline analysis, EUR estimation',
        'Reservoir-specific properties (API, GOR)', 'Decline curve modeling by cohort',
        'Distinguish primary/secondary/tertiary', 'Reservoir thickness calculation',
        'Emissions calculations', 'Terrain analysis', 'Well purpose classification'
    ],
    'OPGEE Relevance': [
        'Medium - energy content', 'Low', 'Medium - unconventional flag',
        'Low', 'Medium - uptime affects energy', 'Low',
        'High - formation correlates with API/properties', 'Medium - field maturity',
        'High - recovery method affects energy', 'Low',
        'Critical - future flaring emissions', 'Low', 'Low'
    ],
    'Implementation Complexity': [
        'Low - direct conversion', 'Medium - pivot required', 'Low - binary flag',
        'Medium - temporal analysis', 'Low - direct calc', 'Low - direct use',
        'High - need formation property database', 'Medium - cohort tracking',
        'Medium - concept mapping', 'Low - direct calc',
        'Medium - requires plant association', 'Low - direct', 'Low - direct'
    ]
})

# ============================================================================
# SHEET 7: 2019 Production Analysis
# ============================================================================

prod_2019_analysis = pd.DataFrame({
    'Source': [
        'field_production_by_formation_vintage',
        'oil_field_production (primary)',
        'oil_field_production (secondary)',
        'oil_field_production (tertiary EOR)',
        'oil_field_production (unconventional)',
        'oil_field_production (condensate)',
        'oil_field_production (TOTAL)',
        'External reference (Argentina stats)'
    ],
    'Oil Production m3': [
        '29,980,731',
        '16,234,187',
        '10,494,011',
        '153,517',
        '5,751,849',
        '1,515,654',
        '34,149,218',
        '~29,500,000'
    ],
    'Oil Production Mm3': [
        '29.98',
        '16.23',
        '10.49',
        '0.15',
        '5.75',
        '1.52',
        '34.15',
        '29.5'
    ],
    'Notes': [
        'Aggregated across all formations and vintages',
        'Primary recovery only',
        'Waterflooding and other secondary',
        'CO2-EOR, thermal, etc.',
        'Vaca Muerta and other tight reservoirs',
        'Natural gas liquids',
        'Sum of all recovery types + condensate',
        'Government statistics (may exclude condensate)'
    ],
    'Match with Reference': [
        '✓ Very close (29.98 vs 29.5)',
        '-',
        '-',
        '-',
        '-',
        '-',
        '○ Higher (includes condensate)',
        'Reference value'
    ]
})

unit_conclusion = pd.DataFrame({
    'Question': [
        'What does Mm3 mean?',
        'Is it consistent across files?',
        'How to convert for OPGEE?',
        'What about km3?'
    ],
    'Answer': [
        'Mm3 = Million cubic meters (10^6 m3)',
        'YES - daily_gas_production and gas_field_production both use Mm3 = million m3',
        'Oil: m3 × 6.28981 = bbl; Gas: Mm3 × 35,314,666.7 = scf',
        'km3 = thousand m3 (10^3 m3), used ONLY for gas in formation_vintage and well_production files'
    ],
    'Evidence': [
        '2019 analysis: 29.98 Mm3 matches 29.5 Mm3 reference',
        'Consistent calculations across all gas files',
        'Standard O&G conversion factors',
        'Context makes it clear: gas volumes are typically smaller than km3 scale'
    ]
})

# ============================================================================
# SHEET 8: Implementation Notes
# ============================================================================

implementation_notes = pd.DataFrame({
    'Topic': [
        'Output Granularity',
        'Time Period Selection',
        'Data Quality',
        'Missing Data Handling',
        'Field Matching',
        'Aggregation Strategy',
        'Production Method Flags',
        'Well Counts',
        'Formation Data',
        'Validation Steps'
    ],
    'Recommendation': [
        'Monthly output (one row per field per month)',
        'Start with 2025 for most complete data (Jan-Aug available)',
        'Cross-validate totals across multiple source files',
        'Use NULL for missing values, document data availability',
        'Use field_id as primary key (consistent across all files)',
        'For formation_vintage: SUM across formations and vintages',
        'Set TRUE if ANY month shows the method (conservative)',
        'Use MAX(monthly_count) for the year to avoid double-counting',
        'Keep formation detail in separate analysis table',
        '1) Check field_id coverage 2) Validate production totals 3) Check unit conversions'
    ],
    'Rationale': [
        'Preserves temporal patterns, enables trend analysis, matches OPGEE modeling needs',
        '2025 has well_production data; earlier years rely on daily_oil/gas only',
        'Different files have different scopes (primary vs total, with/without condensate)',
        'Better than 0 or estimates - allows users to filter',
        'field_name has variations and duplicates across provinces',
        'Matches oil_field_production totals when summed',
        'Once a field uses a method, it typically continues',
        'Wells can be active intermittently throughout year',
        'Formation-level detail too granular for main output but valuable for analysis',
        'Essential QA before using in OPGEE'
    ],
    'Implementation Detail': [
        'Output: field_id, year, month, time_index, [all metrics]',
        'For 2024 and earlier: use daily files + formation file; For 2025: add well_production',
        'Compare daily file totals vs formation file totals per field-month',
        'Add data_quality_flags: has_daily_data, has_well_data, has_injection_data',
        'Create field_id master table with canonical field_name',
        'GROUP BY field_id, year, month THEN SUM(production_m3)',
        'Aggregate monthly: ANY_VALUE(flag) WHERE flag=TRUE',
        'SELECT field_id, month, MAX(well_count) GROUP BY field_id, month',
        'Create separate formation_detail.csv with formation-level breakdowns',
        'Write validation script: compare sources, check unit conversions, verify totals'
    ]
})

# ============================================================================
# Write to Excel
# ============================================================================

with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
    main_mapping.to_excel(writer, sheet_name='1_Main_Pyxis_Mapping', index=False)
    functional_unit_logic.to_excel(writer, sheet_name='2_Functional_Unit', index=False)
    unit_conversions.to_excel(writer, sheet_name='3_Unit_Conversions', index=False)
    fracture_mapping.to_excel(writer, sheet_name='4_Fracture_Mapping', index=False)
    file_usage.to_excel(writer, sheet_name='5_File_Usage', index=False)
    unused_data.to_excel(writer, sheet_name='6_Data_Not_Yet_Used', index=False)
    implementation_notes.to_excel(writer, sheet_name='7_Implementation', index=False)
    prod_2019_analysis.to_excel(writer, sheet_name='8_2019_Verification', index=False)

    # Auto-adjust column widths
    for sheet_name in writer.sheets:
        worksheet = writer.sheets[sheet_name]
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            worksheet.column_dimensions[column_letter].width = adjusted_width

print(f"✅ Mapping documentation created: {output_file}")
print(f"\nSheets created:")
print("  1. Main Pyxis Mapping (Monthly Output)")
print("  2. Functional Unit Logic")
print("  3. Unit Conversions (incl. API from density)")
print("  4. Fracture/Completion Mapping")
print("  5. File Usage Priority")
print("  6. Data Not Yet Extracted")
print("  7. Implementation Notes")
print("  8. 2019 Production Verification")
