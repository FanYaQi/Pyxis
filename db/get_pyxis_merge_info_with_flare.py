from utils.path_util import DATA_PATH
import pandas as pd
import geopandas as gpd
from shapely import wkt
from shapely.geometry import Point
import numpy as np


BCM2scf = 35314666572.222

# Load flare data
def load_flare_data(filepath, country, year):
    flare_month = pd.read_csv(filepath)
    # Filter flare data by country and year, then aggregate by ID and coordinates
    flare_filtered = flare_month[(flare_month['country'] == country) & (flare_month['year'] == year)]
    flare_aggregated = flare_filtered.groupby(['id'], as_index=False).agg({
        'lat': 'first',
        'lon': 'first',
        't_mean': 'mean',
        'BCM': 'sum'
    }).rename(columns={
        'lat': 'Latitude',
        'lon': 'Longitude',
        't_mean': 'Avg_temp_K',
        'BCM': 'BCM_2021'
    })
    # Convert to GeoDataFrame
    flare_aggregated['geometry'] = flare_aggregated.apply(lambda row: Point(row['Longitude'], row['Latitude']), axis=1)
    flare_gdf = gpd.GeoDataFrame(flare_aggregated, geometry='geometry', crs="EPSG:4326")
    return flare_gdf

# Load field data and parse geometry
def load_field_data(filepath):
    field_data = pd.read_csv(filepath)
    field_data['geometry'] = field_data['geometry'].apply(wkt.loads)
    field_gdf = gpd.GeoDataFrame(field_data, geometry='geometry', crs="EPSG:4326")
    return field_gdf

# Match flares to fields and calculate flaring-to-oil ratio
def match_flares_to_fields(flare_gdf, field_gdf):
    # Step 1: Match flares within field boundaries
    matches_initial = gpd.sjoin(flare_gdf, field_gdf, how='left', predicate='within')
    matches_initial['matched'] = ~matches_initial.index_right.isna()
    matches_initial['weight'] = 1  # Initialize weight to 1 for each matched flare
    
    # Calculate match rate based on unique flare IDs and flare volume (BCM_2021)
    unique_matched_ids = matches_initial[matches_initial['matched']]['id'].unique()
    initial_match_volume = flare_gdf[flare_gdf['id'].isin(unique_matched_ids)]['BCM_2021'].sum()
    total_flare_volume = flare_gdf['BCM_2021'].sum()
    initial_match_rate = initial_match_volume / total_flare_volume if total_flare_volume != 0 else 0

    # Step 2: Handle overlapping fields if a flare matches multiple fields
    matches_within_fields = matches_initial[matches_initial['matched']]
    if not matches_within_fields.empty:
        overlaps = matches_within_fields.groupby('id').filter(lambda x: len(x) > 1)
        if not overlaps.empty:
            overlaps['weight'] = overlaps['Oil production volume'] / overlaps.groupby('id')['Oil production volume'].transform('sum')
            matches_within_fields = pd.concat([matches_within_fields.drop(overlaps.index), overlaps])

    # Step 3: Extend field boundaries by 5 km to match more flares
    buffered_fields = field_gdf.copy()
    buffered_fields['geometry'] = buffered_fields.geometry.buffer(0.05)  # 5 km buffer in degrees
    extended_matches = gpd.sjoin(flare_gdf[~flare_gdf['id'].isin(unique_matched_ids)], buffered_fields, how='left', predicate='within')
    extended_matches['extended_matched'] = ~extended_matches.index_right.isna()
    extended_matches['weight'] = 1  # Initialize weight to 1 for each extended matched flare

    # Step 4: Assign extended flare volumes, considering overlaps
    if not extended_matches.empty:
        extended_overlaps = extended_matches.groupby('id').filter(lambda x: len(x) > 1)
        if not extended_overlaps.empty:
            extended_overlaps['weight'] = extended_overlaps['Oil production volume'] / extended_overlaps.groupby('id')['Oil production volume'].transform('sum')
            extended_matches = pd.concat([extended_matches.drop(extended_overlaps.index), extended_overlaps])

    # Combine the results from initial matches and extended matches without double-counting
    all_matches = pd.concat([matches_within_fields, extended_matches], axis=0)
    all_matches = all_matches[~all_matches['index_right'].isna()]  # Filter out NaN values
    all_matches['Oil production volume'] = all_matches['Oil production volume'].apply(lambda x: x if pd.notna(x) and x > 0 else 1)  # Assign a small value of 1 bbl/d if None or zero

    # Calculate the flare contribution to each field based on weight
    all_matches['weighted_volume'] = all_matches['BCM_2021'] * all_matches['weight']

    # Handle cases where weight may be zero due to unmatched flares
    unmatched_flares = all_matches[all_matches['weight'] == 0]
    if not unmatched_flares.empty:
        all_matches.loc[unmatched_flares.index, 'weight'] = 1  # Assign weight of 1 for unmatched flares to retain original volume

    # Check if the weight of all flare IDs adds up to 1 where applicable
    weight_sums = all_matches.groupby('id')['weight'].sum().reset_index()
    weight_sums.rename(columns={'weight': 'weight_sum'}, inplace=True)
    all_matches = all_matches.merge(weight_sums, on='id', how='left')
    all_matches['weight'] = all_matches.apply(lambda row: row['weight'] / row['weight_sum'] if row['weight_sum'] > 0 else row['weight'], axis=1)
    all_matches.drop(columns=['weight_sum'], inplace=True)

    # Group by field and calculate total flare volume considering weighted volumes
    combined_matches = all_matches.groupby('index_right').agg({
        'weighted_volume': 'sum',
        'Oil production volume': 'first'
    }).reset_index()
    combined_matches['Flaring-to-oil ratio'] = combined_matches['weighted_volume'] * BCM2scf / (combined_matches['Oil production volume'] * 365)

    # Update the existing Flaring-to-oil ratio column in the field data
    field_gdf['Flaring-to-oil ratio'] = field_gdf.apply(lambda row: combined_matches[combined_matches['index_right'] == row.name]['Flaring-to-oil ratio'].sum() if row.name in combined_matches['index_right'].values else row['Flaring-to-oil ratio'], axis=1)

    # Calculate final match rate and unmatched flare volume
    final_match_volume = all_matches['weighted_volume'].sum()
    final_match_rate = final_match_volume / total_flare_volume if total_flare_volume != 0 else 0
    unmatched_flare_volume = 1 - final_match_rate
    
    return field_gdf, initial_match_rate, final_match_rate, unmatched_flare_volume

def main():
    # Load data
    flare_gdf = load_flare_data(f'{DATA_PATH}/br_geodata/flare_2021/flare_2021_month.csv', 'Brazil', 2021)
    field_gdf = load_field_data(f'{DATA_PATH}/br_geodata/merged_pyxis_field_info_table_filtered_withwm.csv')

    # Perform the matching
    final_merged_data, initial_match_rate, final_match_rate, unmatched_flare_volume = match_flares_to_fields(flare_gdf, field_gdf)

    final_merged_data.drop(columns=['Centroid H3 Index', 'Source ID used', 'geometry', 'Detailed in use field']).to_csv(f'{DATA_PATH}/br_geodata/merged_pyxis_field_info_with_flare_withwm.csv')

    # Display the matching rates
    print(f"Initial Match Rate (based on volume): {initial_match_rate:.2%}")
    print(f"Final Match Rate (based on volume): {final_match_rate:.2%}")
    print(f"Unmatched Flare Volume: {unmatched_flare_volume:.2%}")

def main_wowm():
    # Load data
    flare_gdf = load_flare_data(f'{DATA_PATH}/br_geodata/flare_2021/flare_2021_month.csv', 'Brazil', 2021)
    field_gdf = load_field_data(f'{DATA_PATH}/br_geodata/merged_pyxis_field_info_table_filtered_wowm.csv')

    # Perform the matching
    final_merged_data, initial_match_rate, final_match_rate, unmatched_flare_volume = match_flares_to_fields(flare_gdf, field_gdf)

    final_merged_data.drop(columns=['Centroid H3 Index', 'Source ID used', 'geometry', 'Detailed in use field']).to_csv(f'{DATA_PATH}/br_geodata/merged_pyxis_field_info_with_flare_wowm.csv')

    # Display the matching rates
    print(f"Initial Match Rate (based on volume): {initial_match_rate:.2%}")
    print(f"Final Match Rate (based on volume): {final_match_rate:.2%}")
    print(f"Unmatched Flare Volume: {unmatched_flare_volume:.2%}")

if __name__ == '__main__':
    main()