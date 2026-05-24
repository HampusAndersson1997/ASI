from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_py(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def test_arc_agi_2_smoke_runner_writes_jsonl() -> None:
    result = run_py("benchmarks/arc_agi_2/run_solver.py", "--suite", "smoke")

    assert result.returncode == 0, result.stderr
    assert "Wrote" in result.stdout

    logs = sorted((ROOT / "logs" / "benchmarks").glob("arc-smoke-*.jsonl"))
    assert logs

    latest = logs[-1]
    records = [json.loads(line) for line in latest.read_text(encoding="utf-8").splitlines() if line.strip()]

    assert records
    assert records[0]["suite"] == "smoke"
    assert records[0]["solver"] == "identity"
    assert records[0]["predictions"] == records[0]["expected"]


def test_arc_agi_2_score_latest_writes_eval_log() -> None:
    run_result = run_py("benchmarks/arc_agi_2/run_solver.py", "--suite", "smoke")
    assert run_result.returncode == 0, run_result.stderr

    score_result = run_py("benchmarks/arc_agi_2/score.py", "--latest")
    assert score_result.returncode == 0, score_result.stderr
    assert '"score": 1.0' in score_result.stdout

    eval_log = ROOT / "logs" / "evals" / "arc_agi_2_scores.jsonl"
    assert eval_log.exists()

    lines = [json.loads(line) for line in eval_log.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert lines
    assert lines[-1]["score"] == 1.0
    assert lines[-1]["total"] >= 1
