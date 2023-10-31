import geopandas as gpd
import pandas as pd
from pathlib2 import Path
import os
from shapely.geometry import Point

from utils.path_util import DATA_PATH


def combine_shapefiles_to_geojson(input_folder, output_geojson,target_crs = 'EPSG:4326'):
    # List all shapefiles in the input folder
    shapefiles = [os.path.join(input_folder, f) for f in os.listdir(input_folder) if f.endswith('.shp')]
    
    if not shapefiles:
        print("No shapefiles found in the specified folder.")
        return

    # Read each shapefile into a GeoDataFrame and concatenate them
    gdf_list = []
    for shapefile in shapefiles:
        gdf = gpd.read_file(str(shapefile))
        gdf.crs = target_crs
        gdf_list.append(gdf)
    combined_gdf = gpd.GeoDataFrame(pd.concat(gdf_list, ignore_index=True))


    # Write the combined GeoDataFrame to a GeoJSON file
    combined_gdf.to_file(output_geojson, driver='GeoJSON')

    print(f"Combined shapefiles successfully written to {output_geojson}")

def point_csv_to_geojson(columns_to_read, csv_file_path, output_geojson_path):

    # Read the CSV file into a pandas DataFrame
    
    well_data_df = pd.read_csv(csv_file_path, usecols=columns_to_read)

    # Create Point geometries based on latitude and longitude
    geometry = [Point(xy) for xy in zip(well_data_df['well_centroid_x'], well_data_df['well_centroid_y'])]

    # Create a GeoDataFrame
    gdf = gpd.GeoDataFrame(well_data_df, geometry=geometry, crs="EPSG:4326")

    # Export as GeoJSON
    gdf.to_file(output_geojson_path, driver='GeoJSON')

    print("GeoDataFrame exported as GeoJSON:", output_geojson_path)

if __name__ == "__main__":

  input_folder = f'{DATA_PATH}/zhan_field/fields'
  output_geojson = f'{DATA_PATH}/zhan_field/zhan_global_field_shape.json'
  target_crs = 'EPSG:4326'
  combine_shapefiles_to_geojson(input_folder, output_geojson)

# Specify the columns you want to read from the CSV file
    # columns_to_read = ['id_well', 'well_name', 'country_name', 'id_field_associated','well_associated_field',
    #                 'well_centroid_x', 'well_centroid_y']
    # csv_file_path = f'{DATA_PATH}/wm_well/WM_LENS_upstream_weekly-well_summary_10122022_SEED.csv'
    # output_geojson_path = f'{DATA_PATH}/wm_well/wm_global_well.json'
    # point_csv_to_geojson(columns_to_read,csv_file_path,output_geojson_path)
