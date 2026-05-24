from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research" / "patch_proposal_loop.py"
FULL_PYTEST_COMMAND = r".venv\Scripts\python.exe -B -m pytest -p no:cacheprovider -q"

IGNORED_SNAPSHOT_PARTS = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    "logs",
}


def run_script(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(ROOT),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        check=False,
    )


def production_snapshot() -> dict[str, tuple[int, int]]:
    snapshot: dict[str, tuple[int, int]] = {}
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        if any(part in IGNORED_SNAPSHOT_PARTS for part in rel.parts):
            continue
        stat = path.stat()
        snapshot[str(rel).replace("\\", "/")] = (stat.st_size, stat.st_mtime_ns)
    return snapshot


def test_stage6c_script_exists() -> None:
    assert SCRIPT.exists()


def test_stage6c_one_cycle_writes_reviewable_patch_without_production_changes(tmp_path: Path) -> None:
    audit_path = tmp_path / "patch_proposal_runs.jsonl"
    proposal_dir = tmp_path / "patch_proposals"
    before = production_snapshot()

    proc = run_script(
        "--cycles",
        "1",
        "--suite",
        "smoke",
        "--audit-path",
        str(audit_path),
        "--proposal-dir",
        str(proposal_dir),
    )

    after = production_snapshot()

    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)

    assert data["ok"] is True
    assert data["stage"] == "6c"
    assert data["cycles_completed"] == 1
    assert data["risk_classification"] in {"low", "medium", "high"}
    assert data["risk_reasons"]
    assert data["tests_selected"]
    assert data["human_approval_required"] is True
    assert data["auto_applied"] is False
    assert data["changed_files"] == []
    assert data["decision"] == "recommend_review"

    proposal_path = Path(data["proposal_path"])
    patch_path = Path(data["patch_path"])
    assert proposal_path.exists()
    assert patch_path.exists()
    assert proposal_path.parent == proposal_dir
    assert patch_path.parent == proposal_dir

    proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
    assert proposal["human_approval_required"] is True
    assert proposal["auto_applied"] is False
    assert proposal["changed_files"] == []
    assert proposal["tests_selected"]

    patch_text = patch_path.read_text(encoding="utf-8")
    assert "--- " in patch_text
    assert "+++ " in patch_text
    assert "@@ " in patch_text
    assert "verification/safe_autonomy_boundary.md" in patch_text

    audit_records = [
        json.loads(line)
        for line in audit_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert audit_records
    assert audit_records[-1]["stage"] == "6c"
    assert audit_records[-1]["event"] == "patch_proposal_summary"
    assert audit_records[-1]["summary"]["auto_applied"] is False
    assert audit_records[-1]["summary"]["human_approval_required"] is True

    assert after == before


def test_stage6c_rejects_cycle_limit_violation(tmp_path: Path) -> None:
    proc = run_script(
        "--cycles",
        "4",
        "--audit-path",
        str(tmp_path / "audit.jsonl"),
        "--proposal-dir",
        str(tmp_path / "proposals"),
    )

    assert proc.returncode == 2
    data = json.loads(proc.stderr)
    assert data["ok"] is False
    assert data["max_cycles"] == 3


def test_stage6c_risk_classifier_is_deterministic() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("patch_proposal_loop", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    low = module.classify_risk(["verification/safe_autonomy_boundary.md"], patch_text="+review gate\n")
    medium = module.classify_risk(["research/patch_proposal_loop.py"], patch_text="+value = 1\n")
    high_network = module.classify_risk(["research/patch_proposal_loop.py"], patch_text="+import requests\n")
    high_unknown = module.classify_risk(["unknown/path.txt"], patch_text="+x\n")

    assert low["risk_classification"] == "low"
    assert medium["risk_classification"] == "medium"
    assert high_network["risk_classification"] == "high"
    assert high_unknown["risk_classification"] == "high"


def test_stage6c_dashboard_summarizes_latest_patch_proposal_run(tmp_path: Path) -> None:
    from dashboards import progress_report

    audit_path = tmp_path / "logs" / "research" / "patch_proposal_runs.jsonl"
    audit_path.parent.mkdir(parents=True)
    audit_path.write_text(
        json.dumps(
            {
                "stage": "6c",
                "event": "patch_proposal_summary",
                "timestamp_unix": 1.0,
                "summary": {
                    "stage": "6c",
                    "ok": True,
                    "cycles_completed": 1,
                    "proposal_path": str(tmp_path / "logs" / "research" / "patch_proposals" / "stage6c.json"),
                    "patch_path": str(tmp_path / "logs" / "research" / "patch_proposals" / "stage6c.patch"),
                    "risk_classification": "low",
                    "risk_reasons": ["docs-only"],
                    "tests_selected": [FULL_PYTEST_COMMAND],
                    "human_approval_required": True,
                    "auto_applied": False,
                    "changed_files": [],
                    "decision": "recommend_review",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    summary = progress_report.summarize_patch_proposal_runs(tmp_path)

    assert summary["exists"] is True
    assert summary["ok"] is True
    assert summary["stage"] == "6c"
    assert summary["risk_classification"] == "low"
    assert summary["human_approval_required"] is True
    assert summary["auto_applied"] is False
    assert summary["changed_files"] == []
