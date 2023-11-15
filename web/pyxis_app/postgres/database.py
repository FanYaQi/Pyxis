import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Load environment variables from .env
load_dotenv()

SQLALCHEMY_DATABASE_URL = os.getenv("SQLALCHEMY_DATABASE_URL")

engine = create_engine(SQLALCHEMY_DATABASE_URL)

# Each of this instance is a database connection.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# To be inherited by database models or classes (the ORM models).
Base = declarative_base()
