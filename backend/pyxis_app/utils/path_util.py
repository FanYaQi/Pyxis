import os
from pathlib import Path

# Get the base directory for data files
# By default, look for data in the db/data directory relative to the project root
ROOT_DIR = Path(os.path.abspath(os.path.dirname(__file__))).parent.parent.parent
DATA_PATH = os.environ.get("DATA_DIR", os.path.join(ROOT_DIR, "db", "data"))

# Ensure the data path exists
os.makedirs(DATA_PATH, exist_ok=True)


def get_data_path(*paths):
    """
    Construct a path within the data directory.

    Args:
        *paths: Path segments to append to the data directory path

    Returns:
        str: Absolute path to the requested file/directory
    """
    return os.path.join(DATA_PATH, *paths)
