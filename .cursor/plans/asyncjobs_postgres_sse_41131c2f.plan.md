---
name: AsyncJobs_Postgres_SSE
overview: Add Postgres-backed async job persistence, best-effort cancellation, and SSE progress streaming to the existing FastAPI+Vite app.
todos:
  - id: add-pg-deps
    content: Add SQLAlchemy + psycopg deps and DB config via DATABASE_URL
    status: completed
  - id: db-models
    content: Create Postgres models for jobs and events (JSONB payload/result) and init tables
    status: completed
  - id: persist-jobs
    content: Refactor FastAPI endpoints to use DB-backed job store
    status: completed
  - id: cancel-endpoint
    content: Add best-effort cancel endpoint and ensure worker respects cancelled status
    status: completed
  - id: sse-endpoint
    content: Add SSE endpoint streaming job events with Last-Event-ID support
    status: completed
  - id: frontend-sse-cancel
    content: Update React UI to subscribe to SSE, show progress panel, and provide Cancel button
    status: completed
  - id: docs-changelog
    content: Update README, gitignore for env examples, and append CHANGELOG entry
    status: completed
  - id: smoke-test
    content: Run quick local checks for create/persist/cancel/SSE
    status: completed
isProject: false
---

## Scope

- Replace in-memory job store with Postgres persistence.
- Add best-effort job cancellation.
- Add SSE endpoint to stream job status/progress events.
- Update the Vite UI to show live progress, a Cancel button, and stop polling when SSE is connected.

## Backend design (FastAPI)

- **Database**: Postgres via `DATABASE_URL` (you said you already have Postgres running).
- **Tables**:
  - `estimate_jobs`: one row per job, stores payload + result (JSONB), status, timestamps, error.
  - `estimate_job_events`: append-only progress events used by SSE.
- **Statuses**: `queued | running | done | error | cancelled`.
- **Cancellation** (best-effort): `POST /api/estimate-jobs/{job_id}/cancel` sets status to `cancelled` immediately; the worker checks status before writing final result and will not overwrite a cancelled job.
- **SSE**: `GET /api/estimate-jobs/{job_id}/events` streams new `estimate_job_events` rows (with `Last-Event-ID` support). Frontend subscribes with `EventSource`.

### Endpoints

- `POST /api/estimate-jobs` (unchanged request): create job row + first event; start background task.
- `GET /api/estimate-jobs/{job_id}`: read job row.
- `POST /api/estimate-jobs/{job_id}/cancel`: cancel.
- `GET /api/estimate-jobs/{job_id}/events`: SSE of events.

## Frontend design (Vite React)

- Add a **progress/log panel** fed by SSE events.
- Add **Cancel** button shown when job is `queued/running`.
- Keep the existing polling as a fallback if SSE disconnects, but prefer SSE.

## Files to add / update

- Add `[backend/app/db.py](/Users/chanthaithong/Desktop/own/travel_budget_estimator/backend/app/db.py)`: engine/session helpers (SQLAlchemy 2.x).
- Add `[backend/app/models.py](/Users/chanthaithong/Desktop/own/travel_budget_estimator/backend/app/models.py)`: ORM models for jobs + events.
- Add `[backend/app/repo.py](/Users/chanthaithong/Desktop/own/travel_budget_estimator/backend/app/repo.py)`: CRUD helpers (create job, append event, update status/result, cancel).
- Update `[backend/app/main.py](/Users/chanthaithong/Desktop/own/travel_budget_estimator/backend/app/main.py)`: swap in DB-backed logic, add cancel + SSE endpoints, write events during job lifecycle.
- Update `[frontend/src/App.jsx](/Users/chanthaithong/Desktop/own/travel_budget_estimator/frontend/src/App.jsx)`: EventSource subscription + UI for progress + Cancel.
- Update `[README.md](/Users/chanthaithong/Desktop/own/travel_budget_estimator/README.md)`: add `DATABASE_URL` instructions + new endpoints.
- Update `[.gitignore](/Users/chanthaithong/Desktop/own/travel_budget_estimator/.gitignore)`: unignore `*.env.example` so examples can be committed.
- Update `[CHANGELOG.md](/Users/chanthaithong/Desktop/own/travel_budget_estimator/CHANGELOG.md)`: add a new entry for cancellation + persistence + SSE.

## Dependencies (Python)

Will add:

- `sqlalchemy`
- `psycopg[binary]`

(No new JS deps; SSE uses built-in `EventSource`.)

## Minimal verification

- Start backend with `DATABASE_URL` set; hit `/health`.
- Create a job; confirm it persists (restart backend and `GET` still works).
- Subscribe to SSE; confirm events arrive and UI updates.
- Cancel a running job; confirm status becomes `cancelled` and UI stops.
