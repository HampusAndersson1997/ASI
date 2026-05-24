from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
AUDIT_LOG = ROOT / "logs" / "safety" / "autonomous_research_audit.jsonl"

# Allow direct script execution without requiring package installation.
sys.path.insert(0, str(ROOT))

from safety.policy import assert_safe_policy, load_policy, validate_command, validate_cycles  # noqa: E402


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_audit(record: dict) -> None:
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, separators=(",", ":")) + "\n")


def run_allowed_python_script(script_and_args: list[str], policy: dict) -> dict:
    validate_command(script_and_args, policy)

    command = [sys.executable, *script_and_args]
    started = utc_now()

    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=int(policy["timeout_seconds"]),
        check=False,
    )

    return {
        "timestamp": started,
        "command": script_and_args,
        "returncode": result.returncode,
        "stdout_tail": result.stdout[-2000:],
        "stderr_tail": result.stderr[-2000:],
    }


def run_cycle(cycle_index: int, policy: dict) -> dict:
    steps = [
        ["research/propose_hypothesis.py", "--suite", "smoke"],
        ["research/run_experiment.py", "--suite", "smoke"],
        ["research/compare_results.py", "--latest"],
    ]

    step_results = []
    status = "passed"

    for step in steps:
        result = run_allowed_python_script(step, policy)
        step_results.append(result)

        if result["returncode"] != 0:
            status = "failed"
            break

    return {
        "cycle_index": cycle_index,
        "status": status,
        "steps": step_results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cycles", type=int, default=1)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    policy = load_policy()
    assert_safe_policy(policy)
    validate_cycles(args.cycles, policy)

    run_id = f"safe-auto-{uuid4().hex[:12]}"

    header = {
        "run_id": run_id,
        "timestamp": utc_now(),
        "event": "autonomous_research_started",
        "cycles_requested": args.cycles,
        "dry_run": args.dry_run,
        "policy": {
            "network_allowed": policy["network_allowed"],
            "secrets_allowed": policy["secrets_allowed"],
            "destructive_actions_allowed": policy["destructive_actions_allowed"],
            "auto_apply_patches": policy["auto_apply_patches"],
            "human_approval_required_for_changes": policy["human_approval_required_for_changes"],
            "timeout_seconds": policy["timeout_seconds"],
        },
    }
    append_audit(header)

    cycle_records = []

    if args.dry_run:
        for i in range(args.cycles):
            cycle_records.append({
                "cycle_index": i,
                "status": "dry_run",
                "steps": policy["allowed_commands"],
                "changed_files": [],
            })
    else:
        for i in range(args.cycles):
            cycle_records.append(run_cycle(i, policy))

    final_status = "passed"
    if any(cycle["status"] == "failed" for cycle in cycle_records):
        final_status = "failed"

    footer = {
        "run_id": run_id,
        "timestamp": utc_now(),
        "event": "autonomous_research_finished",
        "status": final_status,
        "cycles": cycle_records,
        "changed_files": [],
        "auto_apply_patches": False,
        "requires_human_approval_for_changes": True,
    }
    append_audit(footer)

    print(json.dumps(footer, indent=2))
    print(f"Wrote {AUDIT_LOG}")

    return 0 if final_status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
