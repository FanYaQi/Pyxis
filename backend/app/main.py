# backend/app/main.py
"""Main module for Pyxis API."""
# pylint: disable=C0301
from logging import basicConfig

import logfire
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute
from starlette.middleware.sessions import SessionMiddleware

from .api.main import router
from .postgres.database import engine
from .configs.settings import settings


def custom_generate_unique_id(route: APIRoute) -> str:
    """Custom function to generate unique IDs for routes."""
    return f"{route.tags[0]}-{route.name}"


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
    description="API for Pyxis - a GIS-based data platform for oil and gas emissions monitoring",
)

# Add SessionMiddleware - required for OAuth flows
app.add_middleware(SessionMiddleware, secret_key=settings.SESSION_SECRET_KEY)

# Add CORS middleware if needed
# Set all CORS enabled origins
if settings.all_cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.all_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Include routers
app.include_router(router, prefix=settings.API_V1_STR)

# Configure Logfire
logfire.configure()
basicConfig(handlers=[logfire.LogfireLoggingHandler()])
logfire.instrument_system_metrics()
logfire.instrument_sqlalchemy(engine)
logfire.instrument_pydantic()
logfire.instrument_fastapi(app)


@app.get("/", tags=["root"])
async def root():
    """Root endpoint for Pyxis API."""
    return {
        "message": "Welcome to Pyxis",
        "description": "A GIS-based data platform for oil and gas emissions monitoring",
        "docs_url": "/docs",
    }
