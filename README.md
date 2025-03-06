# Pyxis

A GIS-based data platform for oil and gas emissions monitoring. Pyxis integrates diverse data sources to consistently estimate and monitor greenhouse gas emissions in the oil and gas industry.
## Docker Setup (Recommended)

1. Clone the repository.
2. Go under the `backend` directory. Please create a `.env` file under the backend folder.
   Copy`.env.example` to `.env` and update the configuration
3. Build and run the Docker containers under `Pyxis` root folder:

```bash
docker-compose up -d
```

4. Initialize the database:

```bash
curl -X POST http://localhost:8000/data/init_db
```

5. Access the API at http://localhost:8000 and API documentation at http://localhost:8000/docs


## Local Setup (macOS)

1. PostgresSQL Database:
  - `brew install postgres`, then create a database called `pyxis`
  - [**PostGIS**](https://postgis.net/documentation/getting_started/install_macos/) - A postgres extension to manage geo data: `brew install postgis`
  - After the previous step, use `psql pyxis` to log into pyxis db. Then type `CREATE EXTENSION postgis;` and `CREATE EXTENSION postgis_raster;` to enable postgis extension. You can then use `\dx` to see all the enabled extensions.

2. [H3](https://h3geo.org/) version 4.x - Uber developed geo indexing library.
  - The core H3 library is written in C, so in order to use it in other languages, a binding is required.
  - [**h3-pg**](https://github.com/zachasme/h3-pg): binding for PostgresSQL database.
  - [**pgxn**](https://pgxn.org/about/) - A PostgresSQL extension management tool: in the previous setup, we used this to install and load H3 extension to our database.

After all these steps, use `\dx` in postgres database to see the extensions, it should look something like this:

```zsh
pyxis=# \dx
                                    List of installed extensions
      Name      | Version |   Schema   |                        Description
----------------+---------+------------+------------------------------------------------------------
 h3             | 4.1.3   | public     | H3 bindings for PostgreSQL
 h3_postgis     | 4.1.3   | public     | H3 PostGIS integration
 plpgsql        | 1.0     | pg_catalog | PL/pgSQL procedural language
 postgis        | 3.3.4   | public     | PostGIS geometry and geography spatial types and functions
 postgis_raster | 3.3.4   | public     | PostGIS raster types and functions
(5 rows)
```

## Project Structure

- `/scripts_n_notebooks`: Data processing scripts and utilities
- `/backend`: FastAPI web application
- `/docs`: Documentation and diagrams

## Troubleshooting

1. When installing `psycopg2`, `Error: pg_config executable not found.`:

https://stackoverflow.com/questions/35104097/how-to-install-psycopg2-with-pg-config-error

2. When writing queries in postgres, keep in mind to check the (x,y) coordinates for sequence of longitude and latitude.

3. If you have issues with Docker setup, ensure Docker is running and ports 5432 and 8000 are available.

