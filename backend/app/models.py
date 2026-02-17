from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from sqlalchemy import JSON, DateTime, Index, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


JobStatus = Literal["queued", "running", "done", "error", "cancelled"]


class Base(DeclarativeBase):
  pass


class EstimateJob(Base):
  __tablename__ = "estimate_jobs"

  id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
  job_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)

  # request payload
  trip_title: Mapped[str] = mapped_column(String(255))
  origin: Mapped[str] = mapped_column(String(255))
  destination: Mapped[str] = mapped_column(String(255))
  start_date: Mapped[str] = mapped_column(String(32))
  end_date: Mapped[str] = mapped_column(String(32))
  travelers: Mapped[int]
  currency: Mapped[str] = mapped_column(String(16))
  budget_style: Mapped[str] = mapped_column(String(32))

  status: Mapped[str] = mapped_column(String(16), index=True)
  created_at: Mapped[datetime]
  started_at: Mapped[Optional[datetime]]
  finished_at: Mapped[Optional[datetime]]

  error: Mapped[Optional[str]] = mapped_column(Text)
  result: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)

  __table_args__ = (
    Index("ix_estimate_jobs_status_created_at", "status", "created_at"),
  )


class EstimateJobEvent(Base):
  __tablename__ = "estimate_job_events"

  id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
  job_id: Mapped[str] = mapped_column(String(64), index=True)
  created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
  type: Mapped[str] = mapped_column(String(32))
  message: Mapped[str] = mapped_column(Text)
  data: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

  __table_args__ = (
    Index("ix_estimate_job_events_job_created", "job_id", "created_at"),
  )

