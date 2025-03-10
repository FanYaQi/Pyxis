from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.configs.settings import settings


SQLALCHEMY_DATABASE_URL = str(settings.SQLALCHEMY_DATABASE_URI)

print(f"Connecting to database: {SQLALCHEMY_DATABASE_URL}")

engine = create_engine(SQLALCHEMY_DATABASE_URL)

# Each of this instance is a database connection.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
