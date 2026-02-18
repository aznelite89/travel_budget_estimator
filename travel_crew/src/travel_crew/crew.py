from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

import yaml
from crewai import Agent, Task, Crew, Process
from pydantic import ValidationError

from .schemas import TravelBudgetEstimateV1

from dotenv import load_dotenv
load_dotenv()

CONFIG_DIR = Path(__file__).resolve().parent / "config"
# Fallback for backward compatibility when brace-matching finds nothing
JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def load_yaml(path: Path) -> Dict[str, Any]:
  with path.open("r", encoding="utf-8") as f:
    return yaml.safe_load(f)


def _strip_code_fences(text: str) -> str:
  """Remove optional markdown code fences (e.g. ```json ... ```) from the string."""
  s = text.strip()
  if s.startswith("```"):
    # Find first newline after opening fence
    first_nl = s.find("\n")
    if first_nl != -1:
      s = s[first_nl + 1:]
    # Find closing fence
    close = s.find("```")
    if close != -1:
      s = s[:close]
  return s.strip()


def _extract_brace_object(text: str) -> str | None:
  """Extract the first complete top-level {...} object using brace-matching."""
  start = text.find("{")
  if start == -1:
    return None
  depth = 0
  in_string = False
  escape = False
  quote_char = None
  i = start
  while i < len(text):
    c = text[i]
    if escape:
      escape = False
      i += 1
      continue
    if c == "\\" and in_string:
      escape = True
      i += 1
      continue
    if in_string:
      if c == quote_char:
        in_string = False
      i += 1
      continue
    if c in ('"', "'"):
      in_string = True
      quote_char = c
      i += 1
      continue
    if c == "{":
      depth += 1
    elif c == "}":
      depth -= 1
      if depth == 0:
        return text[start : i + 1]
    i += 1
  return None


def extract_json(text: str) -> Dict[str, Any]:
  """
  Extract a single JSON object from text that may contain markdown fences or
  surrounding commentary. Uses fence stripping and brace-matching for robustness.
  """
  text = _strip_code_fences(text)
  if not text:
    raise ValueError("No content to parse after stripping code fences.")

  # Try direct parse first
  try:
    obj = json.loads(text)
    if isinstance(obj, dict):
      return obj
    raise ValueError("Parsed JSON is not an object.")
  except json.JSONDecodeError:
    pass

  # Extract first balanced {...} object
  candidate = _extract_brace_object(text)
  if candidate:
    try:
      obj = json.loads(candidate)
      if isinstance(obj, dict):
        return obj
    except json.JSONDecodeError:
      pass

  # Fallback: greedy regex (backward compatibility)
  m = JSON_OBJECT_RE.search(text)
  if m:
    try:
      obj = json.loads(m.group(0))
      if isinstance(obj, dict):
        return obj
    except json.JSONDecodeError:
      pass

  raise ValueError("Could not parse valid JSON object from crew output.")


def coerce_json_dict(result: Any) -> Dict[str, Any]:
  # Normalise known CrewAI result container types to raw string/dict.
  # Newer versions of CrewAI return a `CrewOutput` object from `kickoff()`,
  # which exposes the underlying text on `.raw`. We duck-type here so we
  # don't need to import the concrete class.
  if not isinstance(result, (dict, str)):
    if hasattr(result, "raw"):
      result = result.raw  # type: ignore[assignment]
    elif hasattr(result, "output"):
      # Fallback for any future attribute naming; treat like `.raw`.
      result = getattr(result, "output")  # type: ignore[assignment]
    else:
      raise TypeError(f"Unexpected crew result type: {type(result)}")

  if isinstance(result, dict):
    return result

  return extract_json(result.strip())


# Schema expects these exact estimate keys; map common LLM variants.
ESTIMATES_KEY_MAP = {
  "flight": "flights",
  "accommodation": "stay",
  "accommodations": "stay",
  "lodging": "stay",
  "local_transport": "transport",
  "transportation": "transport",
  "doc_fees": "docs_fees",
  "documentation": "docs_fees",
  "docs_and_fees": "docs_fees",
  "documents_fees": "docs_fees",
}


def _normalize_line_item(item: Any) -> Dict[str, Any]:
  if isinstance(item, dict):
    name = item.get("name") or item.get("item") or item.get("label") or str(item.get("amount", ""))
    amount = item.get("amount")
    if amount is None:
      amount = item.get("value") or item.get("cost") or 0
    return {"name": str(name).strip() or "Item", "amount": float(amount)}
  return {"name": "Item", "amount": 0.0}


def _normalize_estimates_and_totals(data: Dict[str, Any]) -> None:
  """Ensure estimates use schema keys and category shape; ensure totals.per_person_base exists."""
  estimates = data.get("estimates")
  if not isinstance(estimates, dict):
    return

  schema_keys = ("flights", "stay", "transport", "food", "activities", "docs_fees")
  normalized: Dict[str, Any] = {}
  for key, val in estimates.items():
    if not isinstance(val, dict):
      continue
    k = key.lower().replace(" ", "_").replace("-", "_")
    canonical = ESTIMATES_KEY_MAP.get(k, k)
    if canonical in schema_keys:
      normalized[canonical] = val

  for cat_key in ("flights", "stay", "transport", "food", "activities", "docs_fees"):
    if cat_key not in normalized:
      normalized[cat_key] = {
        "low": 0.0,
        "base": 0.0,
        "high": 0.0,
        "line_items": [],
        "assumptions": [],
        "confidence": 0.5,
      }
    cat = normalized[cat_key]
    if not isinstance(cat.get("line_items"), list):
      cat["line_items"] = []
    cat["line_items"] = [_normalize_line_item(i) for i in cat["line_items"]]
    if not isinstance(cat.get("assumptions"), list):
      cat["assumptions"] = [str(cat.get("assumptions", ""))] if cat.get("assumptions") else []
    cat["assumptions"] = [str(a).strip() for a in cat["assumptions"] if str(a).strip()]
    if "confidence" not in cat or cat["confidence"] is None:
      cat["confidence"] = 0.5
  data["estimates"] = normalized

  totals = data.get("totals")
  meta = data.get("meta") or {}
  travelers = meta.get("travelers") or 1
  if isinstance(totals, dict):
    if "per_person_base" not in totals and "base" in totals:
      try:
        base = float(totals["base"])
        data["totals"]["per_person_base"] = base / max(1, int(travelers))
      except (TypeError, ValueError):
        data["totals"]["per_person_base"] = 0.0
    for k in ("low", "base", "high"):
      if k in totals and totals[k] is not None and not isinstance(totals[k], (int, float)):
        try:
          data["totals"][k] = float(totals[k])
        except (TypeError, ValueError):
          pass

  contingency = data.get("contingency")
  if isinstance(contingency, dict):
    base_totals = data.get("totals") or {}
    base_val = base_totals.get("base")
    try:
      base_float = float(base_val) if base_val is not None else 0.0
    except (TypeError, ValueError):
      base_float = 0.0
    for k, default in (
      ("buffer_rate_used", 0.1),
      ("base_subtotal", base_float),
      ("buffer_amount", 0.0),
      ("total_with_buffer", base_float),
    ):
      if k not in contingency or contingency[k] is None:
        contingency[k] = default

  validation = data.get("validation")
  if isinstance(validation, dict):
    if "validated" not in validation or validation["validated"] is None:
      validation["validated"] = True
    if "confidence" not in validation or validation["confidence"] is None:
      validation["confidence"] = 0.8
    if not isinstance(validation.get("issues"), list):
      validation["issues"] = []
    if not isinstance(validation.get("recommendations"), list):
      validation["recommendations"] = []


@dataclass
class RunInputs:
  trip_title: str
  origin: str
  destination: str
  start_date: str
  end_date: str
  travelers: int
  currency: str = "MYR"
  budget_style: str = "midrange"  # budget | midrange | luxury


def build_agents(agents_cfg: Dict[str, Any], shared_cfg: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Agent]:
  defaults = shared_cfg.get("defaults", {})
  llm_model = defaults.get("llm_model", "gpt-4o-mini")
  temperature = float(defaults.get("temperature", 0.2))
  max_iter = int(defaults.get("max_iter", 3))
  verbose = bool(defaults.get("verbose", False))

  agents: Dict[str, Agent] = {}
  for agent_name, spec in agents_cfg.items():
    agents[agent_name] = Agent(
      role=spec["role"].format(**inputs),
      goal=spec["goal"].format(**inputs),
      backstory=spec["backstory"].format(**inputs),
      llm=llm_model,
      temperature=temperature,
      max_iter=max_iter,
      verbose=verbose,
    )
  return agents


def build_tasks(tasks_cfg: Dict[str, Any], agents: Dict[str, Agent], shared_cfg: Dict[str, Any], inputs: Dict[str, Any]) -> Dict[str, Task]:
  merged = dict(inputs)
  merged.update(shared_cfg.get("assumptions", {}))
  merged.update({
    "buffers": shared_cfg.get("buffers", {}),
    "rounding": shared_cfg.get("currency", {}).get("rounding", {}),
  })

  tasks: Dict[str, Task] = {}

  # pass 1: create
  for task_name, spec in tasks_cfg.items():
    agent_key = spec["agent"]
    task_kw: Dict[str, Any] = {
      "description": spec["description"].format(**merged),
      "expected_output": spec["expected_output"].format(**merged),
      "agent": agents[agent_key],
    }
    if task_name == "final_report_task":
      task_kw["output_pydantic"] = TravelBudgetEstimateV1
    tasks[task_name] = Task(**task_kw)

  # pass 2: context wiring
  for task_name, spec in tasks_cfg.items():
    ctx = spec.get("context") or []
    if ctx:
      tasks[task_name].context = [tasks[c] for c in ctx]

  return tasks


def run_budget_estimate(run: RunInputs, validate: bool = True) -> Dict[str, Any]:
  shared_cfg = load_yaml(CONFIG_DIR / "config.yaml")
  agents_cfg = load_yaml(CONFIG_DIR / "agents.yaml")
  tasks_cfg = load_yaml(CONFIG_DIR / "tasks.yaml")

  inputs = {
    "trip_title": run.trip_title,
    "origin": run.origin,
    "destination": run.destination,
    "start_date": run.start_date,
    "end_date": run.end_date,
    "travelers": int(run.travelers),
    "currency": run.currency,
    "budget_style": run.budget_style,
    "days": 0,
    "nights": 0,
  }

  agents = build_agents(agents_cfg, shared_cfg, inputs)
  tasks = build_tasks(tasks_cfg, agents, shared_cfg, inputs)

  MANAGER_AGENT_KEY = "budget_crew_manager"
  worker_agents = [a for k, a in agents.items() if k != MANAGER_AGENT_KEY]
  manager_agent = agents[MANAGER_AGENT_KEY]

  crew = Crew(
    agents=worker_agents,
    tasks=[
      tasks["trip_plan_task"],
      tasks["flight_estimate_task"],
      tasks["stay_estimate_task"],
      tasks["transport_estimate_task"],
      tasks["food_estimate_task"],
      tasks["activity_estimate_task"],
      tasks["docs_fees_estimate_task"],
      tasks["risk_buffer_task"],
      tasks["budget_aggregation_task"],
      tasks["validation_task"],
      tasks["final_report_task"],
    ],
    process=Process.hierarchical,
    manager_agent=manager_agent,
    verbose=shared_cfg.get("defaults", {}).get("verbose", True),
    tracing=True,
  )

  def _result_to_data(result: Any) -> Dict[str, Any]:
    # Prefer structured output from final task when output_pydantic is set
    if hasattr(result, "tasks") and result.tasks:
      last_task = result.tasks[-1]
      out = getattr(last_task, "output", None)
      if out is not None and hasattr(out, "model_dump"):
        return out.model_dump()
      if isinstance(out, dict):
        return out
    return coerce_json_dict(result)

  last_error = None
  data = None
  for attempt in range(2):
    result = crew.kickoff()
    try:
      data = _result_to_data(result)
      break
    except (ValueError, json.JSONDecodeError) as e:
      last_error = e
      raw = getattr(result, "raw", getattr(result, "output", result))
      if isinstance(raw, str) and len(raw) > 2000:
        raw_preview = raw[:2000] + "..."
      else:
        raw_preview = raw
      logger.warning(
        "Failed to parse crew output (attempt %s): %s. Raw output: %s",
        attempt + 1,
        e,
        raw_preview,
      )
      if attempt == 1:
        raise last_error

  # Normalize meta structure to match TravelBudgetEstimateV1 schema
  meta = data.get("meta")
  if isinstance(meta, dict):
    # Map nested trip_dates structure to flat fields
    trip_dates = meta.get("trip_dates")
    if isinstance(trip_dates, dict):
      if "start" in trip_dates and "start_date" not in meta:
        meta["start_date"] = trip_dates["start"]
      if "end" in trip_dates and "end_date" not in meta:
        meta["end_date"] = trip_dates["end"]
      meta.pop("trip_dates", None)

    # Map duration structure if present
    duration = meta.get("duration")
    if isinstance(duration, dict):
      if "days" in duration and "days" not in meta:
        meta["days"] = duration["days"]
      if "nights" in duration and "nights" not in meta:
        meta["nights"] = duration["nights"]
      meta.pop("duration", None)

    # Map party_size to travelers
    if "party_size" in meta and "travelers" not in meta:
      meta["travelers"] = meta["party_size"]
      meta.pop("party_size", None)

    # Ensure all required fields are present and match the original user inputs.
    # We intentionally overwrite any model-generated values here so the final
    # response always reflects what the user entered in the UI.
    meta["trip_title"] = run.trip_title
    meta["origin"] = run.origin
    meta["destination"] = run.destination
    meta["start_date"] = run.start_date
    meta["end_date"] = run.end_date
    meta["travelers"] = int(run.travelers)
    meta["currency"] = run.currency
    meta["budget_style"] = run.budget_style
  else:
    # If meta is missing or not a dict, create it from RunInputs
    data["meta"] = {
      "trip_title": run.trip_title,
      "origin": run.origin,
      "destination": run.destination,
      "start_date": run.start_date,
      "end_date": run.end_date,
      "travelers": int(run.travelers),
      "currency": run.currency,
      "budget_style": run.budget_style,
    }

  # Normalize assumptions: schema expects an object, but model may output a list
  assumptions = data.get("assumptions")
  if isinstance(assumptions, list):
    data["assumptions"] = {"notes": [str(item) for item in assumptions if str(item).strip()]}
  elif not isinstance(assumptions, dict):
    data["assumptions"] = {"notes": []}
  else:
    notes = assumptions.get("notes")
    if not isinstance(notes, list):
      data["assumptions"] = {**assumptions, "notes": [] if notes is None else [str(notes)]}

  _normalize_estimates_and_totals(data)

  if validate:
    model = TravelBudgetEstimateV1.model_validate(data)  # raises ValidationError
    return model.model_dump()

  return data
