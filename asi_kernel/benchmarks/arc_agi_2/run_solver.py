from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[2]
TASK_DIR = ROOT / "benchmarks" / "arc_agi_2" / "smoke_tasks"
LOG_DIR = ROOT / "logs" / "benchmarks"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_tasks(suite: str) -> list[dict]:
    if suite != "smoke":
        raise SystemExit(f"Unsupported suite: {suite!r}. Only 'smoke' exists.")

    tasks = []
    for path in sorted(TASK_DIR.glob("*.json")):
        with path.open("r", encoding="utf-8") as f:
            task = json.load(f)
        task["_path"] = str(path)
        tasks.append(task)

    if not tasks:
        raise SystemExit(f"No smoke tasks found in {TASK_DIR}")

    return tasks


def solve_identity(task: dict) -> list[dict]:
    predictions = []
    for item in task.get("test", []):
        predictions.append({"output": item["input"]})
    return predictions


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", default="smoke")
    parser.add_argument("--solver", default="identity")
    args = parser.parse_args()

    run_id = f"arc-smoke-{uuid4().hex[:12]}"
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    out_path = LOG_DIR / f"{run_id}.jsonl"

    tasks = load_tasks(args.suite)

    with out_path.open("w", encoding="utf-8") as f:
        for task in tasks:
            if args.solver != "identity":
                raise SystemExit(f"Unsupported solver: {args.solver!r}")

            record = {
                "run_id": run_id,
                "timestamp": utc_now(),
                "suite": args.suite,
                "solver": args.solver,
                "task_id": task["id"],
                "task_path": task["_path"],
                "predictions": solve_identity(task),
                "expected": [{"output": item["output"]} for item in task.get("test", [])],
            }
            f.write(json.dumps(record, separators=(",", ":")) + "\n")

    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
