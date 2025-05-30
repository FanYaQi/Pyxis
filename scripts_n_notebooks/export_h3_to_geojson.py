import psycopg2
import h3
import json
from shapely.geometry import shape
from utils.path_util import DATA_PATH


def h3_cells_to_geojson(
    db_params, h3_column, table_name, output_file, additional_columns=None
):
    try:
        # Establish a database connection
        conn = psycopg2.connect(**db_params)
        cursor = conn.cursor()

        # Create a comma-separated string of additional column names for the SQL query
        additional_columns_str = ", ".join(additional_columns)

        # Execute the SQL query to fetch H3 cell indexes and the additional columns
        sql_query = f"""
        SELECT {h3_column}, {additional_columns_str}
        FROM {table_name};
        """
        cursor.execute(sql_query)

        # Fetch all H3 cell indexes
        rows = cursor.fetchall()

        # Create a list to store GeoJSON features
        features = []

        # Convert H3 cell indexes to GeoJSON shapes
        for row in rows:
            hexagon = h3.h3_to_geo_boundary(row[0], geo_json=True)
            polygon = shape({"type": "Polygon", "coordinates": [hexagon]})
            # Create a feature with geometry and properties
            properties = {}
            for i, column_name in enumerate(additional_columns):
                properties[column_name] = float(row[i + 1])

            feature = {
                "type": "Feature",
                "geometry": polygon.__geo_interface__,
                "properties": properties,
            }

            features.append(feature)

        feature_collection = {"type": "FeatureCollection", "features": features}

        # Convert the FeatureCollection to a GeoJSON string
        geojson_data = json.dumps(feature_collection, indent=2)

        # Save the GeoJSON to the specified output file
        with open(output_file, "w") as geojson_file:
            geojson_file.write(geojson_data)

        print(f"H3 cells converted to GeoJSON and saved as '{output_file}'.")

    except Exception as e:
        print(f"An error occurred: {str(e)}")
    finally:
        # Close the database connection
        if cursor:
            cursor.close()
        if conn:
            conn.close()


if __name__ == "__main__":
    db_params = {
        "host": "localhost",
        "database": "postgres",
        "user": "yaqifan",
        "password": "6221",
    }
    # h3_column = "h3_index"
    # table_name = "well_with_zhan_id_2kring"
    # output_file = f'{DATA_PATH}/tm_geodata/{table_name}.json'
    # additional_col = ["id_pk","wm_field","zhan_field_id"]

    # h3_cells_to_geojson(db_params, h3_column, table_name, output_file,additional_col)

    h3_column = "h3_index"
    table_name = "tm_zhan_h3_9_2ring_smooth"
    output_file = f"{DATA_PATH}/tm_geodata/{table_name}.json"
    additional_col = ["id"]

    h3_cells_to_geojson(db_params, h3_column, table_name, output_file, additional_col)
