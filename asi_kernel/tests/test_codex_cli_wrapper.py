from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import time
from pathlib import Path

import pytest


ROOT = Path("D:/Sandbox/asi_kernel")
WRAPPER_PATH = ROOT / "tools" / "codex_cli" / "run_codex_exec.py"
PREFLIGHT_PATH = ROOT / "tools" / "codex_cli" / "check_codex_cli.ps1"
AUDIT_LOG = ROOT / "logs" / "codex_cli_runs.jsonl"
OUTPUT_DIR = ROOT / "logs" / "codex_cli_outputs"


def load_wrapper():
    spec = importlib.util.spec_from_file_location("run_codex_exec", WRAPPER_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def base_task(**overrides):
    task = {
        "task_id": f"pytest_dry_run_{time.time_ns()}",
        "prompt": "Inspect README.md only. Do not edit files.",
        "workspace": str(ROOT),
        "expected_outputs": ["logs/codex_cli_outputs/pytest_dry_run.md"],
        "validation_commands": ["python tools\\codex_cli\\run_codex_exec.py --help"],
        "max_duration_sec": 5,
        "max_recursion_depth": 0,
        "risk_level": "low",
    }
    task.update(overrides)
    return task


def test_rejects_workspace_outside_root():
    wrapper = load_wrapper()

    result = wrapper.run_task(base_task(workspace="D:\\Sandbox"), dry_run=True)

    assert result["exit_code"] == 2
    assert result["status"] == "rejected"
    assert "outside allowed root" in result["stderr"]


def test_rejects_forbidden_flags():
    wrapper = load_wrapper()

    result = wrapper.run_task(
        base_task(prompt="Inspect this repo with --yolo enabled."),
        dry_run=True,
    )

    assert result["exit_code"] == 2
    assert result["status"] == "rejected"
    assert "--yolo" in result["stderr"]


def test_rejects_high_risk_tasks():
    wrapper = load_wrapper()

    result = wrapper.run_task(
        base_task(risk_level="high", prompt="Delete files after inspection."),
        dry_run=True,
    )

    assert result["exit_code"] == 2
    assert result["status"] == "rejected"
    assert "risk_level" in result["stderr"]


def test_accepts_low_risk_dry_run_task():
    wrapper = load_wrapper()

    result = wrapper.run_task(base_task(), dry_run=True)

    assert result["exit_code"] == 0
    assert result["status"] == "dry_run"
    assert result["stderr"] == ""
    assert "--sandbox" in result["command"]
    assert "workspace-write" in result["command"]
    assert "--ask-for-approval" in result["command"]
    assert "on-request" in result["command"]


def test_audit_log_jsonl_is_written():
    wrapper = load_wrapper()
    task = base_task(task_id=f"pytest_audit_{time.time_ns()}")

    result = wrapper.run_task(task, dry_run=True)

    assert result["exit_code"] == 0
    assert AUDIT_LOG.exists()
    records = [
        json.loads(line)
        for line in AUDIT_LOG.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert any(record["task_id"] == task["task_id"] for record in records)


def test_output_path_stays_under_codex_cli_outputs():
    wrapper = load_wrapper()

    result = wrapper.run_task(base_task(task_id="pytest_output_path"), dry_run=True)
    output_path = Path(result["output_file"])

    assert output_path.is_relative_to(OUTPUT_DIR)
    assert output_path.name == "pytest_output_path.md"


def test_preflight_file_can_be_generated():
    shell = shutil.which("powershell") or shutil.which("pwsh")
    if shell is None:
        pytest.skip("PowerShell is not available")

    if shell.lower().endswith("powershell.exe") or shell.lower().endswith("powershell"):
        command = [
            shell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(PREFLIGHT_PATH),
        ]
    else:
        command = [shell, "-NoProfile", "-File", str(PREFLIGHT_PATH)]

    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=30)

    assert result.returncode == 0
    preflight_log = ROOT / "logs" / "codex_cli_preflight.json"
    assert preflight_log.exists()
    data = json.loads(preflight_log.read_text(encoding="utf-8-sig"))
    assert data["expected_root"] == str(ROOT)
    assert data["current_path_ok"] is True
    assert "codex_version" in data["checks"]
    if not data["checks"]["codex_command"]["available"]:
        assert "npm install -g @openai/codex@latest" in result.stdout
