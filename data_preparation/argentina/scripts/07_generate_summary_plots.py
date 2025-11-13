"""
Generate Summary Statistics and Plots for Argentina Outputs

Creates individual plot files for:
1. argentina_pyxis_fields_2025.csv
2. argentina_fracture_well_combined.csv

Outputs:
- Individual PNG files saved to output/plots/
- Uses Mcf (thousand cubic feet) for gas
- Basin distribution by production
- GOR with oil/gas cutoff line
"""

import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import warnings
warnings.filterwarnings('ignore')

# Set plot style
sns.set_style("whitegrid")
plt.rcParams['font.size'] = 11
plt.rcParams['font.family'] = 'sans-serif'

# Constants
GOR_THRESHOLD_GAS_FIELD = 100000  # scf/bbl


# ============================================================================
# PYXIS FIELDS ANALYSIS
# ============================================================================

def plot_pyxis_fields(df, output_dir):
    """Generate individual plots for Pyxis field data."""

    print("\n" + "="*70)
    print("PYXIS FIELDS ANALYSIS")
    print("="*70)

    plots_dir = output_dir / 'plots'
    plots_dir.mkdir(exist_ok=True)

    # 1. Functional Unit Distribution (Pie Chart)
    plt.figure(figsize=(10, 8))
    func_counts = df['functional_unit'].value_counts()
    colors = ['#FF6B6B', '#4ECDC4']
    plt.pie(func_counts, labels=[f'{x}\n({func_counts[x]:,} records)' for x in func_counts.index],
            autopct='%1.1f%%', colors=colors, startangle=90, textprops={'fontsize': 12})
    plt.title(f'Functional Unit Distribution\nTotal: {len(df):,} field-months across 1,267 fields',
              fontsize=14, fontweight='bold', pad=20)
    plt.tight_layout()
    plt.savefig(plots_dir / 'pyxis_01_functional_unit.png', dpi=300, bbox_inches='tight')
    print(f"  ✓ Saved: pyxis_01_functional_unit.png")
    plt.close()

    # 2. Oil Production Distribution
    plt.figure(figsize=(10, 6))
    oil_data = df[df['oil_prod'] > 0]['oil_prod']
    plt.hist(np.log10(oil_data + 1), bins=50, color='#FF6B6B', alpha=0.7, edgecolor='black')
    plt.xlabel('log₁₀(Oil Production + 1) [bbl/day]', fontsize=12)
    plt.ylabel('Frequency', fontsize=12)
    plt.title(f'Oil Production Distribution\nn={len(oil_data):,} | mean={oil_data.mean():,.0f} bbl/day | median={oil_data.median():.0f}',
              fontsize=13, fontweight='bold')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(plots_dir / 'pyxis_02_oil_production.png', dpi=300, bbox_inches='tight')
    print(f"  ✓ Saved: pyxis_02_oil_production.png")
    plt.close()

    # 3. Gas Production Distribution (in Mcf = thousand cubic feet)
    plt.figure(figsize=(10, 6))
    gas_data = df[df['gas_prod'].notna() & (df['gas_prod'] > 0)]['gas_prod'] / 1000  # Convert to Mcf
    if len(gas_data) > 0:
        plt.hist(np.log10(gas_data + 1), bins=50, color='#4ECDC4', alpha=0.7, edgecolor='black')
        plt.xlabel('log₁₀(Gas Production + 1) [Mcf/day]', fontsize=12)
        plt.ylabel('Frequency', fontsize=12)
        plt.title(f'Gas Production Distribution\nn={len(gas_data):,} | mean={gas_data.mean():,.0f} Mcf/day | median={gas_data.median():,.0f} Mcf/day',
                  fontsize=13, fontweight='bold')
        plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(plots_dir / 'pyxis_03_gas_production.png', dpi=300, bbox_inches='tight')
    print(f"  ✓ Saved: pyxis_03_gas_production.png")
    plt.close()

    # 4. GOR Distribution (linear scale with cutoff line, exclude extremes)
    plt.figure(figsize=(10, 6))
    gor_data = df[df['gor'].notna() & (df['gor'] > 0) & (df['gor'] < 500000)]['gor']  # Exclude extreme values
    if len(gor_data) > 0:
        plt.hist(gor_data, bins=50, color='#95E1D3', alpha=0.7, edgecolor='black')
        plt.axvline(GOR_THRESHOLD_GAS_FIELD, color='red', linestyle='--', linewidth=2,
                    label=f'Gas Field Cutoff: {GOR_THRESHOLD_GAS_FIELD:,} scf/bbl')
        plt.xlabel('Gas-Oil Ratio [scf/bbl]', fontsize=12)
        plt.ylabel('Frequency', fontsize=12)
        plt.title(f'GOR Distribution (excluding GOR > 500k)\nn={len(gor_data):,} | median={gor_data.median():,.0f} scf/bbl',
                  fontsize=13, fontweight='bold')
        plt.legend(fontsize=11, loc='upper right')
        plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(plots_dir / 'pyxis_04_gor_distribution.png', dpi=300, bbox_inches='tight')
    print(f"  ✓ Saved: pyxis_04_gor_distribution.png")
    plt.close()

    # 5. API Gravity Distribution
    plt.figure(figsize=(10, 6))
    api_data = df[df['api'].notna() & (df['api'] > 0) & (df['api'] < 100)]['api']
    if len(api_data) > 0:
        plt.hist(api_data, bins=40, color='#F38181', alpha=0.7, edgecolor='black')
        plt.axvline(api_data.mean(), color='darkred', linestyle='--', linewidth=2,
                    label=f'Mean: {api_data.mean():.1f}°')
        plt.axvline(api_data.median(), color='blue', linestyle='--', linewidth=2,
                    label=f'Median: {api_data.median():.1f}°')
        plt.xlabel('API Gravity [degrees]', fontsize=12)
        plt.ylabel('Frequency', fontsize=12)
        plt.title(f'API Gravity Distribution\nn={len(api_data):,} | mean={api_data.mean():.1f}° | median={api_data.median():.1f}°',
                  fontsize=13, fontweight='bold')
        plt.legend(fontsize=11)
        plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(plots_dir / 'pyxis_05_api_gravity.png', dpi=300, bbox_inches='tight')
    print(f"  ✓ Saved: pyxis_05_api_gravity.png")
    plt.close()

    # 6. WOR Distribution
    plt.figure(figsize=(10, 6))
    wor_data = df[df['wor'].notna() & (df['wor'] > 0) & (df['wor'] < 50)]['wor']  # Filter extremes
    if len(wor_data) > 0:
        plt.hist(wor_data, bins=50, color='#AA96DA', alpha=0.7, edgecolor='black')
        plt.xlabel('Water-Oil Ratio [bbl water/bbl oil]', fontsize=12)
        plt.ylabel('Frequency', fontsize=12)
        plt.title(f'Water-Oil Ratio Distribution (WOR < 50)\nn={len(wor_data):,} | median={wor_data.median():.2f}',
                  fontsize=13, fontweight='bold')
        plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(plots_dir / 'pyxis_06_wor_distribution.png', dpi=300, bbox_inches='tight')
    print(f"  ✓ Saved: pyxis_06_wor_distribution.png")
    plt.close()

    # 7. Basin Distribution by PRODUCTION (not field count)
    plt.figure(figsize=(12, 6))
    basin_prod = df.groupby('basin').agg({
        'oil_prod': 'sum',
        'gas_prod': 'sum'
    })
    # Calculate BOE (Barrels of Oil Equivalent): oil + gas/6000
    basin_prod['boe'] = basin_prod['oil_prod'] + (basin_prod['gas_prod'].fillna(0) / 6000)
    basin_prod = basin_prod.sort_values('boe', ascending=False).head(10)

    plt.barh(range(len(basin_prod)), basin_prod['boe'], color='#FFD3B6', alpha=0.8, edgecolor='black')
    plt.yticks(range(len(basin_prod)), basin_prod.index)
    plt.xlabel('Total Production [BOE/day, 3-month sum]', fontsize=12)
    plt.title('Top 10 Basins by Production (BOE = oil + gas/6000)', fontsize=13, fontweight='bold')
    plt.grid(True, alpha=0.3, axis='x')

    # Add values on bars
    for i, (basin, row) in enumerate(basin_prod.iterrows()):
        plt.text(row['boe'], i, f"  {row['boe']:,.0f}", va='center', fontsize=10)

    plt.tight_layout()
    plt.savefig(plots_dir / 'pyxis_07_basin_production.png', dpi=300, bbox_inches='tight')
    print(f"  ✓ Saved: pyxis_07_basin_production.png")
    plt.close()

    # 8. Production Method Flags
    plt.figure(figsize=(10, 6))
    methods = {}
    if 'water_flooding' in df.columns:
        methods['Water Flooding'] = df['water_flooding'].sum()
    if 'gas_flooding' in df.columns:
        methods['Gas Flooding'] = df['gas_flooding'].sum()
    if 'natural_gas_reinjection' in df.columns:
        methods['Gas Reinjection'] = df['natural_gas_reinjection'].sum()
    if 'downhole_pump' in df.columns:
        methods['Downhole Pump'] = df['downhole_pump'].sum()
    if 'gas_lifting' in df.columns:
        methods['Gas Lifting'] = df['gas_lifting'].sum()

    methods_df = pd.Series(methods).sort_values(ascending=True)
    plt.barh(range(len(methods_df)), methods_df.values, color='#FCBAD3', alpha=0.8, edgecolor='black')
    plt.yticks(range(len(methods_df)), methods_df.index)
    plt.xlabel('Number of Field-Months', fontsize=12)
    plt.title('Production Methods Usage', fontsize=13, fontweight='bold')
    plt.grid(True, alpha=0.3, axis='x')

    # Add values
    for i, (method, count) in enumerate(methods_df.items()):
        pct = count / len(df) * 100
        plt.text(count, i, f"  {count:,} ({pct:.1f}%)", va='center', fontsize=10)

    plt.tight_layout()
    plt.savefig(plots_dir / 'pyxis_08_production_methods.png', dpi=300, bbox_inches='tight')
    print(f"  ✓ Saved: pyxis_08_production_methods.png")
    plt.close()

    # 9. Data Completeness
    plt.figure(figsize=(10, 6))
    completeness = {
        'oil_prod': df['oil_prod'].notna().mean() * 100,
        'gas_prod': df['gas_prod'].notna().mean() * 100,
        'gor': df['gor'].notna().mean() * 100,
        'wor': df['wor'].notna().mean() * 100,
        'api': df['api'].notna().mean() * 100,
        'depth': df['depth'].notna().mean() * 100,
        'num_prod_wells': df['num_prod_wells'].notna().mean() * 100
    }
    comp_df = pd.Series(completeness).sort_values(ascending=True)
    colors_comp = ['#A8E6CF' if x >= 70 else '#FFB6B6' for x in comp_df.values]

    plt.barh(range(len(comp_df)), comp_df.values, color=colors_comp, alpha=0.8, edgecolor='black')
    plt.yticks(range(len(comp_df)), comp_df.index)
    plt.xlabel('Completeness (%)', fontsize=12)
    plt.xlim(0, 100)
    plt.title('Data Completeness by Column', fontsize=13, fontweight='bold')
    plt.axvline(70, color='orange', linestyle='--', linewidth=2, label='70% threshold')
    plt.legend(fontsize=11)
    plt.grid(True, alpha=0.3, axis='x')

    # Add values
    for i, (col, pct) in enumerate(comp_df.items()):
        plt.text(pct, i, f"  {pct:.1f}%", va='center', fontsize=10)

    plt.tight_layout()
    plt.savefig(plots_dir / 'pyxis_09_data_completeness.png', dpi=300, bbox_inches='tight')
    print(f"  ✓ Saved: pyxis_09_data_completeness.png")
    plt.close()

    # Print statistics
    print("\n--- Key Statistics ---")
    stats = {
        'Total Records': len(df),
        'Unique Fields': df['field_id'].nunique(),
        'Oil Fields': (df['functional_unit'] == 'oil').sum(),
        'Gas Fields': (df['functional_unit'] == 'gas').sum(),
        'Avg Oil Prod (bbl/day)': df['oil_prod'].mean(),
        'Avg Gas Prod (Mcf/day)': df[df['gas_prod'].notna()]['gas_prod'].mean() / 1000,
        'Avg API': df['api'].mean(),
        'Avg Depth (ft)': df['depth'].mean()
    }
    for key, val in stats.items():
        if isinstance(val, float):
            print(f"  {key}: {val:,.0f}")
        else:
            print(f"  {key}: {val:,}")


# ============================================================================
# FRACTURE DATA ANALYSIS
# ============================================================================

def plot_fracture_data(df, output_dir):
    """Generate individual plots for fracture well data."""

    print("\n" + "="*70)
    print("FRACTURE WELL DATA ANALYSIS")
    print("="*70)

    plots_dir = output_dir / 'plots'
    plots_dir.mkdir(exist_ok=True)

    # 1. Reservoir Type Distribution
    plt.figure(figsize=(10, 8))
    res_counts = df['reservoir_type'].value_counts()
    colors = ['#E63946', '#F1FAEE', '#A8DADC']
    plt.pie(res_counts, labels=[f'{x}\n({res_counts[x]:,} jobs)' for x in res_counts.index],
            autopct='%1.1f%%', colors=colors, startangle=90, textprops={'fontsize': 12})
    plt.title(f'Reservoir Type Distribution\nTotal: {len(df):,} fracture jobs',
              fontsize=14, fontweight='bold', pad=20)
    plt.tight_layout()
    plt.savefig(plots_dir / 'fracture_01_reservoir_type.png', dpi=300, bbox_inches='tight')
    print(f"  ✓ Saved: fracture_01_reservoir_type.png")
    plt.close()

    # 2. Completion Type Distribution
    plt.figure(figsize=(10, 6))
    comp_counts = df['completion_type'].value_counts().head(7)
    plt.barh(range(len(comp_counts)), comp_counts.values, color='#457B9D', alpha=0.8, edgecolor='black')
    plt.yticks(range(len(comp_counts)), comp_counts.index)
    plt.xlabel('Number of Jobs', fontsize=12)
    plt.title('Completion Type Distribution', fontsize=13, fontweight='bold')
    plt.grid(True, alpha=0.3, axis='x')

    for i, (comp_type, count) in enumerate(comp_counts.items()):
        pct = count / len(df) * 100
        plt.text(count, i, f"  {count:,} ({pct:.1f}%)", va='center', fontsize=10)

    plt.tight_layout()
    plt.savefig(plots_dir / 'fracture_02_completion_type.png', dpi=300, bbox_inches='tight')
    print(f"  ✓ Saved: fracture_02_completion_type.png")
    plt.close()

    # 3. Annual Activity
    plt.figure(figsize=(12, 6))
    year_counts = df['frac_start_year'].value_counts().sort_index()
    plt.bar(year_counts.index, year_counts.values, color='#1D3557', alpha=0.7, edgecolor='black', width=0.8)
    plt.xlabel('Year', fontsize=12)
    plt.ylabel('Number of Fracture Jobs', fontsize=12)
    plt.title('Annual Fracture Activity', fontsize=13, fontweight='bold')
    plt.grid(True, alpha=0.3, axis='y')
    plt.xticks(year_counts.index, rotation=45)

    # Add values on bars
    for year, count in year_counts.items():
        plt.text(year, count, f'{count:,}', ha='center', va='bottom', fontsize=9)

    plt.tight_layout()
    plt.savefig(plots_dir / 'fracture_03_annual_activity.png', dpi=300, bbox_inches='tight')
    print(f"  ✓ Saved: fracture_03_annual_activity.png")
    plt.close()

    # 4. Fracture Stages Distribution
    plt.figure(figsize=(10, 6))
    stages = df[df['fracture_stages_count'] < 100]['fracture_stages_count']
    plt.hist(stages, bins=50, color='#E76F51', alpha=0.7, edgecolor='black')
    plt.xlabel('Number of Stages', fontsize=12)
    plt.ylabel('Frequency', fontsize=12)
    plt.title(f'Fracture Stages Distribution\nn={len(stages):,} | mean={stages.mean():.1f} | median={stages.median():.0f}',
              fontsize=13, fontweight='bold')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(plots_dir / 'fracture_04_stages.png', dpi=300, bbox_inches='tight')
    print(f"  ✓ Saved: fracture_04_stages.png")
    plt.close()

    # 5. Lateral Length Distribution
    plt.figure(figsize=(10, 6))
    lateral = df[df['horizontal_lateral_length_ft'] > 0]['horizontal_lateral_length_ft']
    plt.hist(lateral, bins=50, color='#F4A261', alpha=0.7, edgecolor='black')
    plt.xlabel('Lateral Length [ft]', fontsize=12)
    plt.ylabel('Frequency', fontsize=12)
    plt.title(f'Lateral Length Distribution\nn={len(lateral):,} | mean={lateral.mean():.0f} ft | median={lateral.median():.0f} ft',
              fontsize=13, fontweight='bold')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(plots_dir / 'fracture_05_lateral_length.png', dpi=300, bbox_inches='tight')
    print(f"  ✓ Saved: fracture_05_lateral_length.png")
    plt.close()

    # 6. Total Proppant Distribution
    plt.figure(figsize=(10, 6))
    proppant = df[df['proppant_total_lb'] > 0]['proppant_total_lb'] / 1e6  # Convert to million lb
    plt.hist(proppant, bins=50, color='#2A9D8F', alpha=0.7, edgecolor='black')
    plt.xlabel('Total Proppant [million lb]', fontsize=12)
    plt.ylabel('Frequency', fontsize=12)
    plt.title(f'Total Proppant Distribution\nn={len(proppant):,} | mean={proppant.mean():.1f} Mlb | median={proppant.median():.1f} Mlb',
              fontsize=13, fontweight='bold')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(plots_dir / 'fracture_06_proppant.png', dpi=300, bbox_inches='tight')
    print(f"  ✓ Saved: fracture_06_proppant.png")
    plt.close()

    # 7. Fluid Volume Distribution
    plt.figure(figsize=(10, 6))
    fluid = df[df['frac_fluid_water_gal'] > 0]['frac_fluid_water_gal'] / 1e6  # Convert to million gal
    plt.hist(fluid, bins=50, color='#264653', alpha=0.7, edgecolor='black')
    plt.xlabel('Water Volume [million gal]', fontsize=12)
    plt.ylabel('Frequency', fontsize=12)
    plt.title(f'Frac Fluid Distribution\nn={len(fluid):,} | mean={fluid.mean():.1f} Mgal | median={fluid.median():.1f} Mgal',
              fontsize=13, fontweight='bold')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(plots_dir / 'fracture_07_fluid_volume.png', dpi=300, bbox_inches='tight')
    print(f"  ✓ Saved: fracture_07_fluid_volume.png")
    plt.close()

    # 8. Unconventional vs Conventional Comparison
    plt.figure(figsize=(12, 6))
    unconv = df[df['reservoir_type'] == 'unconventional']
    conv = df[df['reservoir_type'] == 'conventional']

    comparison = pd.DataFrame({
        'Unconventional': [
            unconv['fracture_stages_count'].mean(),
            unconv['horizontal_lateral_length_ft'].mean() / 1000,
            unconv['proppant_total_lb'].mean() / 1e6,
            unconv['frac_fluid_water_gal'].mean() / 1e6
        ],
        'Conventional': [
            conv['fracture_stages_count'].mean(),
            conv['horizontal_lateral_length_ft'].mean() / 1000,
            conv['proppant_total_lb'].mean() / 1e6,
            conv['frac_fluid_water_gal'].mean() / 1e6
        ]
    }, index=['Stages', 'Lateral (kft)', 'Proppant (Mlb)', 'Fluid (Mgal)'])

    x = np.arange(len(comparison.index))
    width = 0.35

    plt.bar(x - width/2, comparison['Unconventional'], width, label='Unconventional',
            color='#E63946', alpha=0.8, edgecolor='black')
    plt.bar(x + width/2, comparison['Conventional'], width, label='Conventional',
            color='#F1FAEE', alpha=0.8, edgecolor='black')

    plt.xlabel('Metric', fontsize=12)
    plt.ylabel('Value', fontsize=12)
    plt.title(f'Unconventional vs Conventional Completion Design\nUnconv: n={len(unconv):,} | Conv: n={len(conv):,}',
              fontsize=13, fontweight='bold')
    plt.xticks(x, comparison.index)
    plt.legend(fontsize=11)
    plt.grid(True, alpha=0.3, axis='y')
    plt.tight_layout()
    plt.savefig(plots_dir / 'fracture_08_comparison.png', dpi=300, bbox_inches='tight')
    print(f"  ✓ Saved: fracture_08_comparison.png")
    plt.close()

    # Print statistics
    print("\n--- Key Statistics ---")
    print(f"  Total Fracture Jobs: {len(df):,}")
    print(f"  Unconventional: {len(unconv):,} ({len(unconv)/len(df)*100:.1f}%)")
    print(f"  Conventional: {len(conv):,} ({len(conv)/len(df)*100:.1f}%)")
    print(f"\n  Unconventional Averages:")
    print(f"    Stages: {unconv['fracture_stages_count'].mean():.1f}")
    print(f"    Lateral: {unconv['horizontal_lateral_length_ft'].mean():.0f} ft")
    print(f"    Proppant: {unconv['proppant_total_lb'].mean():.2e} lb")
    print(f"    Fluid: {unconv['frac_fluid_water_gal'].mean():.2e} gal")


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Generate all individual plots."""

    print("="*70)
    print("ARGENTINA DATA SUMMARY - INDIVIDUAL PLOTS")
    print("="*70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # Paths
    base_dir = Path(__file__).parent.parent
    output_dir = base_dir / 'output'

    # Load Pyxis fields data
    print("\nLoading Pyxis fields data...")
    pyxis_file = output_dir / 'argentina_pyxis_fields_2025.csv'
    if pyxis_file.exists():
        pyxis_df = pd.read_csv(pyxis_file)
        print(f"  ✓ Loaded: {len(pyxis_df):,} records")
        plot_pyxis_fields(pyxis_df, output_dir)
    else:
        print(f"  ⚠️  File not found: {pyxis_file}")

    # Load fracture data
    print("\nLoading fracture well data...")
    fracture_file = output_dir / 'argentina_fracture_well_combined.csv'
    if fracture_file.exists():
        fracture_df = pd.read_csv(fracture_file)
        print(f"  ✓ Loaded: {len(fracture_df):,} records")
        plot_fracture_data(fracture_df, output_dir)
    else:
        print(f"  ⚠️  File not found: {fracture_file}")

    print("\n" + "="*70)
    print("✅ PLOT GENERATION COMPLETE")
    print("="*70)
    print(f"Plots saved to: {output_dir / 'plots'}")
    print(f"Total: 17 individual PNG files")
    print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")


if __name__ == "__main__":
    main()
