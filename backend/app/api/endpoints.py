from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List
from app.engine.strategy_engine import StrategyEngine
import uuid

router = APIRouter()
engine = StrategyEngine()

# In-memory storage for job status and results (replace with Redis/DB for production)
jobs = {}

class BacktestRequest(BaseModel):
    strategy_id: str
    symbol: str
    exchange: str = "NSE"
    interval: str = "1min"
    from_date: str
    to_date: str
    parameters: Dict[str, Any]
    initial_capital: float = 100000.0

@router.post("/backtest/run")
async def run_backtest(request: BacktestRequest):
    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "running", "result": None}
    
    # Run synchronously for MVP; in production, use BackgroundTasks or Celery
    try:
        if request.strategy_id == "sma_crossover":
            result = engine.run_sma_crossover(
                symbol=request.symbol,
                fast_window=request.parameters.get("short_window", 20),
                slow_window=request.parameters.get("long_window", 50),
                exchange=request.exchange,
                granularity=request.interval
            )
            jobs[job_id] = {"status": "completed", "result": result}
        else:
            raise HTTPException(status_code=400, detail="Strategy not supported")
    except Exception as e:
        jobs[job_id] = {"status": "failed", "error": str(e)}
        raise HTTPException(status_code=500, detail=str(e))
    
    return {"job_id": job_id}

@router.get("/backtest/status/{job_id}")
async def get_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"status": jobs[job_id]["status"]}

@router.get("/backtest/results/{job_id}")
async def get_results(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    if jobs[job_id]["status"] != "completed":
        raise HTTPException(status_code=400, detail="Job not completed yet")
    return jobs[job_id]["result"]

@router.get("/data/symbols")
async def get_symbols():
    # Placeholder for fetching from SQLite metadata
    return ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "TATASTEEL"]
