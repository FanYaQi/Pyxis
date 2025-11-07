import pandas as pd
import numpy as np
from utils.path_util import DATA_PATH
import json
import geopandas as gpd
from shapely import wkt
from shapely.ops import unary_union
import h3
import datetime

with open(f"{DATA_PATH}/OPGEE_cols.json", "r") as json_file:
    OPGEE_cols = json.load(json_file)


def load_merge_rules(json_path):
    """Load merge rules from a JSON file"""
    with open(json_path, "r") as file:
        return json.load(file)


def apply_merge_rule(data, rule):
    """Apply a merge rule to a list of data"""
    if not data:  # Early exit if data list is empty
        return None
    if rule == "average":
        return np.average(data)
    elif rule == "average int":
        return int(np.median(data))
    elif rule == "median":
        return np.median(data)
    elif rule == "median int":
        return int(np.median(data))
    elif rule == "most frequent":
        return max(set(data), key=data.count)
    elif rule == "avg_age":
        return int(datetime.datetime.now().year - np.average(data))
    return data  # Return as is if no rule matches


def load_data(file_path):
    """Load data from an Excel file"""
    return pd.read_csv(file_path)


def dissolve_geometries(geometries):
    """Dissolve geometries into a single geometry, ensuring all are valid WKT before processing."""
    valid_geometries = []
    for geom in geometries:
        try:
            # Ensure the geometry is valid and not None or empty
            if geom and geom != "None" and geom.strip():
                shapely_geom = wkt.loads(geom)
                valid_geometries.append(shapely_geom)
        except Exception as e:
            print(f"Error loading geometry: with error {e}")

    if valid_geometries:
        merged_geometry = unary_union(valid_geometries)
        centroid = merged_geometry.centroid
        centroid_h3_index = h3.geo_to_h3(centroid.y, centroid.x, resolution=9)
        return merged_geometry, centroid_h3_index
    else:
        return None, None


def merge_data(pyxis_match_table, source_info_tables, merge_rules):
    detailed_merge = []

    for pyxis_id, group in pyxis_match_table.groupby("Pyxis ID"):
        opgee_data = {col: [] for col in merge_rules}  # Data for merge rules
        detailed_fields = {col: [] for col in merge_rules}  # Detailed in-use fields
        geometries = []  # List to collect geometries for each Pyxis ID

        # Process each row associated with the current Pyxis ID
        for _, row in group.iterrows():
            source_info = source_info_tables.get(row["Source ID"])
            if (
                source_info is not None
                and row["Field ID"] in source_info["Field ID"].values
            ):
                source_row = source_info[
                    source_info["Field ID"] == row["Field ID"]
                ].iloc[0]

                for col in merge_rules:
                    if pd.notna(source_row[col]):  # Ensure the data is not null
                        opgee_data[col].append(source_row[col])
                        detailed_fields[col].append(
                            (source_row["Source Name"], row["Field ID"])
                        )

                # Collect geometry for each valid source entry
                if source_row["geometry"] is not None:
                    geometries.append(source_row["geometry"])

        # Dissolve geometries
        merged_geometry, centroid_h3_index = dissolve_geometries(geometries)

        # Apply merge rules for each OPGEE column
        merged_values = {
            col: apply_merge_rule(opgee_data[col], merge_rules[col])
            for col in merge_rules
        }

        # Prepare the detailed in-use field information
        detailed_in_use = {col: values for col, values in detailed_fields.items()}

        # Construct the merged record
        merged_record = {
            "Pyxis ID": pyxis_id,
            "Name": group.sort_values(by="Match Score", ascending=False).iloc[0][
                "Name"
            ],
            "Centroid H3 Index": centroid_h3_index,
            "Source ID used": ", ".join(set(group["Source ID"])),
            **merged_values,
            "geometry": merged_geometry,
            "Detailed in use field": detailed_in_use,
        }
        detailed_merge.append(merged_record)

    return pd.DataFrame(detailed_merge)


def main():
    # File paths
    merge_rules_path = f"{DATA_PATH}/OPGEE_cols_merge_rules.json"
    pyxis_match_path = f"{DATA_PATH}/br_geodata/pyxis_match_table_filtered_withwm.csv"
    source_info_paths = {
        "zhan2021": f"{DATA_PATH}/br_geodata/data_standardization/zhan.csv",
        "wm2022": f"{DATA_PATH}/br_geodata/data_standardization/wm.csv",
        "anp2024": f"{DATA_PATH}/br_geodata/data_standardization/anp.csv",
        "gogi2023": f"{DATA_PATH}/br_geodata/data_standardization/gogi.csv",
    }

    # Load data
    merge_rules = load_merge_rules(merge_rules_path)
    pyxis_match_table = load_data(pyxis_match_path)
    source_info_tables = {id: load_data(path) for id, path in source_info_paths.items()}

    # Merge the data
    merged_info_table = merge_data(pyxis_match_table, source_info_tables, merge_rules)

    # Save the merged table
    merged_info_table.to_csv(
        f"{DATA_PATH}/br_geodata/merged_pyxis_field_info_table_filtered_withwm.csv",
        index=False,
    )


def main_wowm():
    # File paths
    merge_rules_path = f"{DATA_PATH}/OPGEE_cols_merge_rules.json"
    pyxis_match_path = f"{DATA_PATH}/br_geodata/pyxis_match_table_filtered_wowm.csv"
    source_info_paths = {
        "zhan2021": f"{DATA_PATH}/br_geodata/data_standardization/zhan.csv",
        "anp2024": f"{DATA_PATH}/br_geodata/data_standardization/anp.csv",
        "gogi2023": f"{DATA_PATH}/br_geodata/data_standardization/gogi.csv",
    }

    # Load data
    merge_rules = load_merge_rules(merge_rules_path)
    pyxis_match_table = load_data(pyxis_match_path)
    source_info_tables = {id: load_data(path) for id, path in source_info_paths.items()}

    # Merge the data
    merged_info_table = merge_data(pyxis_match_table, source_info_tables, merge_rules)

    # Save the merged table
    merged_info_table.to_csv(
        f"{DATA_PATH}/br_geodata/merged_pyxis_field_info_table_filtered_wowm.csv",
        index=False,
    )


def main_iter():
    # File paths
    merge_rules_path = f"{DATA_PATH}/OPGEE_cols_merge_rules.json"

    # Paths for Pyxis match tables for all five versions
    version_paths = {
        "v1": f"{DATA_PATH}/br_geodata/pyxis_middle_version/pyxis_match_table_v1.csv",
        "v2": f"{DATA_PATH}/br_geodata/pyxis_middle_version/pyxis_match_table_v2.csv",
        "v3": f"{DATA_PATH}/br_geodata/pyxis_middle_version/pyxis_match_table_v3.csv",
        "v4": f"{DATA_PATH}/br_geodata/pyxis_middle_version/pyxis_match_table_v4.csv",
        "v5": f"{DATA_PATH}/br_geodata/pyxis_middle_version/pyxis_match_table_v5.csv",
    }

    # Paths for source data
    source_info_paths = {
        "zhan2021": f"{DATA_PATH}/br_geodata/data_standardization/zhan.csv",
        "wm2022": f"{DATA_PATH}/br_geodata/data_standardization/wm.csv",
        "anp2024": f"{DATA_PATH}/br_geodata/data_standardization/anp.csv",
        "gogi2023": f"{DATA_PATH}/br_geodata/data_standardization/gogi.csv",
        "spe-210009-ms": f"{DATA_PATH}/br_geodata/data_standardization/spe-210009-ms.csv",
        "spe-162323-ms": f"{DATA_PATH}/br_geodata/data_standardization/spe-162323-ms.csv",
        "spe-140145-ms": f"{DATA_PATH}/br_geodata/data_standardization/spe-140145-ms.csv",
        "spe-94706-ms": f"{DATA_PATH}/br_geodata/data_standardization/spe-94706-ms.csv",
        "seg-2018-2990024": f"{DATA_PATH}/br_geodata/data_standardization/seg-2018-2990024.csv",
        "seg-2005-2645": f"{DATA_PATH}/br_geodata/data_standardization/seg-2005-2645.csv",
        "otc-31900-ms": f"{DATA_PATH}/br_geodata/data_standardization/otc-31900-ms.csv",
        "otc-30780-ms": f"{DATA_PATH}/br_geodata/data_standardization/otc-30780-ms.csv",
        "otc-22612-ms": f"{DATA_PATH}/br_geodata/data_standardization/otc-22612-ms.csv",
        "otc-21934-ms": f"{DATA_PATH}/br_geodata/data_standardization/otc-21934-ms.csv",
        "otc-8879-ms": f"{DATA_PATH}/br_geodata/data_standardization/otc-8879-ms.csv",
        "arma-10-162": f"{DATA_PATH}/br_geodata/data_standardization/arma-10-162.csv",
    }

    # Load merge rules and source data
    merge_rules = load_merge_rules(merge_rules_path)
    source_info_tables = {id: load_data(path) for id, path in source_info_paths.items()}

    # Iterate through all versions of Pyxis match tables and create merged tables
    for version, pyxis_match_path in version_paths.items():
        # Load Pyxis match table for the version
        pyxis_match_table = load_data(pyxis_match_path)

        # Merge the data using the merge rules
        merged_info_table = merge_data(
            pyxis_match_table, source_info_tables, merge_rules
        )

        # Save the merged table for the version
        output_path = f"{DATA_PATH}/br_geodata/pyxis_middle_version/merged_pyxis_field_info_table_{version}.csv"
        merged_info_table.to_csv(output_path, index=False)
        print(f"Saved merged Pyxis field info table for {version} at {output_path}")


if __name__ == "__main__":
    main()
