from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research" / "autonomous_improvement_loop.py"


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


def test_stage6b_script_exists() -> None:
    assert SCRIPT.exists()


def test_stage6b_help_exits_zero() -> None:
    proc = run_script("--help")
    assert proc.returncode == 0
    assert "Stage 6b safe autonomous improvement-loop scaffold" in proc.stdout


def test_stage6b_one_cycle_smoke_writes_audit_without_repo_changes(tmp_path: Path) -> None:
    audit_path = tmp_path / "stage6b_audit.jsonl"

    proc = run_script(
        "--cycles",
        "1",
        "--suite",
        "smoke",
        "--audit-path",
        str(audit_path),
    )

    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)

    assert data["ok"] is True
    assert data["stage"] == "6b"
    assert data["cycles_completed"] == 1
    assert data["auto_applied"] is False
    assert data["human_approval_required"] is True
    assert data["changed_files"] == []
    assert data["command_exit_codes"] == [0]

    lines = audit_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["event"] == "improvement_cycle"
    assert json.loads(lines[1])["event"] == "improvement_loop_summary"


def test_stage6b_rejects_cycle_limit_violation(tmp_path: Path) -> None:
    audit_path = tmp_path / "stage6b_audit.jsonl"

    proc = run_script(
        "--cycles",
        "4",
        "--audit-path",
        str(audit_path),
    )

    assert proc.returncode == 2
    data = json.loads(proc.stderr)
    assert data["ok"] is False
    assert data["max_cycles"] == 3
    assert not audit_path.exists()


def test_stage6b_internal_allowlist_blocks_unknown_command() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("autonomous_improvement_loop", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    assert module.is_allowed_command([sys.executable, "-c", "print('stage6b-smoke-ok')"])
    assert module.is_allowed_command([sys.executable, "-B", "-m", "pytest", "-p", "no:cacheprovider", "-q"])
    assert not module.is_allowed_command(["powershell", "-Command", "Remove-Item -Recurse ."])
    assert not module.is_allowed_command([sys.executable, "-c", "import os; print(os.environ)"])

