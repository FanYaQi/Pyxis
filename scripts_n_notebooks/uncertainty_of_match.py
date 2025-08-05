import pandas as pd
from fuzzywuzzy import fuzz
from utils.path_util import DATA_PATH
import h3
import numpy as np
from pathlib import Path
import time

def load_source_data(file_path):
    """Load data from a CSV file"""
    return pd.read_csv(file_path)

def load_metadata(metadata_path):
    """Load metadata from a CSV file"""
    return pd.read_csv(metadata_path)

def sort_sources_by_score(metadata, sources_data):
    """Sort sources by 'Data Score'"""
    sorted_meta = metadata.sort_values(by="Data Score", ascending=False)
    sorted_sources_list = [
        next(src for src in sources_data if src["Source ID"].iloc[0] == source_id)
        for source_id in sorted_meta["Source ID"]
    ]
    return sorted_sources_list

def initialize_pyxis_match_table(source):
    """Initialize the Pyxis Match Table from the highest score source"""
    filtered_source = source[source["Name"].notna()]
    pyxis_match_table = filtered_source[
        ["Name", "Centroid H3 Index", "Source ID", "Source Name", "Field ID"]
    ].copy()
    pyxis_match_table.insert(0, "Pyxis ID", range(len(pyxis_match_table)))
    pyxis_match_table["Match Score"] = 100
    return pyxis_match_table

def calculate_match_score(name1, name2, index1, index2, weights):
    """Calculate match score based on name similarity and H3 distance"""
    if name1 is not None and name2 is not None:
        name_score = fuzz.ratio(str(name1), str(name2))
    else:
        name_score = 0
    
    if index1 is not None and index2 is not None:
        try:
            # Check for valid H3 indexes before calculating distance
            if h3.h3_is_valid(index1) and h3.h3_is_valid(index2):
                grid_distance = h3.h3_distance(index1, index2)
                if grid_distance < 50:
                    geo_score = 100 * np.exp(-0.5 * np.power(grid_distance * 0.1, 2))
                else:
                    geo_score = -40
            else:
                geo_score = -40
        except (ValueError, TypeError):
            geo_score = -40
    else:
        geo_score = 0
        
    return weights[0] * name_score + weights[1] * geo_score

def match_sources(pyxis_match_table, new_source, score_threshold, weights):
    """Match new source fields with existing entries in the Pyxis Match Table"""
    new_pyxis_id = pyxis_match_table["Pyxis ID"].max() + 1
    entries_to_add = []
    
    # Pre-filter the new source for rows with non-NA names
    new_source_filtered = new_source[new_source["Name"].notna()].copy()

    for _, row in new_source_filtered.iterrows():
        best_score = -1
        best_match_id = None
        
        # Vectorized calculation could be complex here due to the nature of fuzzy matching
        # Keeping the iterative approach for clarity and correctness
        for _, match_row in pyxis_match_table.iterrows():
            score = calculate_match_score(
                row["Name"],
                match_row["Name"],
                row["Centroid H3 Index"],
                match_row["Centroid H3 Index"],
                weights=weights,
            )
            if score > best_score:
                best_score = score
                best_match_id = match_row["Pyxis ID"]

        match_entry = {
            "Pyxis ID": best_match_id if best_score >= score_threshold else new_pyxis_id,
            "Name": row["Name"],
            "Centroid H3 Index": row["Centroid H3 Index"],
            "Source ID": row["Source ID"],
            "Source Name": row["Source Name"],
            "Field ID": row["Field ID"],
            "Match Score": best_score if best_score >= score_threshold else 100,
        }
        entries_to_add.append(match_entry)
        if best_score < score_threshold:
            new_pyxis_id += 1

    if entries_to_add:
        pyxis_match_table = pd.concat([pyxis_match_table, pd.DataFrame(entries_to_add)], ignore_index=True)

    return pyxis_match_table

def filter_pyxis_match(df, government_source_id, other_sources):
    """Filter the Pyxis Match Table according to specific criteria"""
    total_sources_count = 1 + len(other_sources)
    required_count = total_sources_count // 2 + 1

    pyxis_with_gov = df[df["Source ID"] == government_source_id]["Pyxis ID"].unique()
    
    # Count unique sources per Pyxis ID
    source_counts = df.groupby('Pyxis ID')['Source ID'].nunique()
    pyxis_with_required_sources = source_counts[source_counts >= required_count].index

    pyxis_ids_to_keep = set(pyxis_with_gov).union(set(pyxis_with_required_sources))

    filtered_df = df[df["Pyxis ID"].isin(pyxis_ids_to_keep)]
    return filtered_df

def run_simulation(sorted_sources, score_threshold, weights, gov_source_id, other_source_ids):
    """
    Runs a single full matching and filtering process and returns the final field count.
    """
    # 1. Initialize the Pyxis Match Table
    pyxis_match_table = initialize_pyxis_match_table(sorted_sources[0])

    # 2. Iteratively match each source
    for source in sorted_sources[1:]:
        pyxis_match_table = match_sources(
            pyxis_match_table, source, score_threshold=score_threshold, weights=weights
        )
    
    # 3. Filter the results
    filtered_df = filter_pyxis_match(
        pyxis_match_table, gov_source_id, other_source_ids
    )

    # 4. Return the count of unique fields
    final_field_count = filtered_df["Pyxis ID"].nunique()
    return final_field_count


def main():
    """
    Main driver for the sensitivity analysis.
    """
    print("Starting sensitivity analysis for field matching...")
    start_time = time.time()
    
    # --- 1. SETUP: Define parameters and load data ONCE ---
    metadata_path = f"{DATA_PATH}/br_geodata/data_standardization/source_metadata.csv"
    data_files = [
        f"{DATA_PATH}/br_geodata/data_standardization/zhan.csv",
        f"{DATA_PATH}/br_geodata/data_standardization/wm.csv",
        f"{DATA_PATH}/br_geodata/data_standardization/anp.csv",
        f"{DATA_PATH}/br_geodata/data_standardization/gogi.csv",
    ]
    GOV_SOURCE_ID = "anp2024"
    OTHER_SOURCE_IDS = ["wm2022", "zhan2021", "gogi2023"]

    # Define the parameter grid
    match_thresholds = [60, 65, 70, 75, 80, 85, 90]
    name_weights = [0.3, 0.4, 0.5, 0.6, 0.7]
    
    # Load and sort data
    metadata = load_metadata(metadata_path)
    sources_data = [load_source_data(Path(file)) for file in data_files]
    sorted_sources = sort_sources_by_score(metadata, sources_data)

    field_counts = []
    run_counter = 0
    total_runs = len(match_thresholds) * len(name_weights)

    # --- 2. EXECUTION: Loop through all parameter combinations ---
    print(f"\nRunning {total_runs} simulations...")
    for threshold in match_thresholds:
        for name_w in name_weights:
            run_counter += 1
            geo_w = 1.0 - name_w
            current_weights = [name_w, geo_w]
            
            print(f"[{run_counter}/{total_runs}] Running with Threshold={threshold}, Weights=[{name_w:.1f}, {geo_w:.1f}]...", end="")
            
            count = run_simulation(
                sorted_sources, 
                score_threshold=threshold, 
                weights=current_weights,
                gov_source_id=GOV_SOURCE_ID,
                other_source_ids=OTHER_SOURCE_IDS
            )
            
            field_counts.append(count)
            print(f" -> Result: {count} fields")

    # --- 3. ANALYSIS: Calculate and display final statistics ---
    counts_array = np.array(field_counts)
    mean_count = np.mean(counts_array)
    std_dev = np.std(counts_array)
    
    # Avoid division by zero if mean is 0
    if mean_count > 0:
        cv = (std_dev / mean_count) * 100  # Expressed as a percentage
    else:
        cv = 0

    end_time = time.time()
    total_time = end_time - start_time

    print("\n--- Uncertainty Analysis Summary ---")
    print(f"Total simulations performed: {len(field_counts)}")
    print(f"Range of final field counts: {np.min(counts_array)} to {np.max(counts_array)}")
    print(f"Mean field count: {mean_count:.2f}")
    print(f"Standard Deviation: {std_dev:.2f}")
    print(f"Coefficient of Variation (CV): {cv:.2f}%")
    print(f"\nTotal analysis time: {total_time:.2f} seconds")


if __name__ == "__main__":
    main()