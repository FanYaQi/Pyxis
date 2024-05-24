from utils.path_util import DATA_PATH
from data_processing.data_standardization import DataSource
from get_pyxis_match_table import load_source_data,match_sources
from pathlib import Path
from fuzzywuzzy import fuzz
import pandas as pd
import json

# List of OPGEE columns
with open(f'{DATA_PATH}/OPGEE_cols.json', 'r') as json_file:
    OPGEE_cols = json.load(json_file)

def process_keep(data):
    # Function to process and keep the data as it is
    return data

def process_age_to_year(data):
    # Function to convert field age to year
    current_year = pd.Timestamp.now().year
    return current_year - data

def update_paper_data(df,name, n_explain, type, time, url, config,score):
  ds_new = DataSource(data=df, name=name, n_explain=n_explain, type=type,
                      time =time, url=url,config=config)
  ds_new.process()
  ds_source_table = ds_new.source_info_table()
  ds_new.data_score(score)
  print(ds_new.metadata)
  ds_source_table.to_csv(f'{DATA_PATH}/br_geodata/data_standardization/'+name+'.csv')

def calculate_name_match_score(name1, name2, weight = 0.7):
    """ Calculate match score based on name similarity and H3 distance (must in the same resolution) """
    if name1 is not None and name2 is not None:
        name_score = fuzz.ratio(name1, name2)
    else:
        name_score = 0
    
    return name_score*weight

def match_sources(pyxis_match_table, new_source, score_threshold = 60):
    """ Match new source fields with existing entries in the Pyxis Match Table """
    new_pyxis_id = pyxis_match_table['Pyxis ID'].max() + 1  # Start new IDs from the max existing ID + 1
    entries_to_add = []
    for _, row in new_source.iterrows():
        if pd.isna(row['Name']):  # Skip rows with None as the Name
            continue
        best_score = 0
        best_match_id = None
        best_match_h3 = None
        for _, match_row in pyxis_match_table.iterrows():
            score = calculate_name_match_score(row['Name'], match_row['Name'])
            if score > best_score:
                best_score = score
                best_match_id = match_row['Pyxis ID']
                best_match_h3 = match_row['Centroid H3 Index']
        
        match_entry = {
            'Pyxis ID': best_match_id if best_score >= score_threshold else new_pyxis_id,
            'Name': row['Name'],
            'Centroid H3 Index': best_match_h3 if best_score >= score_threshold else row['Centroid H3 Index'],
            'Source ID': row['Source ID'],
            'Source Name': row['Source Name'],
            'Field ID': row['Field ID'],
            'Match Score': best_score if best_score >= score_threshold else 100
        }
        entries_to_add.append(pd.DataFrame([match_entry]))
        if best_score < score_threshold:  # Only increment if no match was found
            new_pyxis_id += 1

    pyxis_match_table = pd.concat([pyxis_match_table] + entries_to_add, ignore_index=True)

    return pyxis_match_table

if __name__ == '__main__':
  # Initialize the operation dictionary
  paper_op_table = {}

  # Add uniform columns to the dictionary with process_keep
  for col in OPGEE_cols:
      paper_op_table[col] = ([col], process_keep)

  # Add the specific column with a different processing function
  paper_op_table['Field age'] = (['Field age'], process_age_to_year)
  spe210009 = pd.read_excel(f'{DATA_PATH}/br_geodata/spe/SPE-210009-ms_data.xlsx')
  update_paper_data(spe210009,name='spe210009',n_explain='SPE paper 210009',type='peer reviewed paper',
                    time='2022', url='https://onepetro.org/SPEATCE/proceedings-abstract/22ATCE/2-22ATCE/D022S073R001/509056?redirectedFrom=PDF',
                    config=paper_op_table, score=[5,4.5,2]) #for source reliability/ recency/ coverage score 

  otc30780 = pd.read_excel(f'{DATA_PATH}/br_geodata/spe/otc-30780-ms_data.xlsx')
  update_paper_data(otc30780,name='otc30780',n_explain='One Petro paper 30780',type='peer reviewed paper',
                    time='2020', url='https://onepetro.org/OTCONF/proceedings-abstract/20OTC/4-20OTC/D041S051R003/107449?redirectedFrom=PDF',
                    config=paper_op_table, score=[5,4.2,2]) #for source reliability/ recency/ coverage score 
  
  data_files = [f'{DATA_PATH}/br_geodata/data_standardization/spe210009.csv',
                f'{DATA_PATH}/br_geodata/data_standardization/otc30780.csv']
  
  # Load source data
  sources = [load_source_data(Path(data_file)) for data_file in data_files]
  
  # Read current the Pyxis Match Table
  pyxis_match_table = pd.read_csv(f'{DATA_PATH}/br_geodata/pyxis_match_table.csv')
  
  # Iteratively match each source to the Pyxis Match Table
  for source in sources:
      pyxis_match_table = match_sources(pyxis_match_table, source)
  
  # Save the Pyxis Match Table
  pyxis_match_table.to_csv(f'{DATA_PATH}/br_geodata/pyxis_match_table_v6_paper.csv', index=False)