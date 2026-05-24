from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = ROOT / "logs" / "research" / "experiments.jsonl"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_command(args: list[str]) -> dict:
    result = subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return {
        "command": args,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", default="smoke")
    args = parser.parse_args()

    if args.suite != "smoke":
        raise SystemExit("Only --suite smoke is supported in Stage 5a scaffold")

    experiment_id = f"exp-{uuid4().hex[:12]}"

    run_result = run_command([
        sys.executable,
        "benchmarks/arc_agi_2/run_solver.py",
        "--suite",
        args.suite,
    ])

    score_result = run_command([
        sys.executable,
        "benchmarks/arc_agi_2/score.py",
        "--latest",
    ])

    ok = run_result["returncode"] == 0 and score_result["returncode"] == 0

    record = {
        "experiment_id": experiment_id,
        "timestamp": utc_now(),
        "suite": args.suite,
        "hypothesis": "The identity solver should score 1.0 on the smoke identity benchmark.",
        "bounded": True,
        "changed_files": [],
        "runner": run_result,
        "scorer": score_result,
        "status": "passed" if ok else "failed",
    }

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, separators=(",", ":")) + "\n")

    print(json.dumps({
        "experiment_id": experiment_id,
        "status": record["status"],
        "runner_returncode": run_result["returncode"],
        "scorer_returncode": score_result["returncode"],
    }, indent=2))
    print(f"Wrote {LOG_PATH}")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
