"""
FastAPI backend for the web UI.
"""

import logging
import os
import uuid

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

from api.pipeline_runner import PipelineRunner
from utils.logger import setup_logging

setup_logging(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

app = FastAPI(title="OpenSourceFix AI", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_runs: dict[str, PipelineRunner] = {}
MAX_STORED_RUNS = 50


class RunRequest(BaseModel):
    repo_url: str
    owner: str
    repo_name: str
    issue_number: int
    apply_patch: bool = False

    @field_validator("repo_url", "owner", "repo_name")
    @classmethod
    def must_not_be_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Field must not be empty")
        return v.strip()

    @field_validator("issue_number")
    @classmethod
    def must_be_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("issue_number must be positive")
        return v


class RunResponse(BaseModel):
    run_id: str


@app.post("/api/run", response_model=RunResponse)
async def start_run(req: RunRequest, background_tasks: BackgroundTasks):
    if len(_runs) >= MAX_STORED_RUNS:
        oldest = next(iter(_runs))
        del _runs[oldest]

    run_id = str(uuid.uuid4())[:8]
    runner = PipelineRunner(run_id=run_id)
    _runs[run_id] = runner
    background_tasks.add_task(runner.run, req)
    logger.info("Started run %s for %s/%s#%d", run_id, req.owner, req.repo_name, req.issue_number)
    return RunResponse(run_id=run_id)


@app.get("/api/run/{run_id}")
async def get_status(run_id: str):
    runner = _runs.get(run_id)
    if not runner:
        raise HTTPException(status_code=404, detail="Run not found")
    return runner.status()


@app.get("/api/run/{run_id}/result")
async def get_result(run_id: str):
    runner = _runs.get(run_id)
    if not runner:
        raise HTTPException(status_code=404, detail="Run not found")
    # Return 200 with a "pending" flag instead of 202 so axios doesn't throw
    if not runner.is_done():
        return {"pending": True}
    return runner.result()


@app.get("/health")
async def health():
    return {"status": "ok"}
