# backend/app/main.py
"""Main module for Pyxis API."""
# pylint: disable=C0301
from logging import basicConfig

import logfire
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from .api.main import router
from .postgres.database import engine
from .configs.settings import settings


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    description="API for Pyxis - a GIS-based data platform for oil and gas emissions monitoring",
    version="0.1.0",
)

# Add SessionMiddleware - required for OAuth flows
app.add_middleware(SessionMiddleware, secret_key=settings.SESSION_SECRET_KEY)

# Add CORS middleware if needed
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this in production to specific origins
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


@app.get("/hello")
async def hello(name: str):
    return {"message": f"hello {name}"}


@app.get("/")
async def root():
    """Root endpoint for Pyxis API."""
    return {
        "message": "Welcome to Pyxis API",
        "description": "A GIS-based data platform for oil and gas emissions monitoring",
        "docs_url": "/docs",
    }
