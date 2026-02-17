## Travel Budget Estimator

CrewAI-powered travel budget estimator with:
- `backend/`: FastAPI API (async jobs)
- `frontend/`: Vite React UI (JSX)

### Run backend (FastAPI)

From repo root:

```bash
uv run uvicorn backend.app.main:app --reload --port 8000
```

Health check: `http://localhost:8000/health`

Backend requires a Postgres database configured via `DATABASE_URL`, for example:

```bash
export DATABASE_URL='postgresql+psycopg://user:password@localhost:5432/travel_budget'
```

### Run frontend (Vite React)

```bash
cd frontend
pnpm install
pnpm dev
```

Optional: configure API base URL by copying `frontend/.env.example` to `frontend/.env` and editing `VITE_API_BASE_URL`.

### API overview

- `POST /api/estimate-jobs` – create a new estimate job (async)
- `GET /api/estimate-jobs/{job_id}` – get current job status + result (when ready)
- `POST /api/estimate-jobs/{job_id}/cancel` – best-effort cancel
- `GET /api/estimate-jobs/{job_id}/events` – SSE stream of job events/progress

