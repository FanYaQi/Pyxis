# LearnFastAPI
Repo to learn fast api.

# Prerequisite
Please install `pipenv`.

# Prepare Environment
Run `pipenv install` to install the dependencies.

Please create a `.env` file under the root folder and put your database connection information in it. For example:

```
SQLALCHEMY_DATABASE_URL="postgresql+psycopg2://username:password@127.0.0.1:5432/postgres"
```

Run `uvicorn pyxis_app.main:app --reload` to run the application.

# Troubleshooting

1. `Error: pg_config executable not found.` when installing `psycopg2` via `pipenv`.
  - On Ubuntu: `sudo apt install libpq-dev`
