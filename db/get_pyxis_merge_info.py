import pandas as pd
import numpy as np
from utils.path_util import DATA_PATH
import json
import geopandas as gpd
from shapely import wkt
from shapely.ops import unary_union
import h3
import datetime

with open(f'{DATA_PATH}/OPGEE_cols.json', 'r') as json_file:
    OPGEE_cols = json.load(json_file)

def load_merge_rules(json_path):
    """ Load merge rules from a JSON file """
    with open(json_path, 'r') as file:
        return json.load(file)

def apply_merge_rule(data, rule):
    """ Apply a merge rule to a list of data """
    if not data:  # Early exit if data list is empty
        return None
    if rule == 'average':
        return np.average(data)
    elif rule == 'average int':
        return int(np.median(data))
    elif rule == 'median':
        return np.median(data)
    elif rule == 'median int':
        return int(np.median(data))
    elif rule == 'most frequent':
        return max(set(data), key=data.count)
    elif rule == 'avg_age':
        return int(datetime.datetime.now().year-np.average(data))
    return data  # Return as is if no rule matches

def load_data(file_path):
    """ Load data from an Excel file """
    return pd.read_csv(file_path)

def dissolve_geometries(geometries):
    """Dissolve geometries into a single geometry, ensuring all are valid WKT before processing."""
    valid_geometries = []
    for geom in geometries:
        try:
            # Ensure the geometry is valid and not None or empty
            if geom and geom != 'None' and geom.strip():
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
    
    for pyxis_id, group in pyxis_match_table.groupby('Pyxis ID'):
        opgee_data = {col: [] for col in merge_rules}  # Data for merge rules
        detailed_fields = {col: [] for col in merge_rules}  # Detailed in-use fields
        geometries = []  # List to collect geometries for each Pyxis ID

        # Process each row associated with the current Pyxis ID
        for _, row in group.iterrows():
            source_info = source_info_tables.get(row['Source ID'])
            if source_info is not None and row['Field ID'] in source_info['Field ID'].values:
                source_row = source_info[source_info['Field ID'] == row['Field ID']].iloc[0]
                
                for col in merge_rules:
                    if pd.notna(source_row[col]):  # Ensure the data is not null
                        opgee_data[col].append(source_row[col])
                        detailed_fields[col].append((source_row['Source Name'], row['Field ID']))
                
                # Collect geometry for each valid source entry
                if source_row['geometry'] is not None:
                    geometries.append(source_row['geometry'])

        # Dissolve geometries
        merged_geometry,centroid_h3_index = dissolve_geometries(geometries)

        # Apply merge rules for each OPGEE column
        merged_values = {col: apply_merge_rule(opgee_data[col], merge_rules[col]) for col in merge_rules}

        # Prepare the detailed in-use field information
        detailed_in_use = {col: values for col, values in detailed_fields.items()}

        # Construct the merged record
        merged_record = {
            'Pyxis ID': pyxis_id,
            'Name': group.sort_values(by='Match Score', ascending=False).iloc[0]['Name'],
            'Centroid H3 Index': centroid_h3_index,
            'Source ID used': ", ".join(set(group['Source ID'])),
            **merged_values,
            'geometry': merged_geometry,
            'Detailed in use field': detailed_in_use
        }
        detailed_merge.append(merged_record)
    
    return pd.DataFrame(detailed_merge)


def main():
    # File paths
    merge_rules_path = f'{DATA_PATH}/OPGEE_cols_merge_rules.json'
    pyxis_match_path = f'{DATA_PATH}/br_geodata/pyxis_match_table.csv'
    source_info_paths = {
        'zhan2021':f'{DATA_PATH}/br_geodata/data_standardization/zhan.csv',
        'wm2022':f'{DATA_PATH}/br_geodata/data_standardization/wm.csv',
        'anp2024':f'{DATA_PATH}/br_geodata/data_standardization/anp.csv',
        'gogi2023':f'{DATA_PATH}/br_geodata/data_standardization/gogi.csv'
    }

    # Load data
    merge_rules = load_merge_rules(merge_rules_path)
    pyxis_match_table = load_data(pyxis_match_path)
    source_info_tables = {id: load_data(path) for id, path in source_info_paths.items()}

    # Merge the data
    merged_info_table = merge_data(pyxis_match_table, source_info_tables, merge_rules)

    # Save the merged table
    merged_info_table.to_csv(f'{DATA_PATH}/br_geodata/merged_pyxis_field_info_table.csv', index=False)

if __name__ == '__main__':
    main()
