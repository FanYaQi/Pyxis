import pandas as pd
import geopandas as gpd
import re

# Load data
anp_well_data = pd.read_excel(
    "./db/data/br_geodata/anp/raw/ANP_well_data_translated.xlsx"
)
field_registration_data = pd.read_excel(
    "./db/data/br_geodata/anp/raw/field registration data_translated.xlsx"
)
field_movement_data = pd.read_excel(
    "./db/data/br_geodata/anp/raw/translated_data_for_field_movement_2021.xlsx"
)
campos_gishub = gpd.read_file(
    "./db/data/br_geodata/anp/raw/ANP field shape/campos_gishub_db.shp"
)


# 1. Process ANP Well Data
def process_anp_well_data(df):
    df = df.rename(
        columns={
            "Field (Well)": "Field name",
            "Final drilling depth (m)": "Final drilling depth",
        }
    )
    field_depth = df.groupby("Field name")["Final drilling depth"].mean().reset_index()
    field_depth = field_depth.rename(columns={"Final drilling depth": "Field depth"})
    return field_depth


field_depth = process_anp_well_data(anp_well_data)


# 2. Process Field Registration Data
def process_field_registration_data(df):
    df = df.rename(
        columns={
            "Field": "Field name",
            "API Petroleum Grade": "API",
            "Start of Production": "Start of Production",
            "Location": "Offshore",
        }
    )
    df["Field age"] = pd.to_datetime(df["Start of Production"]).dt.year
    field_registration = df[["Field name", "API", "Field age", "Offshore"]]
    return field_registration


field_registration = process_field_registration_data(field_registration_data)


# 3. Process Field Movement Data
def process_field_movement_data(df):
    df = df.rename(columns={"Field": "Field name"})
    numeric_cols = df.select_dtypes(include="number").columns
    # Filter rows where 'Period' matches the expected format '%Y-%m'
    df = df[df["Period"].apply(lambda x: bool(re.match(r"^\d{4}-\d{2}$", str(x))))]
    df["Period"] = pd.to_datetime(df["Period"], format="%Y-%m")
    df["days_in_month"] = df["Period"].dt.days_in_month
    total_days = (
        df.groupby("Field name")["days_in_month"]
        .sum()
        .reset_index()
        .rename(columns={"days_in_month": "total_days"})
    )
    df = df.merge(total_days, on="Field name", how="left")
    for col in numeric_cols:
        df[col] = df[col] * df["days_in_month"] / df["total_days"]
    field_movement_avg = df.groupby("Field name")[numeric_cols].sum().reset_index()
    return field_movement_avg


field_movement_avg = process_field_movement_data(field_movement_data)


# 4. Process Campos GISHub Data
def process_campos_gishub(df):
    df = df.rename(
        columns={
            "name": "Field name",
            "fluido_pri": "Function unit",
            "etapa": "Field status",
        }
    )
    df = df[df["Function unit"].isin(["ÓLEO", "GÁS"])]  # Keep only oil and gas fields
    df["Function unit"] = df["Function unit"].replace({"ÓLEO": "oil", "GÁS": "gas"})
    return df[["Field name", "Function unit", "Field status", "geometry"]]


campos_gishub_clean = process_campos_gishub(campos_gishub)

# Merge all datasets
combined_data = campos_gishub_clean
combined_data = combined_data.merge(field_depth, on="Field name", how="left")
combined_data = combined_data.merge(field_registration, on="Field name", how="left")
combined_data = combined_data.merge(field_movement_avg, on="Field name", how="left")
combined_data = combined_data.drop_duplicates(subset="Field name")

# Add Field ID column
combined_data.reset_index(inplace=True)
combined_data.rename(columns={"index": "Field ID"}, inplace=True)

# Truncate column names to 10 characters without causing duplicates
column_names = []
seen = set()
for col in combined_data.columns:
    truncated_col = col if len(col) <= 10 else col[:10]
    while truncated_col in seen:
        truncated_col = truncated_col[:-1] + "_"
    column_names.append(truncated_col)
    seen.add(truncated_col)
combined_data.columns = column_names

# Save the final shapefile with adjusted encoding
combined_data.to_file(
    "./db/data/br_geodata/anp/raw/combined_anp_data.shp", encoding="utf-8"
)

print(
    "Data cleaning and combination complete. The final shapefile is saved as 'combined_anp_data.shp'"
)
