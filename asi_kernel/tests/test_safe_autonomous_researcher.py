from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from safety.policy import PolicyError, command_is_allowed, load_policy, validate_command, validate_cycles  # noqa: E402


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


def test_stage6_policy_loads_and_blocks_unsafe_fragments() -> None:
    policy = load_policy()

    assert policy["network_allowed"] is False
    assert policy["secrets_allowed"] is False
    assert policy["destructive_actions_allowed"] is False
    assert policy["auto_apply_patches"] is False

    allowed = ["research/propose_hypothesis.py", "--suite", "smoke"]
    blocked = ["research/propose_hypothesis.py", "--suite", "smoke", ".env"]

    assert command_is_allowed(allowed, policy) is True
    assert command_is_allowed(blocked, policy) is False

    validate_command(allowed, policy)

    with pytest.raises(PolicyError):
        validate_command(blocked, policy)


def test_stage6_policy_enforces_cycle_hard_limit() -> None:
    policy = load_policy()

    validate_cycles(1, policy)
    validate_cycles(policy["max_cycles_hard_limit"], policy)

    with pytest.raises(PolicyError):
        validate_cycles(policy["max_cycles_hard_limit"] + 1, policy)

    with pytest.raises(PolicyError):
        validate_cycles(0, policy)


def test_stage6_autonomous_loop_dry_run_writes_audit_log() -> None:
    result = run_py("research/autonomous_loop.py", "--cycles", "1", "--dry-run")

    assert result.returncode == 0, result.stderr
    assert '"event": "autonomous_research_finished"' in result.stdout
    assert '"auto_apply_patches": false' in result.stdout.lower()

    audit_log = ROOT / "logs" / "safety" / "autonomous_research_audit.jsonl"
    records = read_jsonl(audit_log)

    assert records
    assert records[-1]["event"] == "autonomous_research_finished"
    assert records[-1]["changed_files"] == []
    assert records[-1]["requires_human_approval_for_changes"] is True


def test_stage6_autonomous_loop_executes_one_safe_cycle() -> None:
    result = run_py("research/autonomous_loop.py", "--cycles", "1")

    assert result.returncode == 0, result.stderr
    assert '"status": "passed"' in result.stdout

    audit_log = ROOT / "logs" / "safety" / "autonomous_research_audit.jsonl"
    records = read_jsonl(audit_log)

    assert records[-1]["event"] == "autonomous_research_finished"
    assert records[-1]["status"] == "passed"
    assert records[-1]["changed_files"] == []
    assert records[-1]["auto_apply_patches"] is False
