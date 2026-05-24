from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def failed_validation_commands(evaluation: dict[str, Any]) -> list[str]:
    commands: list[str] = []
    for result in evaluation.get("validation_results", []):
        if int(result.get("exit_code", 1)) != 0:
            commands.append(str(result.get("command", "")))
    return commands


def classify_failure(run_record: dict[str, Any], evaluation: dict[str, Any] | None = None) -> dict[str, Any]:
    evaluation = evaluation or {}
    status = str(run_record.get("status", "")).lower()
    exit_code = int(run_record.get("exit_code", 1))
    stderr = str(run_record.get("stderr", "")).lower()
    reasons = [str(reason) for reason in evaluation.get("failure_reasons", [])]
    failed_commands = failed_validation_commands(evaluation)

    if status == "rejected" or exit_code == 2:
        failure_class = "unsafe_task_rejected"
    elif status == "timeout" or exit_code == 124:
        failure_class = "timeout"
    elif exit_code == 127 or "codex cli not found" in stderr or "not recognized" in stderr:
        failure_class = "codex_cli_missing"
    elif failed_commands:
        failure_class = "validation_failed"
    elif any("expected output missing" in reason for reason in reasons):
        failure_class = "output_missing"
    elif any("outside" in reason for reason in reasons):
        failure_class = "path_policy_violation"
    elif exit_code != 0 or status in {"failed", "validation_failed"}:
        failure_class = "delegation_failed"
    else:
        failure_class = "unknown_failure"

    return {
        "classified_at": utc_now(),
        "task_id": run_record.get("task_id"),
        "failure_class": failure_class,
        "run_status": run_record.get("status"),
        "exit_code": exit_code,
        "failure_reasons": reasons,
        "failed_validation_commands": failed_commands,
    }


def load_json_arg(value: str) -> dict[str, Any]:
    stripped = value.strip()
    if stripped.startswith("{"):
        return json.loads(stripped)
    return json.loads(Path(value).read_text(encoding="utf-8-sig"))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Classify a failed Codex CLI delegation result.")
    parser.add_argument("--run-record", required=True, help="Run record JSON path or inline JSON")
    parser.add_argument("--evaluation", help="Evaluation JSON path or inline JSON")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    run_record = load_json_arg(args.run_record)
    evaluation = load_json_arg(args.evaluation) if args.evaluation else {}
    print(json.dumps(classify_failure(run_record, evaluation), indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
