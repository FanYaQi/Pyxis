"""
Side-by-side comparison of Carbon Mapper and IMEO methane plumes in Argentina.
"""

import math
import warnings
from pathlib import Path
from typing import Optional, List, Tuple

import matplotlib.pyplot as plt
import matplotlib.lines as mlines
import numpy as np
import pandas as pd

try:
    import geopandas as gpd
except ImportError as exc:
    raise SystemExit(
        "geopandas is required. Install with: pip install geopandas"
    ) from exc

# Suppress deprecation warnings for naturalearth_lowres
warnings.filterwarnings("ignore", category=FutureWarning)

# Style configuration
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.size": 10,
    "axes.titlesize": 13,
    "axes.labelsize": 10,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "axes.edgecolor": "#cccccc",
    "axes.linewidth": 0.8,
    "grid.color": "#e0e0e0",
    "grid.linewidth": 0.4,
    "axes.spines.top": False,
    "axes.spines.right": False,
})

# Color palette
CM_COLOR = "#2171b5"  # Blue for Carbon Mapper
IMEO_COLOR = "#cb181d"  # Red for IMEO
ARGENTINA_COLOR = "#f7f7f7"
NEIGHBOR_COLOR = "#e8e8e8"
BORDER_COLOR = "#888888"
ARGENTINA_BORDER = "#444444"


def pick_latest_cm_file(cm_dir: Path) -> Path:
    candidates = sorted(cm_dir.glob("argentina_og_plumes_*_raw.csv"))
    if not candidates:
        raise FileNotFoundError(f"No CM raw files found in {cm_dir}")
    return candidates[-1]


def scale_sizes(
    values: pd.Series,
    min_size: float = 30.0,
    max_size: float = 400.0,
    vmin: Optional[float] = None,
    vmax: Optional[float] = None,
) -> pd.Series:
    """Scale emission values to marker sizes using square root scaling."""
    clean = pd.to_numeric(values, errors="coerce").fillna(0)
    if clean.nunique() <= 1:
        return pd.Series([min_size] * len(clean), index=clean.index)
    vmin = clean.min() if vmin is None else vmin
    vmax = clean.max() if vmax is None else vmax
    # Square root scaling for area-proportional perception
    denom = max(vmax - vmin, 1e-9)
    normalized = ((clean - vmin) / denom).clip(lower=0, upper=1)
    scaled = np.sqrt(normalized)
    scaled_sizes = min_size + scaled * (max_size - min_size)
    return scaled_sizes.fillna(min_size).clip(lower=min_size, upper=max_size)


def load_cm_plumes(cm_path: Path) -> pd.DataFrame:
    df = pd.read_csv(cm_path)
    df = df[df["gas"].eq("CH4")].copy()
    df = df[df["is_offshore"].eq(False)].copy()
    df.rename(columns={"longitude": "lon", "latitude": "lat"}, inplace=True)
    df["plume_size"] = df["emission_auto"].astype(float)
    return df


def load_imeo_plumes(imeo_path: Path) -> pd.DataFrame:
    df = pd.read_csv(imeo_path)
    df = df[df["country"].eq("Argentina")].copy()
    df = df[df["sector"].eq("Oil and Gas")].copy()
    df.rename(columns={"lon": "lon", "lat": "lat"}, inplace=True)
    df["plume_size"] = df["ch4_fluxrate"].astype(float)
    return df


def load_boundaries() -> Tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
    """Load Argentina and neighboring countries boundaries from Natural Earth."""
    # Natural Earth 110m cultural vectors (small file, fast download)
    url = "https://naturalearth.s3.amazonaws.com/110m_cultural/ne_110m_admin_0_countries.zip"

    try:
        world = gpd.read_file(url)
        name_col = "NAME"
    except Exception as e:
        raise RuntimeError(
            f"Could not download Natural Earth data: {e}\n"
            "Please check your internet connection."
        ) from e

    argentina = world[world[name_col].eq("Argentina")]

    # Get South American neighbors for context
    sa_countries = [
        "Argentina", "Chile", "Uruguay", "Paraguay", "Bolivia",
        "Brazil", "Peru"
    ]
    neighbors = world[world[name_col].isin(sa_countries)]

    return argentina, neighbors


def get_nice_legend_values(vmin: float, vmax: float) -> List[int]:
    """Generate nice round numbers for the legend within data range."""
    candidates = [100, 200, 500, 1000, 2000, 5000, 10000, 20000]
    values = [v for v in candidates if vmin <= v <= vmax]

    if len(values) < 2:
        values = [int(vmin), int((vmin + vmax) / 2), int(vmax)]
    elif len(values) > 4:
        step = max(1, len(values) // 3)
        values = [values[0], values[step], values[min(2 * step, len(values) - 1)], values[-1]]

    return values


def build_shared_legend(legend_values: List[int], legend_sizes: List[float], legend_title: str):
    """Build legend handles and labels."""
    handles = []
    labels = []
    for raw, size in zip(legend_values, legend_sizes):
        handles.append(
            mlines.Line2D(
                [0], [0],
                marker="o",
                markersize=math.sqrt(size),
                markerfacecolor="none",
                markeredgecolor="#333333",
                markeredgewidth=1.2,
                linestyle="None",
            )
        )
        labels.append(f"{int(raw):,}")
    return handles, labels, legend_title


def style_ax(ax, argentina, neighbors, xlim, ylim, title, show_ylabel=True):
    """Style a map axis with Argentina basemap."""
    # Plot neighboring countries first (lighter)
    neighbors.plot(ax=ax, color=NEIGHBOR_COLOR, edgecolor=BORDER_COLOR, linewidth=0.5, zorder=1)
    # Plot Argentina on top (highlighted)
    argentina.plot(ax=ax, color=ARGENTINA_COLOR, edgecolor=ARGENTINA_BORDER, linewidth=1.0, zorder=2)

    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_title(title, fontsize=13, fontweight="medium", pad=10)
    ax.set_xlabel("Longitude", fontsize=10)
    if show_ylabel:
        ax.set_ylabel("Latitude", fontsize=10)
    else:
        ax.set_ylabel("")

    # Light grid
    ax.grid(True, alpha=0.3, linestyle="-", linewidth=0.3, zorder=0)
    ax.set_axisbelow(True)

    # Clean up spines
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_color("#cccccc")
        spine.set_linewidth(0.5)


def plot_plumes(ax, lons, lats, sizes, color, label):
    """Plot plume scatter points."""
    ax.scatter(
        lons, lats,
        s=sizes,
        facecolors="none",
        edgecolors=color,
        linewidths=1.3,
        alpha=0.75,
        zorder=3,
        label=label,
    )


def add_data_counts(ax, n_plumes, color):
    """Add plume count annotation."""
    ax.text(
        0.98, 0.02,
        f"n = {n_plumes}",
        transform=ax.transAxes,
        ha="right", va="bottom",
        fontsize=10,
        color=color,
        fontweight="medium",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor="none", alpha=0.8),
    )


def summarize_plumes(df: pd.DataFrame, label: str) -> pd.Series:
    """Return summary stats for plume sizes."""
    series = pd.to_numeric(df["plume_size"], errors="coerce").dropna()
    stats = series.describe(percentiles=[0.1, 0.25, 0.5, 0.75, 0.9])
    stats["sum"] = series.sum()
    stats.name = label
    return stats


def print_stats_table(stats_list: List[pd.Series], title: str) -> pd.DataFrame:
    """Print a compact stats table for plume sizes and return as DataFrame."""
    if not stats_list:
        return pd.DataFrame()
    table = pd.DataFrame(stats_list)
    cols = [
        "count", "min", "10%", "25%", "50%", "75%", "90%", "mean", "max", "std", "sum"
    ]
    table = table[[c for c in cols if c in table.columns]]
    print(f"\n{title}")
    print(table.to_string(float_format=lambda v: f"{v:,.2f}"))
    return table


def main() -> None:
    base_dir = Path(__file__).resolve().parents[1]
    cm_dir = base_dir / "methane_CM_raw"
    imeo_path = (
        base_dir
        / "methane_raw_imeo"
        / "_downloads_unep_methanedata_detected_plumes_csv"
        / "unep_methanedata_detected_plumes.csv"
    )
    cm_path = pick_latest_cm_file(cm_dir)

    print(f"Loading CM data from: {cm_path.name}")
    print(f"Loading IMEO data from: {imeo_path.name}")

    cm = load_cm_plumes(cm_path)
    imeo = load_imeo_plumes(imeo_path)
    cm["plume_size"] = pd.to_numeric(cm["plume_size"], errors="coerce")
    imeo["plume_size"] = pd.to_numeric(imeo["plume_size"], errors="coerce")

    print(f"  CM plumes: {len(cm)}")
    print(f"  IMEO plumes: {len(imeo)}")
    all_stats = print_stats_table(
        [summarize_plumes(cm, "CM (all)"), summarize_plumes(imeo, "IMEO (all)")],
        "Plume size stats (kg CH4/hr): all Argentina plumes",
    )

    # Load map boundaries
    argentina, neighbors = load_boundaries()

    # Argentina extent with padding
    bounds = argentina.total_bounds  # minx, miny, maxx, maxy
    pad_x = (bounds[2] - bounds[0]) * 0.08
    pad_y = (bounds[3] - bounds[1]) * 0.08
    xlim = (bounds[0] - pad_x, bounds[2] + pad_x)
    ylim = (bounds[1] - pad_y, bounds[3] + pad_y)

    # Combine for consistent scaling across both plots
    combined_sizes = pd.concat([cm["plume_size"], imeo["plume_size"]], ignore_index=True)
    combined_min = combined_sizes.min()
    combined_max = combined_sizes.max()

    # Nice round legend values
    legend_values = get_nice_legend_values(combined_min, combined_max)
    legend_sizes = scale_sizes(
        pd.Series(legend_values), min_size=40, max_size=500, vmin=combined_min, vmax=combined_max
    ).tolist()

    cm_sizes = scale_sizes(
        cm["plume_size"], min_size=40, max_size=500, vmin=combined_min, vmax=combined_max
    )
    imeo_sizes = scale_sizes(
        imeo["plume_size"], min_size=40, max_size=500, vmin=combined_min, vmax=combined_max
    )

    # Create figure
    fig, axes = plt.subplots(1, 2, figsize=(12, 12))
    fig.subplots_adjust(bottom=0.15, wspace=0.02, left=0.06, right=0.98, top=0.90)

    # Style both axes
    style_ax(axes[0], argentina, neighbors, xlim, ylim, "Carbon Mapper", show_ylabel=True)
    style_ax(axes[1], argentina, neighbors, xlim, ylim, "IMEO", show_ylabel=False)

    # Plot plumes
    plot_plumes(axes[0], cm["lon"], cm["lat"], cm_sizes, CM_COLOR, "CM")
    plot_plumes(axes[1], imeo["lon"], imeo["lat"], imeo_sizes, IMEO_COLOR, "IMEO")

    # Add counts
    add_data_counts(axes[0], len(cm), CM_COLOR)
    add_data_counts(axes[1], len(imeo), IMEO_COLOR)

    # Build and add shared legend at bottom center
    handles, labels, legend_title = build_shared_legend(
        legend_values, legend_sizes, "Emission Rate (kg CH\u2084/hr)"
    )
    fig.legend(
        handles, labels,
        title=legend_title,
        loc="lower center",
        ncol=len(legend_values),
        frameon=True,
        framealpha=0.95,
        edgecolor="#cccccc",
        bbox_to_anchor=(0.5, 0.02),
        fontsize=10,
        title_fontsize=10,
    )

    # Main title
    fig.suptitle(
        "Argentina Oil & Gas Methane Plumes",
        fontsize=15,
        fontweight="bold",
        y=0.96,
    )

    # Attribution
    fig.text(
        0.98, 0.005,
        "Data: Carbon Mapper, UNEP IMEO | Basemap: Natural Earth",
        ha="right", va="bottom",
        fontsize=8,
        color="#666666",
        style="italic",
    )

    # Save
    output_dir = base_dir / "methane_CM_processed"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "argentina_plumes_cm_imeo_side_by_side.png"
    fig.savefig(output_path, dpi=200, bbox_inches="tight", facecolor="white")
    print(f"\nSaved: {output_path}")
    if not all_stats.empty:
        all_stats_path = output_dir / "argentina_plumes_cm_imeo_stats_all.csv"
        all_stats.to_csv(all_stats_path)
        print(f"Saved stats: {all_stats_path}")

    # --- Matched plumes plot ---
    matched_candidates = sorted(output_dir.glob("matched_plumes_cm_imeo_*.csv"))
    if matched_candidates:
        matched = pd.read_csv(matched_candidates[-1])
        print(f"\nLoading matched plumes: {matched_candidates[-1].name}")
        print(f"  Matched pairs: {len(matched)}")

        matched_cm = matched.rename(columns={
            "cm_longitude": "lon",
            "cm_latitude": "lat",
            "cm_emission_kg_hr": "plume_size",
        })
        matched_imeo = matched.rename(columns={
            "imeo_longitude": "lon",
            "imeo_latitude": "lat",
            "imeo_emission_kg_hr": "plume_size",
        })
        matched_cm["plume_size"] = pd.to_numeric(matched_cm["plume_size"], errors="coerce")
        matched_imeo["plume_size"] = pd.to_numeric(matched_imeo["plume_size"], errors="coerce")
        matched_stats = print_stats_table(
            [
                summarize_plumes(matched_cm, "CM (matched)"),
                summarize_plumes(matched_imeo, "IMEO (matched)"),
            ],
            "Plume size stats (kg CH4/hr): matched plumes",
        )

        matched_cm_sizes = scale_sizes(
            matched_cm["plume_size"], min_size=40, max_size=500, vmin=combined_min, vmax=combined_max
        )
        matched_imeo_sizes = scale_sizes(
            matched_imeo["plume_size"], min_size=40, max_size=500, vmin=combined_min, vmax=combined_max
        )

        fig2, axes2 = plt.subplots(1, 2, figsize=(12, 12))
        fig2.subplots_adjust(bottom=0.15, wspace=0.02, left=0.06, right=0.98, top=0.90)

        style_ax(axes2[0], argentina, neighbors, xlim, ylim, "Carbon Mapper (matched)", show_ylabel=True)
        style_ax(axes2[1], argentina, neighbors, xlim, ylim, "IMEO (matched)", show_ylabel=False)

        plot_plumes(axes2[0], matched_cm["lon"], matched_cm["lat"], matched_cm_sizes, CM_COLOR, "CM")
        plot_plumes(axes2[1], matched_imeo["lon"], matched_imeo["lat"], matched_imeo_sizes, IMEO_COLOR, "IMEO")

        add_data_counts(axes2[0], len(matched_cm), CM_COLOR)
        add_data_counts(axes2[1], len(matched_imeo), IMEO_COLOR)

        fig2.legend(
            handles, labels,
            title=legend_title,
            loc="lower center",
            ncol=len(legend_values),
            frameon=True,
            framealpha=0.95,
            edgecolor="#cccccc",
            bbox_to_anchor=(0.5, 0.02),
            fontsize=10,
            title_fontsize=10,
        )

        fig2.suptitle(
            "Argentina Oil & Gas Methane Plumes (Matched Only)",
            fontsize=15,
            fontweight="bold",
            y=0.96,
        )

        fig2.text(
            0.98, 0.005,
            "Data: Carbon Mapper, UNEP IMEO | Basemap: Natural Earth",
            ha="right", va="bottom",
            fontsize=8,
            color="#666666",
            style="italic",
        )

        matched_output = output_dir / "argentina_plumes_cm_imeo_matched_side_by_side.png"
        fig2.savefig(matched_output, dpi=200, bbox_inches="tight", facecolor="white")
        print(f"Saved: {matched_output}")
        if not matched_stats.empty:
            matched_stats_path = output_dir / "argentina_plumes_cm_imeo_stats_matched.csv"
            matched_stats.to_csv(matched_stats_path)
            print(f"Saved stats: {matched_stats_path}")

    plt.close("all")
    print("\nDone!")


if __name__ == "__main__":
    main()
