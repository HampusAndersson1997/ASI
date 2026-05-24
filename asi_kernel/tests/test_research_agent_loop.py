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


def read_jsonl(path: Path) -> list[dict]:
    assert path.exists(), f"Missing expected log: {path}"
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_research_hypothesis_cli_writes_log() -> None:
    result = run_py("research/propose_hypothesis.py", "--suite", "smoke")

    assert result.returncode == 0, result.stderr
    assert "hypothesis_id" in result.stdout

    records = read_jsonl(ROOT / "logs" / "research" / "hypotheses.jsonl")
    assert records
    assert records[-1]["suite"] == "smoke"
    assert records[-1]["status"] == "proposed"


def test_research_experiment_cli_runs_benchmark_and_scores() -> None:
    result = run_py("research/run_experiment.py", "--suite", "smoke")

    assert result.returncode == 0, result.stderr
    assert '"status": "passed"' in result.stdout

    records = read_jsonl(ROOT / "logs" / "research" / "experiments.jsonl")
    assert records
    assert records[-1]["suite"] == "smoke"
    assert records[-1]["bounded"] is True
    assert records[-1]["changed_files"] == []
    assert records[-1]["status"] == "passed"


def test_research_compare_cli_writes_decision() -> None:
    run_result = run_py("research/run_experiment.py", "--suite", "smoke")
    assert run_result.returncode == 0, run_result.stderr

    compare_result = run_py("research/compare_results.py", "--latest")
    assert compare_result.returncode == 0, compare_result.stderr
    assert '"decision": "keep"' in compare_result.stdout

    records = read_jsonl(ROOT / "logs" / "research" / "comparisons.jsonl")
    assert records
    assert records[-1]["comparison_type"] == "baseline_vs_latest"
    assert records[-1]["candidate_score"] >= records[-1]["baseline_score"]
    assert records[-1]["decision"] == "keep"
