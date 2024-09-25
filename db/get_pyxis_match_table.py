import pandas as pd
from fuzzywuzzy import fuzz
from utils.path_util import DATA_PATH
import h3
import numpy as np
from pathlib import Path


def load_source_data(file_path):
    """ Load data from an Excel file """
    return pd.read_csv(file_path)

def load_metadata(metadata_path):
    """ Load metadata from an Excel file """
    return pd.read_csv(metadata_path)

def sort_sources_by_score(metadata):
    """ Sort sources by 'Data Score' """
    return metadata.sort_values(by='Data Score', ascending=False)

def initialize_pyxis_match_table(source):
    """ Initialize the Pyxis Match Table from the highest score source """
    filtered_source = source[source['Name'].notna()]
    pyxis_match_table = filtered_source[['Name', 'Centroid H3 Index', 'Source ID','Source Name','Field ID']].copy()
    pyxis_match_table.insert(0, 'Pyxis ID', range(0, len(pyxis_match_table)))
    pyxis_match_table['Match Score'] = 100  # Initial match score
    return pyxis_match_table

def calculate_match_score(name1, name2, index1, index2, weight = [0.7, 0.3]):
    """ Calculate match score based on name similarity and H3 distance (must in the same resolution) """
    if name1 is not None and name2 is not None:
        name_score = fuzz.ratio(name1, name2)
    else:
        name_score = 0
    if index1 is not None and index2 is not None:
        try:
            grid_distance = h3.h3_distance(index1, index2)
            if grid_distance < 50:
            # Normalize distance to a score
                geo_score = 100 * np.exp(-0.5 * np.power(grid_distance*0.1,2))  # gaussian distribution
            else:
                geo_score = -40
        except ValueError:
            geo_score = -40 # Handle cases where distance cannot be computed (too far away)
    else:
        geo_score = 0
    return weight[0] * name_score + weight[1] * geo_score

def match_sources(pyxis_match_table, new_source, score_threshold = 60):
    """ Match new source fields with existing entries in the Pyxis Match Table """
    new_pyxis_id = pyxis_match_table['Pyxis ID'].max() + 1  # Start new IDs from the max existing ID + 1
    entries_to_add = []
    for _, row in new_source.iterrows():
        if pd.isna(row['Name']):  # Skip rows with None as the Name
            continue
        best_score = 0
        best_match_id = None
        for _, match_row in pyxis_match_table.iterrows():
            score = calculate_match_score(row['Name'], match_row['Name'], row['Centroid H3 Index'], match_row['Centroid H3 Index'])
            if score > best_score:
                best_score = score
                best_match_id = match_row['Pyxis ID']
        
        match_entry = {
            'Pyxis ID': best_match_id if best_score >= score_threshold else new_pyxis_id,
            'Name': row['Name'],
            'Centroid H3 Index': row['Centroid H3 Index'],
            'Source ID': row['Source ID'],
            'Source Name': row['Source Name'],
            'Field ID': row['Field ID'],
            'Match Score': best_score if best_score >= score_threshold else 100
        }
        entries_to_add.append(pd.DataFrame([match_entry]))
        if best_score < score_threshold:  # Only increment if no match was found
            new_pyxis_id += 1

    pyxis_match_table = pd.concat([pyxis_match_table] + entries_to_add, ignore_index=True)

    return pyxis_match_table

def filter_pyxis_match(df, government_source_id, other_sources):
    """ Filter the Pyxis Match Table according to specific criteria """
    # Calculate the required number of sources dynamically
    total_sources = [government_source_id] + other_sources
    required_count = len(total_sources) // 2 + 1
    
    # Identify Pyxis IDs that contain the government source ID
    pyxis_with_gov = df[df['Source ID'] == government_source_id]['Pyxis ID'].unique()
    
    # Identify Pyxis IDs that contain at least the required number of other sources
    source_counts = df[df['Source ID'].isin(other_sources)].groupby('Pyxis ID').size()
    pyxis_with_required_sources = source_counts[source_counts >= required_count].index
    
    # Combine both conditions
    pyxis_ids_to_keep = set(pyxis_with_gov).union(set(pyxis_with_required_sources))
    
    # Filter the DataFrame to keep rows for the identified Pyxis IDs
    filtered_df = df[df['Pyxis ID'].isin(pyxis_ids_to_keep)]
    
    # Reorganize IDs sequentially, keeping the same ID for identical Pyxis IDs
    id_map = {old_id: new_id for new_id, old_id in enumerate(sorted(filtered_df['Pyxis ID'].unique()))}
    filtered_df['Pyxis ID'] = filtered_df['Pyxis ID'].map(id_map)
    
    return filtered_df


def main():
    # Paths to the source data and metadata
    metadata_path = f'{DATA_PATH}/br_geodata/data_standardization/source_metadata.csv'
    data_files = [f'{DATA_PATH}/br_geodata/data_standardization/zhan.csv',
                  f'{DATA_PATH}/br_geodata/data_standardization/wm.csv',
                  f'{DATA_PATH}/br_geodata/data_standardization/anp.csv',
                  f'{DATA_PATH}/br_geodata/data_standardization/gogi.csv']
    
    # Load metadata and source data
    metadata = load_metadata(metadata_path)
    sources = [load_source_data(Path(data_file)) for data_file in data_files]
    
    # Sort sources by their data scores in the metadata
    sorted_metadata = sort_sources_by_score(metadata)
    sorted_sources = [next(src for src in sources if src['Source ID'].iloc[0] == id) for id in sorted_metadata['Source ID']]
    
    # Initialize the Pyxis Match Table
    pyxis_match_table = initialize_pyxis_match_table(sorted_sources[0])
    
    # Iteratively match each source to the Pyxis Match Table
    for source in sorted_sources[1:]:
        pyxis_match_table = match_sources(pyxis_match_table, source)
    
    # Filter and reorganize the Pyxis Match Table
    filtered_df = filter_pyxis_match(pyxis_match_table, 'anp2024', ['wm2022','anp2024','gogi2023'])

    # Save the Pyxis Match Table
    filtered_df.to_csv(f'{DATA_PATH}/br_geodata/pyxis_match_table_filtered.csv', index=False)

if __name__ == '__main__':
    main()
