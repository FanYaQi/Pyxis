from utils.path_util import DATA_PATH
from data_processing.data_standardization import DataSource
from get_pyxis_match_table import load_source_data
from pathlib import Path
from fuzzywuzzy import fuzz
import pandas as pd
import json

# List of OPGEE columns
with open(f"{DATA_PATH}/OPGEE_cols.json", "r") as json_file:
    OPGEE_cols = json.load(json_file)

# with open('./data/OPGEE_cols.json', 'r') as json_file:
#     OPGEE_cols = json.load(json_file)


def process_keep(data):
    # Function to process and keep the data as it is
    return data


def process_age_to_year(data):
    # Function to convert field age to year
    current_year = pd.Timestamp.now().year
    return current_year - data


def update_paper_data(df, name, n_explain, type, time, url, config, score):
    ds_new = DataSource(
        data=df,
        name=name,
        n_explain=n_explain,
        type=type,
        time=time,
        url=url,
        config=config,
    )
    ds_new.process()
    ds_source_table = ds_new.source_info_table()
    ds_new.data_score(score)
    print(ds_new.metadata)
    # ds_source_table.to_csv('./data/br_geodata/data_standardization/'+name+'.csv')
    ds_source_table.to_csv(
        f"{DATA_PATH}/br_geodata/data_standardization/" + name + ".csv"
    )


def calculate_name_match_score(name1, name2, weight=1):
    """Calculate match score based on name similarity and H3 distance (must in the same resolution)"""
    if name1 is not None and name2 is not None:
        name_score = fuzz.ratio(name1, name2)
    else:
        name_score = 0

    return name_score * weight


def match_sources(pyxis_match_table, new_source, score_threshold=60):
    """Match new source fields with existing entries in the Pyxis Match Table"""
    new_pyxis_id = (
        pyxis_match_table["Pyxis ID"].max() + 1
    )  # Start new IDs from the max existing ID + 1
    entries_to_add = []
    for _, row in new_source.iterrows():
        if pd.isna(row["Name"]):  # Skip rows with None as the Name
            continue
        best_score = 0
        best_match_id = None
        best_match_h3 = None
        for _, match_row in pyxis_match_table.iterrows():
            score = calculate_name_match_score(row["Name"], match_row["Name"])
            if score > best_score:
                best_score = score
                best_match_id = match_row["Pyxis ID"]
                best_match_h3 = match_row["Centroid H3 Index"]

        match_entry = {
            "Pyxis ID": best_match_id
            if best_score >= score_threshold
            else new_pyxis_id,
            "Name": row["Name"],
            "Centroid H3 Index": best_match_h3
            if best_score >= score_threshold
            else row["Centroid H3 Index"],
            "Source ID": row["Source ID"],
            "Source Name": row["Source Name"],
            "Field ID": row["Field ID"],
            "Match Score": best_score if best_score >= score_threshold else 100,
        }
        entries_to_add.append(pd.DataFrame([match_entry]))
        if best_score < score_threshold:  # Only increment if no match was found
            new_pyxis_id += 1

    pyxis_match_table = pd.concat(
        [pyxis_match_table] + entries_to_add, ignore_index=True
    )

    return pyxis_match_table


if __name__ == "__main__":
    # Initialize the operation dictionary
    paper_op_table = {}

    # Add uniform columns to the dictionary with process_keep
    for col in OPGEE_cols:
        paper_op_table[col] = ([col], process_keep)

    # Add the specific column with a different processing function

    # paper_op_table['Field age'] = (['Field age'], process_age_to_year)
    papers = {
        "spe-210009-ms": {
            "n_explain": "paper spe-210009-ms",
            "type": "peer reviewed paper",
            "time": "2022",
            "score": [5, 4.6, 2.5],
            "url": "https://onepetro.org/SPEATCE/proceedings-abstract/22ATCE/2-22ATCE/D022S073R001/509056?redirectedFrom=PDF",
        },
        "spe-162323-ms": {
            "n_explain": "paper spe-162323-ms",
            "type": "peer reviewed paper",
            "time": "2012",
            "score": [5, 4.1, 1.8],
            "url": "https://onepetro.org/SPEATCE/proceedings-abstract/22ATCE/2-22ATCE/D022S073R001/509056?redirectedFrom=PDF",
        },
        "spe-140145-ms": {
            "n_explain": "paper spe-140145-ms",
            "type": "peer reviewed paper",
            "time": "2011",
            "score": [5, 4.0, 1.7],
            "url": "https://onepetro-org.stanford.idm.oclc.org/SPEDC/proceedings/11DC/All-11DC/SPE-140145-MS/149360?searchresult=1",
        },
        "spe-94706-ms": {
            "n_explain": "paper spe-94706-ms",
            "type": "peer reviewed paper",
            "time": "2005",
            "score": [5, 3.8, 2.7],
            "url": "https://onepetro-org.stanford.idm.oclc.org/SPEEFDC/proceedings/05EFDC/All-05EFDC/SPE-94706-MS/88998?searchresult=1",
        },
        "seg-2018-2990024": {
            "n_explain": "paper seg-2018-2990024",
            "type": "peer reviewed paper",
            "time": "2018",
            "score": [5, 4.3, 1.5],
            "url": "https://onepetro.org/SEGAM/proceedings-abstract/SEG18/All-SEG18/SEG-2018-2990024/104118?redirectedFrom=PDF",
        },
        "seg-2005-2645": {
            "n_explain": "paper seg-2005-2645",
            "type": "peer reviewed paper",
            "time": "2005",
            "score": [5, 3.8, 1.6],
            "url": "https://onepetro.org/SEGAM/proceedings-abstract/SEG05/All-SEG05/SEG-2005-2645/92582",
        },
        "otc-31900-ms": {
            "n_explain": "paper otc-31900-ms",
            "type": "peer reviewed paper",
            "time": "2022",
            "score": [5, 4.6, 1.6],
            "url": "https://onepetro.org/OTCONF/proceedings-abstract/22OTC/2-22OTC/D021S018R007/484398",
        },
        "otc-30780-ms": {
            "n_explain": "paper otc-30780-ms",
            "type": "peer reviewed paper",
            "time": "2020",
            "score": [5, 4.4, 2.2],
            "url": "https://onepetro.org/OTCONF/proceedings-abstract/20OTC/4-20OTC/D041S051R003/107449",
        },
        "otc-22612-ms": {
            "n_explain": "paper otc-22612-ms",
            "type": "peer reviewed paper",
            "time": "2011",
            "score": [5, 4.0, 1.7],
            "url": "https://onepetro.org/OTCBRASIL/proceedings-abstract/11OBRA/All-11OBRA/OTC-22612-MS/36956",
        },
        "otc-21934-ms": {
            "n_explain": "paper otc-21934-ms",
            "type": "peer reviewed paper",
            "time": "2011",
            "score": [5, 4.0, 1.6],
            "url": "https://onepetro.org/OTCONF/proceedings-abstract/11OTC/All-11OTC/OTC-21934-MS/36820",
        },
        "otc-8879-ms": {
            "n_explain": "paper otc-8879-ms",
            "type": "peer reviewed paper",
            "time": "1998",
            "score": [5, 3.4, 2.6],
            "url": "https://onepetro-org.stanford.idm.oclc.org/OTCONF/proceedings/98OTC/All-98OTC/OTC-8879-MS/45440?searchresult=1",
        },
        "arma-10-162": {
            "n_explain": "paper arma-10-162",
            "type": "peer reviewed paper",
            "time": "2010",
            "score": [5, 3.9, 1.6],
            "url": "https://onepetro-org.stanford.idm.oclc.org/ARMAUSRMS/proceedings/ARMA10/All-ARMA10/ARMA-10-162/119406?searchresult=1",
        },
    }

    data_files = []
    for paper in papers:
        data = pd.read_excel(
            f"{DATA_PATH}/br_geodata/paper/" + str(paper) + "_data.xlsx"
        )
        # data = pd.read_excel('./data/br_geodata/spe/'+str(paper)+'_data.xlsx')
        update_paper_data(
            data.set_index("Field ID").T,
            name=paper,
            n_explain=papers[paper]["n_explain"],
            type=papers[paper]["type"],
            time=papers[paper]["time"],
            url=papers[paper]["url"],
            config=paper_op_table,
            score=papers[paper]["score"],
        )  # for source reliability/ recency/ coverage score
        # data_files.append('./data/br_geodata/data_standardization/'+str(paper)+'.csv')
        data_files.append(
            f"{DATA_PATH}/br_geodata/data_standardization/" + str(paper) + ".csv"
        )
    # Load source data
    sources = [load_source_data(Path(data_file)) for data_file in data_files]

    # Read current the Pyxis Match Table
    pyxis_match_table = pd.read_csv(
        f"{DATA_PATH}/br_geodata/pyxis_middle_version/pyxis_match_table_v4.csv"
    )

    # Iteratively match each source to the Pyxis Match Table
    for source in sources:
        pyxis_match_table = match_sources(pyxis_match_table, source)

    # Save the Pyxis Match Table
    pyxis_match_table.to_csv(
        f"{DATA_PATH}/br_geodata/pyxis_middle_version/pyxis_match_table_v5.csv",
        index=False,
    )
