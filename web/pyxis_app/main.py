from fastapi import FastAPI
from .routers import fields

app = FastAPI()

app.include_router(fields.router)


@app.get("/")
async def root():
    return {"message": "Hello World"}
