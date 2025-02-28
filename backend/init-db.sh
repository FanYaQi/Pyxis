#!/bin/bash
set -e

# This script is run when the PostgreSQL container is initialized
# It creates the necessary extensions and initializes the database

# Switch to the pyxis database
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Create extensions
    CREATE EXTENSION IF NOT EXISTS postgis;
    CREATE EXTENSION IF NOT EXISTS postgis_raster;
    CREATE EXTENSION IF NOT EXISTS h3;
    CREATE EXTENSION IF NOT EXISTS h3_postgis;

    -- Print enabled extensions
    SELECT * FROM pg_extension;
EOSQL

echo "PostgreSQL Database initialized with PostGIS and H3 extensions"