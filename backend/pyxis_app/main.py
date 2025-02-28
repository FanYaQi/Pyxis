from fastapi import FastAPI
from .routers import data

app = FastAPI(
    title="Pyxis API",
    description="API for Pyxis - a GIS-based data platform for oil and gas emissions monitoring",
    version="0.1.0",
)

app.include_router(data.router)


@app.get("/")
async def root():
    return {
        "message": "Welcome to Pyxis API",
        "description": "A GIS-based data platform for oil and gas emissions monitoring",
        "docs_url": "/docs",
        "endpoints": {"fields": "/fields/", "data": "/data/"},
    }
