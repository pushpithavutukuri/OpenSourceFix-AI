"""
FastAPI backend for the web UI.
Exposes endpoints that the React frontend calls.
"""

import os
import uuid
import asyncio
import logging
from typing import Optional
from pathlib import Path

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from api.pipeline_runner import PipelineRunner, PipelineStatus

logger = logging.getLogger(__name__)

app = FastAPI(title="OpenSourceFix AI", version="1.0")

# Allow the React dev server to call us
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store of active runs — fine for a demo
_runs: dict[str, PipelineRunner] = {}


class RunRequest(BaseModel):
    repo_url: str
    owner: str
    repo_name: str
    issue_number: int
    apply_patch: bool = False


class RunResponse(BaseModel):
    run_id: str


@app.post("/api/run", response_model=RunResponse)
async def start_run(req: RunRequest, background_tasks: BackgroundTasks):
    """Start a pipeline run and return a run_id for polling."""
    run_id = str(uuid.uuid4())[:8]
    runner = PipelineRunner(run_id=run_id)
    _runs[run_id] = runner
    background_tasks.add_task(runner.run, req)
    return RunResponse(run_id=run_id)


@app.get("/api/run/{run_id}")
async def get_status(run_id: str):
    """Poll for pipeline status and step updates."""
    runner = _runs.get(run_id)
    if not runner:
        raise HTTPException(status_code=404, detail="Run not found")
    return runner.status()


@app.get("/api/run/{run_id}/result")
async def get_result(run_id: str):
    """Get the final result once the run is complete."""
    runner = _runs.get(run_id)
    if not runner:
        raise HTTPException(status_code=404, detail="Run not found")
    if not runner.is_done():
        raise HTTPException(status_code=202, detail="Run still in progress")
    return runner.result()


@app.get("/health")
async def health():
    return {"status": "ok"}
