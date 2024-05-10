import os
import json
from abc import ABC
import pandas as pd
import h3
import geopandas as gpd
import uuid
from unidecode import unidecode

##note: give output for the source metadata table and source info table

with open('./db/data/OPGEE_cols.json', 'r') as json_file:
    OPGEE_cols = json.load(json_file)

##define the data conversion function
###for zhan's data
def process_keep(input):
    return input

def process_function_unit(input):
    if input is not None and isinstance(input, str):
        if unidecode(input.lower()) in ('oil', 'gas'):
            return input.lower()
    return None
# def process_prod_y2d(input):
#     return input / 365 if input is not None else None

# def process_BCM2FOR(BCM, oil):
#     if BCM is not None and oil is not None and oil != 0:
#         return BCM * 35314666572.222 / oil
#     return None

##for wm data


##define operation table for each column in different data sources
op_table = {
  'zhan':{
    'Field name': (['N_Fldname'], process_keep),
    'Function unit': (['Product_Ty'], process_function_unit), #zhan's data is empty for this column
    'Gas-to-oil ratio (GOR)': (['SUM_GOR'], process_keep),
    'Oil production volume': (['SUM_OIL_PR'], process_keep), #zhan's data is bbl/d
    # 'Flaring-to-oil ratio': (['BCM_2019','SUM_OIL_PR'], process_BCM2FOR)
  },
  'wm':{
    'Field name': (['N_Fldname'], process_keep)
  }
}
##define class for all datasource and process it to OPGEE cols
class DataSource(ABC):
    """Abstract Base Class for data sources."""
    
    def __init__(self, data, name=None, url=None, type=None, time=None, 
                 config=None, target_schema = OPGEE_cols, description='', h3_res=9):
        super().__init__()
        self.data = data
        self.name = name
        self.url = url
        self.type = type
        self.time = time

        self.config = config
        self.target_schema = target_schema
        self.description = description
        self.h3_res = h3_res
        self.data_score_avg = None
        self.source_id = str(uuid.uuid4())
        self.processed_data = []
        self.metadata = {
            'Source ID': self.source_id,
            'Name': self.name,
            'Source URL': self.url,
            'Source Type': self.type,
            'Source Time': self.time,
            'Reliability Score': None,
            'Recency Score': None,
            'Coverage Score': None,
            'Data Score': self.data_score_avg
        }
        
    def process(self):
        """Apply configured operations to each row of the data, mapping old column names to new."""
        field_id_counter = 0
        for _, row in self.data.iterrows():
            processed_row = {col: None for col in self.target_schema} # Initialize all columns to None
            processed_row['Field ID'] = field_id_counter
            field_id_counter += 1
            
            # Check if geometry data is available
            if 'geometry' in row and not pd.isnull(row.geometry):
                processed_row['geometry'] = row.geometry
                processed_row['Centroid H3 Index'] = h3.geo_to_h3(row.geometry.centroid.y, row.geometry.centroid.x, self.h3_res)
            else:
                processed_row['geometry'] = None
                processed_row['Centroid H3 Index'] = None
                
            processed_row['Source ID'] = self.source_id
            for new_col_name, (input_cols, func) in self.config.items():
                inputs = [row[col] for col in input_cols if col in row]
                if len(inputs) == len(input_cols): # Only proceed if all columns exist
                    processed_row[new_col_name] = func(*inputs)
                else:# Handle missing columns by setting to None
                    processed_row[new_col_name] = None
            field_name = processed_row['Field name']
            processed_row['Name'] = unidecode(field_name).lower() if field_name else None
            self.processed_data.append(processed_row)
        
    
    def source_info_table(self):
        """Convert processed data back to DataFrame."""
        source_info = pd.DataFrame(self.processed_data)
        # List the first few columns you want at the front
        new_order = ['Field ID', 'Name', 'Centroid H3 Index', 'Source ID'] 
        # Add the rest of the columns that are not included in the new_order list
        new_order += [col for col in source_info.columns if col not in new_order]
        # Rearrange the DataFrame according to new_order
        source_info = source_info[new_order]
        return source_info
    
    def data_score(self, score_cols, score_weight = [0.5,0.3,0.2]): #calculation of the data quality score 
        self.metadata['Reliability Score'] = score_cols[0]
        self.metadata['Recency Score'] = score_cols[1]
        self.metadata['Coverage Score'] = score_cols[2]
        # for source reliability/ recency/ coverage score (coverage refer to data richness in both numerical and spatial data coverage)
        self.data_score_avg = sum([score_weight[i] * score_cols[i] for i in range(len(score_weight))])
        self.metadata['Data Score'] = self.data_score_avg



# Initialize WMDataSource with data and operations configuration
zhan_data = gpd.read_file("./db/data/br_geodata/br_zhan/BR.shp")
zhan = DataSource(data=zhan_data,name = 'Zhang et al.', type = 'peer reviewed paper', time = '2021',
                  url='https://iopscience.iop.org/article/10.1088/1748-9326/ac3956/meta',
                  config=op_table['zhan'])
zhan.process()
zhan_source_table = zhan.source_info_table()
zhan.data_score([5,4,3])
print(zhan.metadata)
zhan_source_table.to_csv('./db/data/zhan.csv')
