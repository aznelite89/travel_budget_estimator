# Changelog

## 2026-02-18

### Added

- extract_json helper: strip markdown code fences, brace-matching for one top-level JSON object, fallback regex; coerce_json_dict now uses it for robust parsing of crew output
- Retry once on JSON parse failure in run_budget_estimate with WARNING log of raw output
- output_pydantic=TravelBudgetEstimateV1 on final_report_task; prefer last task structured output after kickoff before falling back to coerce_json_dict
- Global exception handler in backend returning JSON (detail, code) for uncaught exceptions so frontend never receives non-JSON error bodies

### Fixed

- Restore load_yaml definition in crew.py (was accidentally removed during JSON guardrails refactor)

## 2026-02-18

### Added

- CrewAI tracing enabled on travel budget Crew (traces visible at app.crewai.com)

### Changed

- Travel budget Crew uses Process.hierarchical with custom manager agent (budget_crew_manager) for delegation and validation; worker agents unchanged

### Fixed

- Budget validation: coerce types in schema (budget_style lowercase, travelers int, numerics float), normalize crew output (estimate keys, line_items, totals.per_person_base, contingency/validation defaults), surface first 5 validation error details in job error message

## 2026-02-18

### Fixed

- Trip plan and final report tasks: require crew to use provided origin/destination (no TBD placeholders)
- Force final budget meta fields to match user inputs and relax schema validation to ignore extra fields from crew output

## 2026-02-18

### Fixed

- Normalize crew output meta structure to match TravelBudgetEstimateV1 schema (map trip_dates/duration/party_size to flat fields)
- Ensure all required meta fields (trip_title, origin, destination, start_date, end_date, travelers, currency, budget_style) are present
- Normalize assumptions field when crew outputs a list instead of an object
- Improve validation error messages in backend job handler

## 2026-02-17

### Fixed

- Handle CrewAI CrewOutput in travel budget estimate pipeline

## 2026-02-17

### Added

- FastAPI backend with async estimate job API
- Vite React frontend to submit/poll jobs and render results
- Postgres-backed persistent job store with cancellation and SSE progress streaming
