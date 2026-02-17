from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Literal, Optional
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .db import engine
from .models import Base, JobStatus
from .repo import (
  append_event,
  cancel_job,
  create_job,
  get_events_since,
  get_job,
  update_job_status,
)

ROOT_DIR = Path(__file__).resolve().parents[2]

# Load env for CrewAI (keys live in travel_crew/.env in this repo)
DOTENV_PATH = ROOT_DIR / "travel_crew" / ".env"
if DOTENV_PATH.exists():
  load_dotenv(DOTENV_PATH)
else:
  load_dotenv()

# Allow importing travel_crew without needing an install step
TRAVEL_CREW_SRC = ROOT_DIR / "travel_crew" / "src"
if str(TRAVEL_CREW_SRC) not in sys.path:
  sys.path.insert(0, str(TRAVEL_CREW_SRC))

from travel_crew.crew import RunInputs, run_budget_estimate  # noqa: E402


class EstimateJobCreateRequest(BaseModel):
  trip_title: str = Field(..., min_length=1)
  origin: str = Field(..., min_length=1)
  destination: str = Field(..., min_length=1)
  start_date: str = Field(..., min_length=1, description="YYYY-MM-DD")
  end_date: str = Field(..., min_length=1, description="YYYY-MM-DD")
  travelers: int = Field(..., ge=1)
  currency: str = Field(default="MYR", min_length=1)
  budget_style: Literal["budget", "midrange", "luxury"] = Field(default="midrange")


class EstimateJobResponse(BaseModel):
  job_id: str
  status: JobStatus
  created_at: str
  started_at: Optional[str] = None
  finished_at: Optional[str] = None
  error: Optional[str] = None
  result: Optional[Dict[str, Any]] = None


async def _run_job(job_id: str, payload: EstimateJobCreateRequest) -> None:
  await asyncio.to_thread(
    update_job_status,
    job_id,
    status="running",
    set_started=True,
  )
  try:
    inputs = RunInputs(
      trip_title=payload.trip_title,
      origin=payload.origin,
      destination=payload.destination,
      start_date=payload.start_date,
      end_date=payload.end_date,
      travelers=payload.travelers,
      currency=payload.currency,
      budget_style=payload.budget_style,
    )
    result = await asyncio.to_thread(run_budget_estimate, inputs, True)

    # Persist result if job wasn't cancelled
    await asyncio.to_thread(
      update_job_status,
      job_id,
      status="done",
      result=result,
      set_finished=True,
    )
    await asyncio.to_thread(
      append_event,
      job_id,
      "progress",
      "Job completed",
      {"status": "done"},
    )
  except Exception as e:
    await asyncio.to_thread(
      update_job_status,
      job_id,
      status="error",
      error=f"{type(e).__name__}: {e}",
      set_finished=True,
    )


# Create tables on startup if they don't exist yet
Base.metadata.create_all(bind=engine)


app = FastAPI(title="Travel Budget Estimator API", version="0.1.0")

app.add_middleware(
  CORSMiddleware,
  allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)


@app.get("/health")
def health() -> Dict[str, str]:
  return {"status": "ok"}


@app.post("/api/estimate-jobs", response_model=EstimateJobResponse)
async def create_estimate_job(payload: EstimateJobCreateRequest) -> EstimateJobResponse:
  job_id = str(uuid4())
  job = await asyncio.to_thread(
    create_job,
    {
      "trip_title": payload.trip_title,
      "origin": payload.origin,
      "destination": payload.destination,
      "start_date": payload.start_date,
      "end_date": payload.end_date,
      "travelers": payload.travelers,
      "currency": payload.currency,
      "budget_style": payload.budget_style,
    },
    job_id,
  )

  asyncio.create_task(_run_job(job_id, payload))
  return EstimateJobResponse(**job)


@app.get("/api/estimate-jobs/{job_id}", response_model=EstimateJobResponse)
async def get_estimate_job(job_id: str) -> EstimateJobResponse:
  job = await asyncio.to_thread(get_job, job_id)
  if not job:
    raise HTTPException(status_code=404, detail="Job not found")
  return EstimateJobResponse(**job)


@app.post("/api/estimate-jobs/{job_id}/cancel", response_model=EstimateJobResponse)
async def cancel_estimate_job(job_id: str) -> EstimateJobResponse:
  job = await asyncio.to_thread(cancel_job, job_id)
  if not job:
    raise HTTPException(status_code=404, detail="Job not found")
  await asyncio.to_thread(
    append_event,
    job_id,
    "status",
    "Job cancelled",
    {"status": "cancelled"},
  )
  return EstimateJobResponse(**job)


@app.get("/api/estimate-jobs/{job_id}/events")
async def stream_estimate_job_events(request: Request, job_id: str):
  # Basic existence check
  job = await asyncio.to_thread(get_job, job_id)
  if not job:
    raise HTTPException(status_code=404, detail="Job not found")

  last_event_id_header = request.headers.get("Last-Event-ID")
  try:
    last_id: Optional[int] = int(last_event_id_header) if last_event_id_header else None
  except ValueError:
    last_id = None

  async def event_generator():
    nonlocal last_id
    while True:
      if await request.is_disconnected():
        break

      events = await asyncio.to_thread(get_events_since, job_id, last_id)
      for ev in events:
        last_id = ev.id
        payload = {
          "type": ev.type,
          "message": ev.message,
          "created_at": ev.created_at.isoformat(),
          "data": ev.data,
        }
        yield f"id: {ev.id}\n"
        yield f"event: {ev.type}\n"
        yield f"data: {payload}\n\n"

      await asyncio.sleep(1.0)

  return StreamingResponse(event_generator(), media_type="text/event-stream")

