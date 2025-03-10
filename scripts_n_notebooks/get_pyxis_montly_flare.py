import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
from shapely import wkt
import numpy as np
from utils.path_util import DATA_PATH

BCM2scf = 35314666572.222


# Load flare data
def load_flare_data(filepath, country, year):
    flare_month = pd.read_csv(filepath)
    # Filter flare data by country and year
    flare_filtered = flare_month[
        (flare_month["country"] == country) & (flare_month["year"] == year)
    ]
    # Convert to GeoDataFrame
    flare_filtered["geometry"] = flare_filtered.apply(
        lambda row: Point(row["lon"], row["lat"]), axis=1
    )
    flare_gdf = gpd.GeoDataFrame(flare_filtered, geometry="geometry", crs="EPSG:4326")
    return flare_gdf


# Load field data and parse geometry
def load_field_data(filepath):
    field_data = pd.read_csv(filepath)
    field_data["geometry"] = field_data["geometry"].apply(wkt.loads)
    field_gdf = gpd.GeoDataFrame(field_data, geometry="geometry", crs="EPSG:4326")
    return field_gdf


# Match flares to fields and calculate monthly flare volumes
def match_flares_to_fields(flare_gdf, field_gdf):
    # Match flares within field boundaries
    matches_initial = gpd.sjoin(flare_gdf, field_gdf, how="left", predicate="within")
    matches_initial["matched"] = ~matches_initial.index_right.isna()
    matches_initial["weight"] = 1  # Initialize weight to 1 for each matched flare

    # Step 1: Handle overlapping fields if a flare matches multiple fields
    matches_within_fields = matches_initial[matches_initial["matched"]]
    if not matches_within_fields.empty:
        overlaps = matches_within_fields.groupby(["id", "month"]).filter(
            lambda x: len(x) > 1
        )
        if not overlaps.empty:
            overlaps["weight"] = overlaps["Oil production volume"] / overlaps.groupby(
                ["id", "month"]
            )["Oil production volume"].transform("sum")
            matches_within_fields = pd.concat(
                [matches_within_fields.drop(overlaps.index), overlaps]
            )

    # Step 2: Extend field boundaries by 5 km to match more flares
    buffered_fields = field_gdf.copy()
    buffered_fields["geometry"] = buffered_fields.geometry.buffer(
        0.05
    )  # 5 km buffer in degrees
    extended_matches = gpd.sjoin(
        flare_gdf[~flare_gdf["id"].isin(matches_within_fields["id"])],
        buffered_fields,
        how="left",
        predicate="within",
    )
    extended_matches["extended_matched"] = ~extended_matches.index_right.isna()
    extended_matches[
        "weight"
    ] = 1  # Initialize weight to 1 for each extended matched flare

    # Step 3: Assign extended flare volumes, considering overlaps
    if not extended_matches.empty:
        extended_overlaps = extended_matches.groupby(["id", "month"]).filter(
            lambda x: len(x) > 1
        )
        if not extended_overlaps.empty:
            extended_overlaps["weight"] = extended_overlaps[
                "Oil production volume"
            ] / extended_overlaps.groupby(["id", "month"])[
                "Oil production volume"
            ].transform(
                "sum"
            )
            extended_matches = pd.concat(
                [extended_matches.drop(extended_overlaps.index), extended_overlaps]
            )

    # Combine the results from initial matches and extended matches without double-counting
    all_matches = pd.concat([matches_within_fields, extended_matches], axis=0)
    all_matches = all_matches[
        ~all_matches["index_right"].isna()
    ]  # Filter out NaN values
    all_matches["Oil production volume"] = all_matches["Oil production volume"].apply(
        lambda x: x if pd.notna(x) and x > 0 else 1
    )  # Assign a small value of 1 bbl/d if None or zero

    # Calculate the flare contribution to each field based on weight, ensuring weights sum up to 1 for each month
    all_matches["weighted_volume"] = all_matches["BCM"] * all_matches["weight"]
    weight_sums = (
        all_matches.groupby(["id", "month"])["weight"]
        .sum()
        .reset_index()
        .rename(columns={"weight": "weight_sum"})
    )
    all_matches = pd.merge(all_matches, weight_sums, on=["id", "month"], how="left")
    all_matches["weight"] = all_matches["weight"] / all_matches["weight_sum"]
    all_matches["weighted_volume"] = all_matches["BCM"] * all_matches["weight"]

    # Ensure consistent month format by converting month to a numeric representation (1 to 12)
    all_matches["month"] = (
        all_matches["month"].astype(str).str.extract(r"(\d{1,2})").astype(int)
    )

    # Group by field, month, and flare ID to calculate monthly flare volume considering weighted volumes
    monthly_flare_match = (
        all_matches.groupby(["index_right", "month"])
        .agg({"weighted_volume": "sum"})
        .reset_index()
    )

    # Create a DataFrame with all fields and all 12 months
    all_fields_months = pd.MultiIndex.from_product(
        [field_gdf.index, range(1, 13)], names=["index_right", "month"]
    ).to_frame(index=False)
    monthly_flare_summary = pd.merge(
        all_fields_months, monthly_flare_match, on=["index_right", "month"], how="left"
    ).fillna(0)

    # Add field names to the DataFrame
    result = monthly_flare_summary.merge(
        field_gdf[["Field name"]], left_on="index_right", right_index=True, how="left"
    )
    result = result[["Field name", "month", "weighted_volume"]]
    result.rename(columns={"weighted_volume": "flare_volume"}, inplace=True)

    return result


# Main function to load data and perform flare matching
def main():
    # Load flare data and field data
    flare_gdf = load_flare_data(
        f"{DATA_PATH}/br_geodata/flare_2021/flare_2021_month.csv", "Brazil", 2021
    )
    field_gdf = load_field_data(
        f"{DATA_PATH}/br_geodata/merged_pyxis_field_info_table_filtered_withwm.csv"
    )

    # Perform the matching
    monthly_flare_data = match_flares_to_fields(flare_gdf, field_gdf)

    # Save the matched monthly flare data to a CSV file
    monthly_flare_data.to_csv(
        f"{DATA_PATH}/br_geodata/flare_2021/pyxis_field_monthly_flare_match_2021.csv",
        index=False,
    )
    print(
        "Monthly flare data matched to Pyxis fields and saved to 'pyxis_field_monthly_flare_match_2021.csv'"
    )


if __name__ == "__main__":
    main()
