from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_LOG_DIR = ROOT / "logs" / "benchmarks"
EVAL_LOG_DIR = ROOT / "logs" / "evals"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def latest_benchmark_log() -> Path:
    logs = sorted(BENCHMARK_LOG_DIR.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    if not logs:
        raise SystemExit(f"No benchmark logs found in {BENCHMARK_LOG_DIR}")
    return logs[-1]


def score_file(path: Path) -> dict:
    total = 0
    correct = 0
    failed = []

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue

            record = json.loads(line)
            total += 1
            ok = record.get("predictions") == record.get("expected")
            correct += int(ok)

            if not ok:
                failed.append(record.get("task_id", "unknown"))

    score = correct / total if total else 0.0

    return {
        "timestamp": utc_now(),
        "benchmark_log": str(path),
        "total": total,
        "correct": correct,
        "score": score,
        "failed_task_ids": failed,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--latest", action="store_true")
    parser.add_argument("--file")
    args = parser.parse_args()

    if args.latest:
        path = latest_benchmark_log()
    elif args.file:
        path = Path(args.file)
    else:
        raise SystemExit("Use --latest or --file PATH")

    result = score_file(path)

    EVAL_LOG_DIR.mkdir(parents=True, exist_ok=True)
    out_path = EVAL_LOG_DIR / "arc_agi_2_scores.jsonl"
    with out_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(result, separators=(",", ":")) + "\n")

    print(json.dumps(result, indent=2))
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
