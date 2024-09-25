from utils.path_util import DATA_PATH
import pandas as pd
import geopandas as gpd
from shapely import wkt
from shapely.geometry import Point
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as colors
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
    
    # Calculate match rate based on unique flare IDs and flare volume (BCM_2021)
    unique_matched_ids = matches_initial[matches_initial['matched']]['id'].unique()
    initial_match_volume = flare_gdf[flare_gdf['id'].isin(unique_matched_ids)]['BCM_2021'].sum()
    total_flare_volume = flare_gdf['BCM_2021'].sum()

    # Step 2: Handle overlapping fields if a flare matches multiple fields
    matches_within_fields = matches_initial[matches_initial['matched']]
    if not matches_within_fields.empty:
        overlaps = matches_within_fields.groupby(matches_within_fields.index).filter(lambda x: len(x) > 1)
        if not overlaps.empty:
            overlaps['weighted_volume'] = overlaps['BCM_2021'] * (overlaps['Oil production volume'] / overlaps['Oil production volume'].sum())

    # Step 3: Extend field boundaries by 5 km to match more flares
    buffered_fields = field_gdf.copy()
    buffered_fields['geometry'] = buffered_fields.geometry.buffer(0.05)  # 5 km buffer in degrees
    extended_matches = gpd.sjoin(flare_gdf[~flare_gdf['id'].isin(unique_matched_ids)], buffered_fields, how='left', predicate='within')
    extended_matches['extended_matched'] = ~extended_matches.index_right.isna()

    # Calculate extended match rate based on unique flare IDs and flare volume (BCM_2021)
    extended_unique_ids = extended_matches[extended_matches['extended_matched']]['id'].unique()
    extended_match_volume = flare_gdf[flare_gdf['id'].isin(extended_unique_ids)]['BCM_2021'].sum()

    # Combine the results from initial matches and extended matches without double-counting flares
    total_matched_volume = initial_match_volume + extended_match_volume
    initial_match_rate = initial_match_volume/total_matched_volume
    final_match_rate = total_matched_volume / total_flare_volume
    unmatched_flare_volume = 1 - final_match_rate

    # Calculate flaring-to-oil ratio and overwrite the existing column
    all_matches = pd.concat([matches_initial, extended_matches], axis=0)
    all_matches = all_matches.drop_duplicates(subset=['id'])  # Ensure no double-counting
    all_matches = all_matches[~all_matches['index_right'].isna()]  # Filter out NaN values
    all_matches['Flaring-to-oil ratio'] = all_matches['BCM_2021']*BCM2scf / (all_matches['Oil production volume']*365)

    # Update the existing Flaring-to-oil ratio column in the field data
    field_gdf.loc[all_matches['index_right'].astype(int), 'Flaring-to-oil ratio'] = all_matches['Flaring-to-oil ratio'].values
    
    return field_gdf, initial_match_rate, final_match_rate, unmatched_flare_volume


# Load data
flare_gdf = load_flare_data(f'{DATA_PATH}/br_geodata/flare_2021/flare_2021_month.csv', 'Brazil', 2021)
field_gdf = load_field_data(f'{DATA_PATH}/br_geodata/merged_pyxis_field_info_table_filtered.csv')


# Perform the matching
final_merged_data, initial_match_rate, final_match_rate, unmatched_flare_volume = match_flares_to_fields(flare_gdf, field_gdf)

final_merged_data.drop(columns=['Centroid H3 Index','Source ID used','geometry','Detailed in use field']).to_csv(f'{DATA_PATH}/br_geodata/merged_pyxis_field_info_with_flare.csv')

# Display the matching rates
print(f"Initial Match Rate (based on volume): {initial_match_rate:.2%}")
print(f"Final Match Rate (based on volume): {final_match_rate:.2%}")
print(f"Unmatched Flare Volume: {unmatched_flare_volume:.2%}")
