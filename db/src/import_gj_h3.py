import psycopg2
import geopandas as gpd
import json
import h3pandas
from path_util import DATA_PATH

# PostgreSQL connection parameters
db_params = {
    "host": "localhost",
    "database": "postgres",
    "user": "yaqifan",
    "password": "6221"
}


def insert_h3_index_for_geoj(table_name, geojson_path, h3_resolution, 
                             colname_field_id="field_id", colname_h3_index="h3_index"):
    # Read GeoJSON file
    geojson_data = gpd.read_file(geojson_path)


    # Connect to PostgreSQL
    conn = psycopg2.connect(**db_params)
    cursor = conn.cursor()

    # Convert geometry to h3 index
    h3_polyfill_data = geojson_data.h3.polyfill_resample(h3_resolution)

    for index, row in h3_polyfill_data.iterrows():
        field_id = row['index'] + 1
        h3_index = row.name
        h3_geometry = row['geometry']

        # Insert data into the specified table using a parameterized query
        insert_query = """
        INSERT INTO {} ({}, {}, geometry)
        VALUES (%s, %s, ST_GeomFromText(%s, 4326));
        """.format(table_name, colname_field_id, colname_h3_index)
        cursor.execute(insert_query, (field_id, h3_index, h3_geometry.wkt))

    conn.commit()
    cursor.close()
    conn.close()
    print("H3 polyfill data inserted into {} table successfully!".format(table_name))

if __name__ == "__main__":

    # Path to the GeoJSON file
    geojson_path = f'{DATA_PATH}/tm_geodata/TM.json'

    table_name = "tm_zhan_h3index"
    
    h3_resolution = 9

    insert_h3_index_for_geoj(table_name, geojson_path, h3_resolution)

