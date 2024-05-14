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

###for wm data
# Production method mapping
production_method_map = {
    'Artificiallift': 'Downhole pump',
    'CO2flooding': 'Gas flooding',
    'Nitrogenflooding': 'Gas flooding',
    'Waterdrive': 'Water flooding',
    'Steamflooding': 'Steam flooding',
    'Waterinjection': 'Water reinjection',
    # Additional methods can be added here
}

def parse_production_methods(row, production_method_col):
    """Generate binary indicators for production methods from concatenated source fields."""
    # Safely process each column, skipping None values
    production_methods = ','.join(
        (row[col].replace(' ', '').lower() if row[col] else '') for col in production_method_col if col in row
    )
    method_indicators = pd.Series(production_methods).str.get_dummies(sep=',')
    # Initialize all production method columns with False (0)
    method_results = {value: 0 for value in production_method_map.values()}
    # Update method_results based on mapping
    for source_method, target_method in production_method_map.items():
        if source_method.replace(' ', '').lower() in method_indicators:
            method_results[target_method] = 1
    return method_results

def process_mtr2ft(input):
    return input*3.28084

def process_kbl2bbl(input):
    return input*1000

def process_offtag2bin(input):
    if input is not None and isinstance(input, str):
        if unidecode(input.lower()) in ('onshore'):
            return 0
        elif unidecode(input.lower()) in ('offshore'):
            return 1

def process_ppm2pc(input):
    return input*0.0001

###for anp
def process_getyr(input):
    if input is not None:
        return input[0:4]
    
def process_function_unit_pt(input):
    if input is not None and isinstance(input, str):
        if unidecode(input.lower()) in ('oleo'):
            return 'oil'
        elif unidecode(input.lower()) in ('gas'):
            return 'gas'
    return None

def process_calgor(gas,oil):
    if gas is not None and oil is not None and oil != 0:
        return gas*6000/oil

def process_offtag2bin_anp(input):
    if input is not None and isinstance(input, str):
        if unidecode(input.lower()) in ('Earth'):
            return 0
        elif unidecode(input.lower()) in ('Sea'):
            return 1
###for gogi
def process_getyr_gogi(input):
    if input is not None:
        return input[6:10]

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
    'Field name': (['field_name'], process_keep),
    'Function unit': (['field_oil_'], process_function_unit),
    'Production method': (['field_dr_1', 'field_dr_2', 'field_dr_3'], parse_production_methods),
    'Number of producing wells':(['prodw_cnt'],process_keep),
    'Number of water injecting wells':(['waterw_cnt'],process_keep),
    'Field depth':(['f_depth_mt'],process_mtr2ft),
    'Field age':(['field_year'],process_keep),
    'Oil production volume':(['f_producti'],process_kbl2bbl),
    'Offshore':(['onshore_of'],process_offtag2bin),
    'API gravity (oil at standard pressure and temperature, or "dead oil")':(['f_api__api'],process_keep),
    'CO2':(['f_co2__prc'],process_keep),
    'H2S':(['f_h2s__ppm'],process_ppm2pc),
    'Gas-to-oil ratio (GOR)':(['f_gas_oil_'],process_keep)
  },
  'anp':{
    'Field name': (['Field'], process_keep),
    'Function unit': (['FLUIDO_PRI'], process_function_unit_pt),
    'Field age':(['Start of P'],process_getyr),
    'Oil production volume':(['Oil (bbl/d'],process_keep),
    'Gas-to-oil ratio (GOR)':(['Natural Ga','Oil (bbl/d'],process_calgor),
    'Number of producing wells':(['Number of'],process_keep),
    'Offshore':(['Location_x'],process_offtag2bin_anp),
    'API gravity (oil at standard pressure and temperature, or "dead oil")':(['API Petrol'],process_keep)
  },
  'gogi':{
    'Field name': (['Facility_N'], process_keep),
    'Function unit': (['Commodity'], process_function_unit_pt),
    'Field age':(['Installati'],process_getyr_gogi),
    'Offshore':(['Onshore_Of'],process_offtag2bin)
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
                processed_row['Centroid H3 Index'] = h3.geo_to_h3(row.geometry.centroid.y, row.geometry.centroid.x, self.h3_res)
                processed_row['geometry'] = row.geometry

            processed_row['Source ID'] = self.source_id
            processed_row['Source Name'] = self.name

            for new_col_name, (input_cols, func) in self.config.items():
                if new_col_name == 'Production method':
                    production_methods = func(row, input_cols)
                    processed_row.update(production_methods)
                else:
                    inputs = [row[col] for col in input_cols if col in row] 
                    processed_row[new_col_name] = func(*inputs) if len(inputs) == len(input_cols) else None # Only proceed if all columns exist
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

def main():
    # Initialize WMDataSource with data and operations configuration

    zhan_data = gpd.read_file("./db/data/br_geodata/br_zhan/BR.shp")
    zhan = DataSource(data=zhan_data,name = 'Zhang et al.', type = 'peer reviewed paper', time = '2021',
                    url='https://iopscience.iop.org/article/10.1088/1748-9326/ac3956/meta',
                    config=op_table['zhan'])
    zhan.process()
    zhan_source_table = zhan.source_info_table()
    zhan.data_score([5,4,3])
    print(zhan.metadata)
    zhan_source_table.to_excel('./db/data/br_geodata/data_standardization/zhan.xlsx')

    wm_data = gpd.read_file("./db/data/br_geodata/wm/BR.shp")
    wm = DataSource(data=wm_data,name = 'Wood Mackenzie', type = 'commercial', time = '2022',
                    url='Not open source',
                    config=op_table['wm'])
    wm.process()
    wm_source_table = wm.source_info_table()
    wm.data_score([4,5,5])
    print(wm.metadata)
    wm_source_table.to_excel('./db/data/br_geodata/data_standardization/wm.xlsx')

    anp_data = gpd.read_file("./db/data/br_geodata/anp/BR.shp")
    anp = DataSource(data=anp_data,name = 'National Agency for Petroleum, Natural Gas and Biofuels', type = 'government', time = '2024',
                    url='https://www.gov.br/anp/pt-br/assuntos/exploracao-e-producao-de-oleo-e-gas/dados-tecnicos',
                    config=op_table['anp'])
    anp.process()
    anp_source_table = anp.source_info_table()
    anp.data_score([4.5,5,4])
    print(anp.metadata)
    anp_source_table.to_excel('./db/data/br_geodata/data_standardization/anp.xlsx')

    gogi_data = gpd.read_file("./db/data/br_geodata/gogi/BR.shp")
    gogi = DataSource(data=gogi_data,name = 'National Energy Technology Laboratory', type = 'national lab', time = '2023',
                    url='https://edx.netl.doe.gov/dataset/global-oil-gas-features-database',
                    config=op_table['gogi'])
    gogi.process()
    gogi_source_table = gogi.source_info_table()
    gogi.data_score([4.5,5,3]) #source/ recency/ coverage score
    print(gogi.metadata)
    gogi_source_table.to_excel('./db/data/br_geodata/data_standardization/gogi.xlsx')

    source_metadata = pd.DataFrame([zhan.metadata,wm.metadata,anp.metadata,gogi.metadata])
    source_metadata.to_excel('./db/data/br_geodata/data_standardization/source_metadata.xlsx')   

if __name__ == '__main__':
    main()