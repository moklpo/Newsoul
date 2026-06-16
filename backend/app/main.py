from fastapi import FastAPI
from app.api.endpoints import router

app = FastAPI(title="StratBack India API")

@app.get("/")
async def root():
    return {"message": "Welcome to StratBack India API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

app.include_router(router, prefix="/api/v1")
