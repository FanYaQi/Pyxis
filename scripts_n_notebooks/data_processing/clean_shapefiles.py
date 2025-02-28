import geopandas as gpd
import shapely
import os
from utils.path_util import DATA_PATH


def clean_z_coordinates(input_file, output_file):
    # Read the GeoJSON or shapefile into a GeoDataFrame
    gdf = gpd.read_file(input_file)
    
    # Remove Z coordinates by setting the Z value to NaN for each geometry
    geom = shapely.wkb.loads(shapely.wkb.dumps(gdf.geometry, output_dimension=2))
    gdf.geometry = geom
    # Save the cleaned GeoDataFrame
    gdf.to_file(output_file)
    print('cleaned successfully')

def remove_empty_geometries(input_shapefile, output_shapefile):
    # Read the input shapefile
    gdf = gpd.read_file(input_shapefile)
    
    # Filter rows with non-empty geometries
    gdf = gdf[~gdf['geometry'].isna()]
    
    # Save the filtered GeoDataFrame to the output shapefile
    gdf.to_file(output_shapefile)
    print('remove empty for'+str(input_shapefile))

if __name__ == "__main__":
    # clean India shape file
    # input_shapefile = f'{DATA_PATH}/zhan_field/fields/PK.shp'
    # clean_z_coordinates(input_shapefile, input_shapefile)

    #clean the entire folder
    input_folder = f'{DATA_PATH}/zhan_field/fields'
    shapefiles = [os.path.join(input_folder, f) for f in os.listdir(input_folder) if f.endswith('.shp')]

    for shapefile in shapefiles:
        gdf = gpd.read_file(str(shapefile))
        remove_empty_geometries(str(shapefile),str(shapefile))
        if gdf.has_z.any() == True:
            print(str(shapefile))
            clean_z_coordinates(str(shapefile),str(shapefile))

