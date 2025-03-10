import pandas as pd
import geopandas as gpd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from utils.analysis_util import load_opgee_results
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from matplotlib.colors import LinearSegmentedColormap
from utils.path_util import DATA_PATH
from shapely import wkt


def load_basin_shapefile(filepath):
    basin_gdf = gpd.read_file(filepath)
    return basin_gdf


def load_pyxis_data(filepath):
    pyxis_data = pd.read_csv(filepath)
    pyxis_data["geometry"] = pyxis_data["geometry"].apply(wkt.loads)
    pyxis_fields_gdf = gpd.GeoDataFrame(
        pyxis_data, geometry="geometry", crs="EPSG:4326"
    )
    return pyxis_fields_gdf


def load_flare_data(filepath):
    flare_data = pd.read_csv(filepath)
    return flare_data


def prepare_merged_with_basin_gdf_for_impact(
    results_df, pyxis_fields_gdf, basin_gdf, flare_data
):
    # Prepare basin_gdf without suffixes for impact plot purposes
    basin_gdf["basin_name"] = basin_gdf["name"].str.replace(
        r"(_Mar|_Terra)$", "", regex=True
    )
    merged_basins_gdf = basin_gdf.dissolve(by="basin_name").reset_index()

    merged_gdf = pd.merge(results_df, pyxis_fields_gdf, on="Field name", how="left")
    merged_gdf = gpd.GeoDataFrame(
        merged_gdf, geometry="geometry", crs=pyxis_fields_gdf.crs
    )
    merged_basins_gdf = merged_basins_gdf.to_crs(merged_gdf.crs)
    merged_with_basin_gdf = gpd.sjoin(
        merged_gdf, merged_basins_gdf, how="left", predicate="within"
    )
    merged_with_basin_gdf = merged_with_basin_gdf[
        [
            "Field name",
            "Pyxis ID",
            "Oil Production",
            "Lifecycle GHG Emissions",
            "basin_name",
            "Gas-to-oil ratio (GOR)",
            "Offshore",
        ]
    ].merge(flare_data[["Pyxis ID", "Flaring-to-oil ratio"]], on="Pyxis ID", how="left")
    return merged_with_basin_gdf


def prepare_merged_with_basin_gdf_for_basin(
    basin_gdf, results_df, pyxis_fields_gdf, flare_data
):
    # Prepare basin_gdf with onshore/offshore suffix for basin plot purposes
    basin_gdf["basin_name"] = basin_gdf["name"].str.replace(
        r"_Mar$", "_Offshore", regex=True
    )
    basin_gdf["basin_name"] = basin_gdf["basin_name"].str.replace(
        r"_Terra$", "_Onshore", regex=True
    )

    merged_gdf = pd.merge(results_df, pyxis_fields_gdf, on="Field name", how="left")
    merged_gdf = gpd.GeoDataFrame(
        merged_gdf, geometry="geometry", crs=pyxis_fields_gdf.crs
    )
    basin_gdf = basin_gdf.to_crs(merged_gdf.crs)
    merged_with_basin_gdf = gpd.sjoin(
        merged_gdf, basin_gdf, how="left", predicate="within"
    )
    merged_with_basin_gdf = merged_with_basin_gdf[
        [
            "Field name",
            "Pyxis ID",
            "Oil Production",
            "Lifecycle GHG Emissions",
            "basin_name",
            "Gas-to-oil ratio (GOR)",
            "Offshore",
        ]
    ].merge(flare_data[["Pyxis ID", "Flaring-to-oil ratio"]], on="Pyxis ID", how="left")
    return merged_with_basin_gdf


def prepare_basin_avg(merged_with_basin_gdf):
    basin_avg = (
        merged_with_basin_gdf.groupby("basin_name")
        .apply(
            lambda x: pd.Series(
                {
                    "volume_weighted_CI": np.average(
                        x["Lifecycle GHG Emissions"], weights=x["Oil Production"]
                    ),
                    "average_FOR": x["Flaring-to-oil ratio"].mean(),
                    "total_production": x["Oil Production"].sum(),
                    "offshore_status": x["Offshore"].mode()[
                        0
                    ],  # Offshore/Onshore status based on the majority value
                }
            )
        )
        .reset_index()
    )
    basin_avg["average_FOR"].fillna(0, inplace=True)
    return basin_avg


def create_impact_plot(merged_with_basin_gdf, output_path, version=""):
    plt.rcParams["font.family"] = "Arial"
    plt.rcParams["font.size"] = 14

    merged_with_basin_gdf["Impact"] = (
        merged_with_basin_gdf["Oil Production"]
        * merged_with_basin_gdf["Lifecycle GHG Emissions"]
    )
    conditions = [
        (merged_with_basin_gdf["Gas-to-oil ratio (GOR)"] <= 100),
        (merged_with_basin_gdf["Gas-to-oil ratio (GOR)"] > 100)
        & (merged_with_basin_gdf["Gas-to-oil ratio (GOR)"] <= 500),
        (merged_with_basin_gdf["Gas-to-oil ratio (GOR)"] > 500)
        & (merged_with_basin_gdf["Gas-to-oil ratio (GOR)"] <= 1000),
        (merged_with_basin_gdf["Gas-to-oil ratio (GOR)"] > 1000)
        & (merged_with_basin_gdf["Gas-to-oil ratio (GOR)"] <= 5000),
        (merged_with_basin_gdf["Gas-to-oil ratio (GOR)"] > 5000)
        & (merged_with_basin_gdf["Gas-to-oil ratio (GOR)"] <= 10000),
        (merged_with_basin_gdf["Gas-to-oil ratio (GOR)"] > 10000),
    ]

    colors = ["red", "orange", "yellow", "lightgreen", "seagreen", "darkgreen"]
    merged_with_basin_gdf["color"] = np.select(conditions, colors)
    merged_with_basin_gdf = merged_with_basin_gdf.sort_values(
        by="Lifecycle GHG Emissions"
    )

    merged_with_basin_gdf["width"] = (
        merged_with_basin_gdf["Oil Production"]
        / merged_with_basin_gdf["Oil Production"].sum()
    )
    merged_with_basin_gdf["cumulative_x"] = (
        merged_with_basin_gdf["width"].cumsum() - merged_with_basin_gdf["width"]
    )

    volume_weighted_avg_CI = (
        merged_with_basin_gdf["Lifecycle GHG Emissions"]
        * merged_with_basin_gdf["Oil Production"]
    ).sum() / merged_with_basin_gdf["Oil Production"].sum()

    plt.figure(figsize=(12, 6), dpi=300)
    hatch_patterns = {"Santos": "///", "Campos": "...", "Others": ""}

    for i, row in merged_with_basin_gdf.iterrows():
        hatch = hatch_patterns.get(row["basin_name"], hatch_patterns["Others"])
        plt.bar(
            row["cumulative_x"],
            row["Lifecycle GHG Emissions"],
            color=row["color"],
            width=row["width"],
            edgecolor="k",
            alpha=0.6,
            align="edge",
            hatch=hatch,
        )

    plt.axhline(
        y=volume_weighted_avg_CI,
        color="k",
        linestyle="--",
        linewidth=1,
        label=f"Volume-Weighted Avg CI: {volume_weighted_avg_CI:.2f}",
    )
    plt.text(
        0.05,
        volume_weighted_avg_CI + 0.5,
        f"The volume-weighted average upstream CI: {volume_weighted_avg_CI:.2f} gCO$_2$eq/MJ",
        verticalalignment="bottom",
        horizontalalignment="left",
        color="black",
        fontsize=10,
    )

    top_fields = merged_with_basin_gdf.nlargest(3, "Impact")
    for i, row in top_fields.iterrows():
        plt.annotate(
            row["Field name"],
            xy=(row["cumulative_x"] + row["width"] / 2, row["Lifecycle GHG Emissions"]),
            xytext=(
                row["cumulative_x"] + row["width"] / 2,
                row["Lifecycle GHG Emissions"] + 5,
            ),
            arrowprops=dict(facecolor="black", arrowstyle="->"),
            ha="center",
            fontsize=10,
            color="black",
        )

    plt.ylim(0, 30)
    plt.xlim(0, 1)
    plt.xlabel("Cumulative Oil Production (%)")
    plt.ylabel("Lifecycle GHG Emissions (gCO$_2$eq/MJ)")
    plt.title("Lifecycle GHG Emissions per Field with GOR and Basin Categories")

    x_ticks = np.linspace(0, 1, num=6)
    x_labels = [f"{int(tick * 100)}%" for tick in x_ticks]
    plt.xticks(x_ticks, x_labels)

    legend_labels = [
        r"(0, 100]",
        r"(100, 500]",
        r"(500, 1000]",
        r"(1000, 5000]",
        r"(5000, 10000]",
        r"(10000, Inf)",
    ]
    legend_handles = [
        Patch(facecolor=col, label=label) for col, label in zip(colors, legend_labels)
    ]

    hatch_legend = [
        Patch(facecolor="white", edgecolor="k", hatch="///", label="Santos"),
        Patch(facecolor="white", edgecolor="k", hatch="...", label="Campos"),
        Patch(facecolor="white", edgecolor="k", hatch="", label="Other Basins"),
    ]

    plt.legend(
        handles=legend_handles + hatch_legend,
        title="GOR and Basin Categories",
        frameon=False,
        loc="upper left",
    )

    ax1 = plt.gca()
    ax2 = ax1.twiny()

    annual_production_million_bbl_d = (
        merged_with_basin_gdf["Oil Production"].sum() / 1e3
    )
    top_x_ticks = np.linspace(0, 1, num=6)
    top_x_labels = [
        f"{int(tick * annual_production_million_bbl_d)}" for tick in top_x_ticks
    ]
    ax2.set_xlim(ax1.get_xlim())
    ax2.set_xticks(top_x_ticks)
    ax2.set_xticklabels(top_x_labels)
    ax2.set_xlabel("Cumulative Oil Production (thousand bbl/d)")
    ax2.tick_params(direction="in")

    plt.savefig(output_path, format="png", dpi=300)
    plt.show()
    return volume_weighted_avg_CI


def create_basin_plots(basin_shapefile, basin_avg, output_path, volume_weighted_avg_CI):
    plt.rcParams["font.family"] = "Arial"
    plt.rcParams["font.size"] = 14

    # # Calculate volume-weighted average CI based on production volumes
    # volume_weighted_avg_CI = (basin_avg['volume_weighted_CI'] * basin_avg['total_production']).sum() / basin_avg['total_production'].sum()

    # Sort basin_avg by total production volume
    basin_avg = basin_avg.sort_values(by="total_production", ascending=False)

    fig, (ax1, ax2, ax3) = plt.subplots(
        nrows=1,
        ncols=3,
        figsize=(20, 10),
        dpi=300,
        gridspec_kw={"width_ratios": [1, 1, 2.5]},
    )

    # Plot the volume-weighted CI
    offshore_color = "#006CB8"  # Blue for offshore
    onshore_color = "#B1040E"  # Red for onshore
    bars1 = ax1.barh(
        basin_avg["basin_name"],
        basin_avg["volume_weighted_CI"],
        color=[
            offshore_color if status else onshore_color
            for status in basin_avg["offshore_status"]
        ],
        edgecolor="k",
    )
    ax1.axvline(
        x=volume_weighted_avg_CI,
        color="black",
        linestyle="--",
        linewidth=1,
        label=f"Avg CI: {volume_weighted_avg_CI:.2f}",
    )
    ax1.set_xlabel("Volume-Weighted Average CI (gCO$_2$eq/MJ)")
    ax1.invert_yaxis()

    # Add legend
    offshore_patch = Patch(color=offshore_color, label="Offshore")
    onshore_patch = Patch(color=onshore_color, label="Onshore")
    handles, labels = ax1.get_legend_handles_labels()
    handles.extend([offshore_patch, onshore_patch])
    ax1.legend(handles=handles, loc="lower right")

    # Plot the total production
    bars2 = ax2.barh(
        basin_avg["basin_name"],
        basin_avg["total_production"],
        color="#008566",
        edgecolor="k",
    )
    ax2.set_xlabel("Oil Production (bbl/d)")
    ax2.invert_yaxis()
    ax2.set_yticklabels([])

    # Plot the map with the basin shapefiles and average_FOR values
    basin_gdf = gpd.read_file(basin_shapefile)
    basin_gdf["basin_name"] = basin_gdf["name"].str.replace(
        r"_Mar$", "_Offshore", regex=True
    )
    basin_gdf["basin_name"] = basin_gdf["basin_name"].str.replace(
        r"_Terra$", "_Onshore", regex=True
    )
    basin_gdf_mt = basin_gdf.merge(
        basin_avg, left_on="basin_name", right_on="basin_name", how="inner"
    )

    ax3 = plt.subplot(133, projection=ccrs.PlateCarree())
    ax3.set_extent([-75, -30, -35, 10])
    ax3.add_feature(
        cfeature.LAND, zorder=0, edgecolor="black", facecolor="white", alpha=0.3
    )
    ax3.add_feature(cfeature.COASTLINE)
    ax3.add_feature(cfeature.BORDERS, linestyle=":")

    cmap = LinearSegmentedColormap.from_list("custom_cmap", ["#e9c716", "#bc272d"])
    norm = plt.Normalize(
        basin_gdf_mt["average_FOR"].min(), basin_gdf_mt["average_FOR"].max()
    )

    basin_gdf_mt.plot(
        column="average_FOR",
        cmap=cmap,
        linewidth=0.8,
        ax=ax3,
        edgecolor="1",
        legend=False,
        zorder=2,
    )
    for idx, row in basin_gdf_mt.iterrows():
        ax3.text(
            row.geometry.centroid.x,
            row.geometry.centroid.y,
            row["basin_name"],
            fontsize=8,
            ha="center",
            zorder=3,
        )

    sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax3, orientation="vertical", fraction=0.05, pad=0.05)
    cbar.set_label("Average FOR (scf/bbl)")

    fig.text(
        0.7, 0.07, "Basin Level Flaring-to-Oil Ratio (FOR)", ha="center", fontsize=12
    )

    # Adjust layout
    plt.subplots_adjust(wspace=0.1)
    plt.savefig(output_path, format="png", dpi=300)
    plt.show()


def main():
    version = "withwm"
    excel_path = f"{DATA_PATH}/OPGEE_model/OPGEE_3.0c_BETA_BR_" + version + ".xlsm"
    basin_shapefile = f"{DATA_PATH}/br_geodata/br_basin_shp/bacias_gishub_db.shp"
    pyxis_data_path = (
        f"{DATA_PATH}/br_geodata/merged_pyxis_field_info_table_filtered_"
        + version
        + ".csv"
    )
    flare_data_path = (
        f"{DATA_PATH}/br_geodata/merged_pyxis_field_info_with_flare_" + version + ".csv"
    )
    impact_plot_output_path = (
        f"{DATA_PATH}/br_geodata/plots/Field_CI_Plot_GOR_Basin_" + version + ".png"
    )
    basin_plot_output_path = (
        f"{DATA_PATH}/br_geodata/plots/Basin_CI_Plot_with_production_and_for_"
        + version
        + ".png"
    )

    results_df = load_opgee_results(excel_path, 279)
    basin_gdf = load_basin_shapefile(basin_shapefile)
    pyxis_fields_gdf = load_pyxis_data(pyxis_data_path)
    flare_data = load_flare_data(flare_data_path)

    # Prepare merged_with_basin_gdf for impact plot
    merged_with_basin_gdf_impact = prepare_merged_with_basin_gdf_for_impact(
        results_df, pyxis_fields_gdf, basin_gdf, flare_data
    )
    # Prepare merged_with_basin_gdf for basin plot
    merged_with_basin_gdf_basin = prepare_merged_with_basin_gdf_for_basin(
        basin_gdf, results_df, pyxis_fields_gdf, flare_data
    )
    basin_avg = prepare_basin_avg(merged_with_basin_gdf_basin)

    # Create plots
    volume_weighted_avg_CI = create_impact_plot(
        merged_with_basin_gdf_impact, impact_plot_output_path, "with WM"
    )
    create_basin_plots(
        basin_shapefile, basin_avg, basin_plot_output_path, volume_weighted_avg_CI
    )


if __name__ == "__main__":
    main()
