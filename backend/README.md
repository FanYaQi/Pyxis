# Pyxis Project Backend
Backend for project Pyxis.

# Prerequisite
Please install `pipenv`.

# Prepare Environment
Run `pipenv install` to install the dependencies.
Run `pipenv run` to activate the environment.
Run `uvicorn pyxis_app.main:app --reload` to run the application.

# Troubleshooting

1. `Error: pg_config executable not found.` when installing `psycopg2` via `pipenv`.
  - On Ubuntu: `sudo apt install libpq-dev`
