import geopandas as gpd
from shapely.geometry import Point
import pandas as pd
# from path_util import DATA_PATH

# Specify the columns you want to read from the CSV file
columns_to_read = ['id_well', 'well_name', 'country_name', 'id_field_associated','well_associated_field',
                   'well_centroid_x', 'well_centroid_y']

# Read the CSV file into a pandas DataFrame
csv_file_path = 'db/data/tm_geodata/TM_well.csv'
well_data_df = pd.read_csv(csv_file_path, usecols=columns_to_read)

# Create Point geometries based on latitude and longitude
geometry = [Point(xy) for xy in zip(well_data_df['well_centroid_x'], well_data_df['well_centroid_y'])]

# Create a GeoDataFrame
gdf = gpd.GeoDataFrame(well_data_df, geometry=geometry, crs="EPSG:4326")

# Export as GeoJSON
output_geojson_path = 'db/data/tm_geodata/TM_well.json'
gdf.to_file(output_geojson_path, driver='GeoJSON')

print("GeoDataFrame exported as GeoJSON:", output_geojson_path)