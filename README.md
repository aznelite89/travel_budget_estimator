## Travel Budget Estimator

CrewAI-powered travel budget estimator with:

- `backend/`: FastAPI API (async jobs)
- `frontend/`: Vite React UI (JSX)

### Common `uv` commands for local setup

Run these from the repo root on a new machine:

```bash
# create / reuse a uv-managed virtualenv for this project
uv init

# install all Python dependencies from pyproject.toml
uv sync

# run backend locally (FastAPI)
uv run uvicorn backend.app.main:app --reload --port 8000

# run the CLI-based estimator
uv run python -m travel_budget_estimator.cli --help
```

### Run backend (FastAPI)

From repo root:

```bash
uv run uvicorn backend.app.main:app --reload --port 8000
```

Health check: `http://localhost:8000/health`

Backend requires a Postgres database configured via `DATABASE_URL`, for example:

```bash
export DATABASE_URL='postgresql+psycopg://chanthaithong@localhost:5432/travel_budget'
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

### Amadeus flight pricing (test environment)

Flight estimates can be grounded on real prices from the Amadeus Self-Service APIs.

- Set the following environment variables (for example in `travel_crew/.env`):
  - `AMADEUS_API_KEY` – your Amadeus API key
  - `AMADEUS_API_SECRET` – your Amadeus API secret
  - `AMADEUS_ENV` – `test` (default) or `production`
- The backend uses the **test** environment (`https://test.api.amadeus.com`) by default and can be
  switched to production by setting `AMADEUS_ENV=production`.

### CLI example (CrewAI `travel_crew`)

From the repo root:

```bash
uv run python -m travel_budget_estimator.cli \
  --trip-title "Travel: Tokyo Spring" \
  --origin "Kuala Lumpur" \
  --destination "Tokyo" \
  --start-date 2026-04-10 \
  --end-date 2026-04-18 \
  --travelers 2 \
  --currency MYR \
  --budget-style midrange \
  --out outputs/tokyo_budget.json
```
