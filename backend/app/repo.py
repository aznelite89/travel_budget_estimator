from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_session
from .models import EstimateJob, EstimateJobEvent, JobStatus


def utcnow() -> datetime:
  return datetime.now(UTC)


def create_job(payload: dict[str, Any], job_id: str) -> dict[str, Any]:
  with get_session() as session:
    job = EstimateJob(
      job_id=job_id,
      trip_title=payload["trip_title"],
      origin=payload["origin"],
      destination=payload["destination"],
      start_date=payload["start_date"],
      end_date=payload["end_date"],
      travelers=int(payload["travelers"]),
      currency=payload["currency"],
      budget_style=payload["budget_style"],
      status="queued",
      created_at=utcnow(),
      started_at=None,
      finished_at=None,
      error=None,
      result=None,
    )
    session.add(job)
    session.flush()

    _append_event_in_session(
      session,
      job_id=job_id,
      type="status",
      message="Job queued",
      data={"status": "queued"},
    )

    return job_to_dict(job)


def get_job(job_id: str) -> Optional[dict[str, Any]]:
  with get_session() as session:
    stmt = select(EstimateJob).where(EstimateJob.job_id == job_id)
    job = session.scalar(stmt)
    if not job:
      return None
    return job_to_dict(job)


def update_job_status(
  job_id: str,
  *,
  status: JobStatus,
  error: Optional[str] = None,
  result: Optional[dict[str, Any]] = None,
  set_started: bool = False,
  set_finished: bool = False,
) -> Optional[dict[str, Any]]:
  with get_session() as session:
    stmt = select(EstimateJob).where(EstimateJob.job_id == job_id).with_for_update()
    job = session.scalar(stmt)
    if not job:
      return None

    # Do not overwrite a cancelled job with a completed result
    if job.status == "cancelled" and status in ("done", "error"):
      return job_to_dict(job)

    job.status = status
    now = utcnow()
    if set_started and job.started_at is None:
      job.started_at = now
    if set_finished:
      job.finished_at = now
    if error is not None:
      job.error = error
    if result is not None:
      job.result = result

    message = f"Status changed to {status}"
    if error:
      message = f"Error: {error}"

    _append_event_in_session(
      session,
      job_id=job_id,
      type="status",
      message=message,
      data={"status": status},
    )

    return job_to_dict(job)


def cancel_job(job_id: str) -> Optional[dict[str, Any]]:
  return update_job_status(job_id, status="cancelled", set_finished=True)


def append_event(job_id: str, type: str, message: str, data: Optional[dict[str, Any]] = None) -> None:
  with get_session() as session:
    _append_event_in_session(session, job_id=job_id, type=type, message=message, data=data)


def _append_event_in_session(
  session: Session,
  *,
  job_id: str,
  type: str,
  message: str,
  data: Optional[dict[str, Any]] = None,
) -> None:
  event = EstimateJobEvent(
    job_id=job_id,
    created_at=utcnow(),
    type=type,
    message=message,
    data=data,
  )
  session.add(event)


def get_events_since(job_id: str, last_id: Optional[int] = None) -> Iterable[EstimateJobEvent]:
  with get_session() as session:
    stmt = select(EstimateJobEvent).where(EstimateJobEvent.job_id == job_id)
    if last_id is not None:
      stmt = stmt.where(EstimateJobEvent.id > last_id)
    stmt = stmt.order_by(EstimateJobEvent.id.asc())
    return list(session.scalars(stmt))


def job_to_dict(job: EstimateJob) -> dict[str, Any]:
  return {
    "job_id": job.job_id,
    "status": job.status,
    "created_at": job.created_at.isoformat(),
    "started_at": job.started_at.isoformat() if job.started_at else None,
    "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    "error": job.error,
    "result": job.result,
  }

