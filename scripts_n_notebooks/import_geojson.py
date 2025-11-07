import psycopg2
import json

from utils.path_util import DATA_PATH


def import_geojson(db_params, table_name, geojson_path):
    # Read GeoJSON file
    with open(geojson_path) as f:
        geojson_data = json.load(f)

    # Identify columns from the attributes of the first feature
    first_feature = geojson_data["features"][0]
    # Define the column names
    geometry_column = "geometry"
    attributes_columns = list(first_feature["properties"].keys())

    # Connect to PostgreSQL
    conn = psycopg2.connect(**db_params)
    cursor = conn.cursor()

    # Loop through GeoJSON features and insert into the table
    for feature in geojson_data["features"]:
        geometry = json.dumps(feature["geometry"])
        attributes_values = [
            feature["properties"].get(column) for column in attributes_columns
        ]
        placeholders = ", ".join(["%s" for _ in attributes_columns])
        insert_query = f"INSERT INTO {table_name} ({geometry_column}, {', '.join(attributes_columns)}) VALUES (ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326), {placeholders}) ON CONFLICT DO NOTHING"
        cursor.execute(insert_query, [geometry] + attributes_values)

    conn.commit()
    cursor.close()
    conn.close()
    print("GeoJSON data inserted successfully!")


if __name__ == "__main__":
    # PostgreSQL connection parameters
    db_params = {
        "host": "localhost",
        "database": "postgres",
        "user": "yaqifan",
        "password": "6221",
    }

    # Path to the GeoJSON file
    geojson_path = f"{DATA_PATH}/tm_geodata/TM.json"

    table_name = "zhan_tm_field"

    import_geojson(db_params, table_name, geojson_path)
