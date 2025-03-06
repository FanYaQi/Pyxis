# backend/pyxis_app/main.py
"""Main module for Pyxis API."""
# pylint: disable=C0301
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from dotenv import load_dotenv

from .routers import (
    database,
    data_source_access,
    data_sources,
    data_entries,
    pyxis,
    auth,
)

# Load environment variables
load_dotenv()

# Get session secret key from environment or use a default for development
SESSION_SECRET_KEY = os.getenv(
    "SESSION_SECRET_KEY", "dev-session-secret-key-change-this-in-production"
)

app = FastAPI(
    title="Pyxis API",
    description="API for Pyxis - a GIS-based data platform for oil and gas emissions monitoring",
    version="0.1.0",
)

# Add SessionMiddleware - required for OAuth flows
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET_KEY)

# Add CORS middleware if needed
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this in production to specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(database.router)
app.include_router(data_sources.router, prefix="/api/v1")
app.include_router(data_source_access.router, prefix="/api/v1")
app.include_router(data_entries.router, prefix="/api/v1")
app.include_router(pyxis.router, prefix="/api/v1")


@app.get("/")
async def root():
    """Root endpoint for Pyxis API."""
    return {
        "message": "Welcome to Pyxis API",
        "description": "A GIS-based data platform for oil and gas emissions monitoring",
        "docs_url": "/docs",
    }
