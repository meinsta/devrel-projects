"""
Evaluation endpoints for the experiment dashboard.
Connects to the existing mission_control.py evaluation logic.
"""

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel
from typing import List, Dict, Optional
import json
from pathlib import Path

router = APIRouter(prefix="/api/eval", tags=["evaluation"])

# Load results from mission_control
RESULTS_FILE = Path("mission_results.json")

class ExperimentConfig(BaseModel):
    embedding_model: str
    retrieval_mode: str
    top_k: int
    noise_level: int = 0
    temperature: float = 0.0

class ExperimentResult(BaseModel):
    id: str
    config: ExperimentConfig
    recall_at_k: float
    precision: float
    latency_ms: float
    status: str
    timestamp: str

@router.post("/run")
async def run_experiment(config: ExperimentConfig, background_tasks: BackgroundTasks):
    """
    Run an evaluation experiment with the given configuration.
    """
    # TODO: Import and call your actual evaluation logic from mission_control
    # For now, return a mock response
    return {
        "status": "started",
        "experiment_id": "exp_001",
        "message": "Experiment queued"
    }

@router.get("/results")
async def get_results() -> List[ExperimentResult]:
    """
    Get all experiment results.
    """
    if not RESULTS_FILE.exists():
        return []
    
    with open(RESULTS_FILE, 'r') as f:
        results = json.load(f)
    
    return results

@router.get("/leaderboard")
async def get_leaderboard():
    """
    Get leaderboard sorted by recall@k.
    """
    results = await get_results()
    sorted_results = sorted(results, key=lambda x: x.get('recall_at_k', 0), reverse=True)
    return sorted_results[:10]  # Top 10

@router.get("/status/{experiment_id}")
async def get_experiment_status(experiment_id: str):
    """
    Check the status of a running experiment.
    """
    return {
        "experiment_id": experiment_id,
        "status": "running",
        "progress": 45,
        "current_step": "evaluating queries"
    }





