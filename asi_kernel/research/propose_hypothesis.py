from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = ROOT / "logs" / "research" / "hypotheses.jsonl"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", default="smoke")
    args = parser.parse_args()

    if args.suite != "smoke":
        raise SystemExit("Only --suite smoke is supported in Stage 5a scaffold")

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "hypothesis_id": f"hyp-{uuid4().hex[:12]}",
        "timestamp": utc_now(),
        "suite": args.suite,
        "claim": "The identity solver should score 1.0 on the smoke identity benchmark.",
        "rationale": "The smoke task output is identical to its input, so identity prediction should match expected output.",
        "risk_level": "low",
        "requires_human_approval": False,
        "status": "proposed"
    }

    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, separators=(",", ":")) + "\n")

    print(json.dumps(record, indent=2))
    print(f"Wrote {LOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
