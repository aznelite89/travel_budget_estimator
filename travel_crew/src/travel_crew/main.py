from __future__ import annotations

import argparse
import json
from pathlib import Path

from .crew import RunInputs, run_budget_estimate


def main() -> None:
  p = argparse.ArgumentParser(description="Travel Budget Estimator (CrewAI) - JSON output")
  p.add_argument("--trip-title", required=True)
  p.add_argument("--origin", required=True)
  p.add_argument("--destination", required=True)
  p.add_argument("--start-date", required=True, help="YYYY-MM-DD")
  p.add_argument("--end-date", required=True, help="YYYY-MM-DD")
  p.add_argument("--travelers", type=int, required=True)
  p.add_argument("--currency", default="MYR")
  p.add_argument("--budget-style", default="midrange", choices=["budget", "midrange", "luxury"])
  p.add_argument("--out", default="outputs/budget.json", help="output file path")
  p.add_argument("--no-validate", action="store_true", help="skip pydantic validation")

  args = p.parse_args()

  out_path = Path(args.out)
  out_path.parent.mkdir(parents=True, exist_ok=True)

  data = run_budget_estimate(
    RunInputs(
      trip_title=args.trip_title,
      origin=args.origin,
      destination=args.destination,
      start_date=args.start_date,
      end_date=args.end_date,
      travelers=args.travelers,
      currency=args.currency,
      budget_style=args.budget_style,
    ),
    validate=(not args.no_validate),
  )

  out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
  print(str(out_path))


if __name__ == "__main__":
  main()
