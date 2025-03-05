"""Main module for Pyxis API."""
from fastapi import FastAPI
from .routers import database, data_entries, pyxis

app = FastAPI(
    title="Pyxis API",
    description="API for Pyxis - a GIS-based data platform for oil and gas emissions monitoring",
    version="0.1.0",
)

app.include_router(database.router)
app.include_router(data_entries.router, prefix="/api/v1")
app.include_router(pyxis.router, prefix="/api/v1")

@app.get("/")
async def root():
    """Root endpoint for Pyxis API."""
    return {
        "message": "Welcome to Pyxis API",
        "description": "A GIS-based data platform for oil and gas emissions monitoring",
        "docs_url": "/docs"
    }
