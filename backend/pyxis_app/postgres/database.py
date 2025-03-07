import os

import logfire
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Load environment variables from .env
# First, look in current directory
if os.path.exists(".env"):
    load_dotenv()
# Then look in project root (in case running from web/ directory)
elif os.path.exists("../.env"):
    load_dotenv("../.env")

# Default if not found in environment
DEFAULT_DB_URL = "postgresql+psycopg2://postgres:postgres@localhost:5555/pyxis"
SQLALCHEMY_DATABASE_URL = os.getenv("SQLALCHEMY_DATABASE_URL", DEFAULT_DB_URL)

print(f"Connecting to database: {SQLALCHEMY_DATABASE_URL}")

engine = create_engine(SQLALCHEMY_DATABASE_URL)

# Each of this instance is a database connection.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Configure Logfire to instrument the SQLAlchemy engine
logfire.instrument_sqlalchemy(engine)
