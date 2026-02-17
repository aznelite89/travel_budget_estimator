from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import yaml
from crewai import Agent, Task, Crew, Process
from pydantic import ValidationError

from .schemas import TravelBudgetEstimateV1


CONFIG_DIR = Path(__file__).resolve().parent / "config"
JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def load_yaml(path: Path) -> Dict[str, Any]:
  with path.open("r", encoding="utf-8") as f:
    return yaml.safe_load(f)


def coerce_json_dict(result: Any) -> Dict[str, Any]:
  if isinstance(result, dict):
    return result

  if not isinstance(result, str):
    raise TypeError(f"Unexpected crew result type: {type(result)}")

  text = result.strip()

  # 1) direct JSON
  try:
    obj = json.loads(text)
    if isinstance(obj, dict):
      return obj
  except Exception:
    pass

  # 2) extract first JSON object if model leaked text
  m = JSON_OBJECT_RE.search(text)
  if m:
    candidate = m.group(0)
    obj = json.loads(candidate)
    if isinstance(obj, dict):
      return obj

  raise ValueError("Could not parse valid JSON object from crew output.")


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
    tasks[task_name] = Task(
      description=spec["description"].format(**merged),
      expected_output=spec["expected_output"].format(**merged),
      agent=agents[agent_key],
    )

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

  crew = Crew(
    agents=list(agents.values()),
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
    ],
    process=Process.sequential,
    verbose=shared_cfg.get("defaults", {}).get("verbose", True),
  )

  result = crew.kickoff()
  data = coerce_json_dict(result)

  if validate:
    model = TravelBudgetEstimateV1.model_validate(data)  # raises ValidationError
    return model.model_dump()

  return data
