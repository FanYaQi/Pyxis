import psycopg2
import h3
import h3pandas
import pandas as pd
from utils.path_util import DATA_PATH


def kring_smooth_h3_table(
    db_params, id_column, h3_column, table_name, new_table_name, k
):
    try:
        # Establish a database connection
        conn = psycopg2.connect(**db_params)
        cursor = conn.cursor()

        # Execute the SQL query to fetch H3 cell indexes and the additional columns
        sql_query = f"""
        SELECT {id_column}, {h3_column}
        FROM {table_name};
        """
        cursor.execute(sql_query)

        # Fetch all H3 cell indexes
        rows = cursor.fetchall()
        original_table = pd.DataFrame(columns=[id_column, h3_column])
        # Smooth the H3 cell by k_ring
        for row in rows:
            original_table = pd.concat(
                [original_table, pd.DataFrame([row], columns=[id_column, h3_column])],
                ignore_index=True,
            )

        original_table = original_table.set_index([h3_column])
        smoothed_table = original_table.h3.k_ring(k, explode=True)

        # drop duplicate h3 index for same id
        smoothed_table = smoothed_table.drop_duplicates(subset=[id_column, "h3_k_ring"])

        # create new table for the smoothed h3 index
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

        for _, row in smoothed_table.iterrows():
            id = row[id_column]
            h3_index = row["h3_k_ring"]
            cursor.execute(insert_query, (id, h3_index))

        conn.commit()
        print(f"Smoothed H3 indexes added to the {new_table_name} table.")

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
    h3_column = "h3_index"
    id_column = "id"
    k = 2
    table_name = "tm_zhan_h3_9"
    output_table = f"{table_name}_{k}ring_smooth"

    kring_smooth_h3_table(db_params, id_column, h3_column, table_name, output_table, k)
