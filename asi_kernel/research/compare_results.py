from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVAL_LOG = ROOT / "logs" / "evals" / "arc_agi_2_scores.jsonl"
COMPARISON_LOG = ROOT / "logs" / "research" / "comparisons.jsonl"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_latest_eval() -> dict:
    if not EVAL_LOG.exists():
        raise SystemExit(f"Missing eval log: {EVAL_LOG}")

    records = [
        json.loads(line)
        for line in EVAL_LOG.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    if not records:
        raise SystemExit(f"No eval records found in {EVAL_LOG}")

    return records[-1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--latest", action="store_true")
    parser.add_argument("--baseline-score", type=float, default=1.0)
    args = parser.parse_args()

    if not args.latest:
        raise SystemExit("Use --latest")

    latest = read_latest_eval()
    candidate_score = float(latest.get("score", 0.0))
    delta = candidate_score - args.baseline_score

    decision = "keep" if delta >= 0 else "reject"

    record = {
        "timestamp": utc_now(),
        "comparison_type": "baseline_vs_latest",
        "baseline_score": args.baseline_score,
        "candidate_score": candidate_score,
        "delta": delta,
        "decision": decision,
        "evidence": latest,
        "notes": "Stage 5a scaffold comparison; no code patch is applied automatically.",
    }

    COMPARISON_LOG.parent.mkdir(parents=True, exist_ok=True)
    with COMPARISON_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, separators=(",", ":")) + "\n")

    print(json.dumps(record, indent=2))
    print(f"Wrote {COMPARISON_LOG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
