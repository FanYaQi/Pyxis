import psycopg2
import h3pandas
import h3
import geopandas as gpd

def create_poly_h3_table(db_params, existing_table_name,new_table_name, h3_resolution,
                    id_column, geometry_column):
    try:
        # Connect to the database
        conn = psycopg2.connect(**db_params)
        cursor = conn.cursor()

        # Retrieve data from the existing table using Geopandas
        gdf = gpd.read_postgis(f"""SELECT {id_column}, {geometry_column} FROM {existing_table_name}
                               """, conn, geom_col="geometry")

        # Convert geometry to h3 index
        h3_polyfill_data = gdf.h3.polyfill_resample(h3_resolution)

        # Create the new table
        create_table_query = f"""
        CREATE TABLE {new_table_name} (
            {id_column} numeric,
            h3_index h3index,
            primary key ({id_column}, h3_index)
        );
        """
        cursor.execute(create_table_query)
        conn.commit()

        insert_query = f"""
        INSERT INTO {new_table_name} ({id_column}, h3_index) VALUES (%s, %s);
        """

        for _, row in h3_polyfill_data.iterrows():
            id = row[id_column]
            h3_index = row.name
            cursor.execute(insert_query, (id, h3_index))

        conn.commit()
        cursor.close()
        conn.close()
        print(f"H3 indexes added to the {new_table_name} table.")
    
    except Exception as e:
        print(f"An error occurred: {str(e)}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def create_pt_h3_table(db_params, existing_table_name, new_table_name, 
                    h3_resolution, id_column, geometry_column, assoc_field_column):
    try:
        # Connect to the database
        conn = psycopg2.connect(**db_params)
        cursor = conn.cursor()

        # Retrieve data from the existing table using Geopandas
        gdf = gpd.read_postgis(f"""
                               SELECT {id_column}, {geometry_column}, {assoc_field_column}
                               FROM {existing_table_name}""", conn, geom_col="geometry")
        gdf[assoc_field_column] = gdf[assoc_field_column].fillna(-1)

        # Convert geometry to H3 index
        h3_indexes = []
        for geom in gdf[geometry_column]:
            if geom.geom_type == 'Point':
                h3_indexes.append(h3.geo_to_h3(geom.y, geom.x, h3_resolution))
            else:
                centroid = geom.centroid
                h3_indexes.append(h3.geo_to_h3(centroid.y, centroid.x, h3_resolution))

        gdf['h3_index'] = h3_indexes

        # Create the new table
        create_table_query = f"""
        CREATE TABLE {new_table_name} (
            {id_column} numeric,
            h3_index h3index,
            {assoc_field_column} numeric,
            PRIMARY KEY ({id_column}, h3_index)
        );
        """
        cursor.execute(create_table_query)
        conn.commit()

        insert_query = f"""
        INSERT INTO {new_table_name} 
        ({id_column}, h3_index, {assoc_field_column}) VALUES (%s, %s, %s);
        """

        # Prepare a list of value tuples for the batch insert
        values = [(row[id_column], row['h3_index'],row[assoc_field_column]) for index, row in gdf.iterrows()]

        # Execute the batch insert
        cursor.executemany(insert_query, values)
        conn.commit()
        cursor.close()
        conn.close()

        print(f"H3 indexes added to the {new_table_name} table.")

    except Exception as e:
        print(f"An error occurred: {str(e)}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
    

if __name__ == "__main__":
    # PostgreSQL connection parameters
    db_params = {
        "host": "localhost",
        "database": "postgres",
        "user": "yaqifan",
        "password": "6221"
    }

    ## Create h3 for field
    existing_table_name = "zhan_tm_field"
    h3_resolution = 9
    new_table_name = f"{existing_table_name}_h3_{h3_resolution}"
    primary_id_column = "id"
    geometry_column = "geometry"

    create_poly_h3_table(db_params, existing_table_name, new_table_name, h3_resolution,
                    primary_id_column, geometry_column)
    
    ## Create h3 for well
    # existing_table_name = "wm_global_well"
    # h3_resolution = 7
    # new_table_name = f"{existing_table_name}_h3_{h3_resolution}"
    # id_column = "id"
    # geometry_column = "geometry"
    # field_id_column = "id_field_associated"

    # create_pt_h3_table(db_params, existing_table_name, new_table_name, h3_resolution, id_column, geometry_column, field_id_column)

