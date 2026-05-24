from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path("D:/Sandbox/asi_kernel").resolve(strict=False)
LOG_DIR = ROOT / "logs"
OUTPUT_DIR = LOG_DIR / "codex_cli_outputs"
AUDIT_LOG = LOG_DIR / "codex_cli_runs.jsonl"
TOOLS_PYTHON_DIR = ROOT / "tools" / "python"
TOOLS_MEMORY_DIR = ROOT / "tools" / "memory"

for import_dir in (TOOLS_PYTHON_DIR, TOOLS_MEMORY_DIR):
    import_text = str(import_dir)
    if import_text not in sys.path:
        sys.path.insert(0, import_text)

import score_result
import save_agent_run

ALLOWED_RISK_LEVELS = {"low", "medium"}
FORBIDDEN_RISK_LEVELS = {"high", "destructive", "secret-exfiltration"}
FORBIDDEN_FLAGS = (
    "--yolo",
    "--dangerously-bypass-approvals-and-sandbox",
    "--sandbox danger-full-access",
)
HIGH_RISK_PATTERNS = (
    "exfiltrate",
    "secret",
    "credential",
    "api key",
    "token",
    "password",
    "delete files",
    "wipe",
    "format",
    "rm -rf",
    "remove-item -recurse",
    "git reset --hard",
    "deploy to production",
    "improve everything",
    "danger-full-access",
    "bypass approvals",
)
ABSOLUTE_WINDOWS_PATH_RE = re.compile(r"[A-Za-z]:\\[^\s\"'<>|]+")
SAFE_TASK_ID_RE = re.compile(r"[^A-Za-z0-9_.-]+")


class ValidationError(Exception):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def norm_text(value: Path | str) -> str:
    return os.path.normcase(str(value))


def is_under(path: Path, root: Path) -> bool:
    path_text = norm_text(path.resolve(strict=False))
    root_text = norm_text(root.resolve(strict=False))
    return path_text == root_text or path_text.startswith(root_text + os.sep)


def safe_task_id(task_id: str) -> str:
    cleaned = SAFE_TASK_ID_RE.sub("_", task_id).strip("._")
    if not cleaned:
        raise ValidationError("task_id must contain at least one safe character")
    return cleaned[:120]


def hash_prompt(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def append_audit(record: dict[str, Any]) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"logged_at": utc_now(), **record}
    with AUDIT_LOG.open("a", encoding="utf-8") as audit_file:
        audit_file.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def task_strings(task: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for value in task.values():
        if isinstance(value, str):
            values.append(value)
        elif isinstance(value, list):
            values.extend(item for item in value if isinstance(item, str))
    return values


def validate_forbidden_flags(task: dict[str, Any]) -> None:
    combined = " ".join(task_strings(task))
    normalized = re.sub(r"\s+", " ", combined).lower()
    for flag in FORBIDDEN_FLAGS:
        if flag in normalized:
            raise ValidationError(f"forbidden Codex flag rejected: {flag}")


def validate_required_fields(task: dict[str, Any]) -> None:
    required = {
        "task_id",
        "prompt",
        "workspace",
        "expected_outputs",
        "validation_commands",
        "max_duration_sec",
        "max_recursion_depth",
        "risk_level",
    }
    missing = sorted(required - set(task))
    if missing:
        raise ValidationError(f"missing required fields: {', '.join(missing)}")


def validate_types(task: dict[str, Any]) -> None:
    if not isinstance(task["task_id"], str) or not task["task_id"].strip():
        raise ValidationError("task_id must be a non-empty string")
    if not isinstance(task["prompt"], str) or not task["prompt"].strip():
        raise ValidationError("prompt must be a non-empty string")
    if not isinstance(task["workspace"], str) or not task["workspace"].strip():
        raise ValidationError("workspace must be a non-empty string")
    if not isinstance(task["expected_outputs"], list):
        raise ValidationError("expected_outputs must be a list")
    if not all(isinstance(item, str) for item in task["expected_outputs"]):
        raise ValidationError("expected_outputs must contain only strings")
    if not isinstance(task["validation_commands"], list):
        raise ValidationError("validation_commands must be a list")
    if not all(isinstance(item, str) for item in task["validation_commands"]):
        raise ValidationError("validation_commands must contain only strings")
    if not isinstance(task["max_duration_sec"], int):
        raise ValidationError("max_duration_sec must be an integer")
    if not isinstance(task["max_recursion_depth"], int):
        raise ValidationError("max_recursion_depth must be an integer")
    if not isinstance(task["risk_level"], str):
        raise ValidationError("risk_level must be a string")


def validate_risk(task: dict[str, Any]) -> None:
    risk_level = task["risk_level"].lower()
    if risk_level in FORBIDDEN_RISK_LEVELS or risk_level not in ALLOWED_RISK_LEVELS:
        raise ValidationError(
            "risk_level must be low or medium; high, destructive, and "
            "secret-exfiltration are rejected"
        )

    normalized = " ".join(task_strings(task)).lower()
    for pattern in HIGH_RISK_PATTERNS:
        if pattern in normalized:
            raise ValidationError(f"high-risk task content rejected: {pattern}")


def resolve_task_path(path_text: str) -> Path:
    candidate = Path(path_text)
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    return candidate.resolve(strict=False)


def validate_paths(task: dict[str, Any]) -> None:
    workspace = Path(task["workspace"]).resolve(strict=False)
    if norm_text(workspace) != norm_text(ROOT):
        raise ValidationError(f"workspace outside allowed root rejected: {workspace}")

    for output in task["expected_outputs"]:
        output_path = resolve_task_path(output)
        if not is_under(output_path, ROOT):
            raise ValidationError(f"expected output outside allowed root rejected: {output}")

    for value in task_strings(task):
        for match in ABSOLUTE_WINDOWS_PATH_RE.findall(value):
            candidate = Path(match).resolve(strict=False)
            if not is_under(candidate, ROOT):
                raise ValidationError(f"filesystem path outside allowed root rejected: {match}")


def validate_duration_and_depth(task: dict[str, Any]) -> None:
    if task["max_duration_sec"] < 1 or task["max_duration_sec"] > 3600:
        raise ValidationError("max_duration_sec must be between 1 and 3600")
    if task["max_recursion_depth"] < 0 or task["max_recursion_depth"] > 3:
        raise ValidationError("max_recursion_depth must be between 0 and 3")


def validate_task(task: dict[str, Any]) -> None:
    if not isinstance(task, dict):
        raise ValidationError("task must be a JSON object")
    validate_required_fields(task)
    validate_types(task)
    validate_duration_and_depth(task)
    validate_risk(task)
    validate_forbidden_flags(task)
    validate_paths(task)


def output_path_for(task_id: str) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = (OUTPUT_DIR / f"{safe_task_id(task_id)}.md").resolve(strict=False)
    if not is_under(path, OUTPUT_DIR):
        raise ValidationError("output file path escaped codex_cli_outputs")
    return path


def build_codex_command(task: dict[str, Any], output_file: Path) -> list[str]:
    return [
        "codex",
        "--ask-for-approval",
        "on-request",
        "exec",
        "--cd",
        str(ROOT),
        "--sandbox",
        "workspace-write",
        "--output-last-message",
        str(output_file),
        task["prompt"],
    ]


def powershell_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def codex_execution_command(command: list[str]) -> list[str]:
    script = "& " + " ".join(powershell_quote(str(part)) for part in command)
    return score_result.shell_command(script)


def result_record(
    *,
    task: dict[str, Any],
    status: str,
    command: list[str],
    output_file: Path,
    stdout: str,
    stderr: str,
    exit_code: int,
    duration_sec: float,
    validation_errors: list[str] | None = None,
    evaluation: dict[str, Any] | None = None,
    memory_record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    record = {
        "task_id": task.get("task_id", "unknown"),
        "status": status,
        "workspace": task.get("workspace"),
        "risk_level": task.get("risk_level"),
        "command": command,
        "stdout": stdout,
        "stderr": stderr,
        "exit_code": exit_code,
        "duration_sec": round(duration_sec, 3),
        "output_file": str(output_file),
        "expected_outputs": task.get("expected_outputs", []),
        "validation_commands": task.get("validation_commands", []),
        "prompt_sha256": hash_prompt(str(task.get("prompt", ""))),
        "prompt_preview": str(task.get("prompt", ""))[:240],
        "validation_errors": validation_errors or [],
    }
    if evaluation is not None:
        record["evaluation"] = evaluation
    if memory_record is not None:
        record["memory_record"] = memory_record
    return record


def rejected_record(task: dict[str, Any], error: str, started_at: float) -> dict[str, Any]:
    task_id = str(task.get("task_id", "rejected"))
    try:
        output_file = output_path_for(task_id)
    except ValidationError:
        output_file = OUTPUT_DIR / "rejected.md"
    return result_record(
        task=task,
        status="rejected",
        command=[],
        output_file=output_file,
        stdout="",
        stderr=error,
        exit_code=2,
        duration_sec=time.monotonic() - started_at,
        validation_errors=[error],
    )


def finalize_delegation_record(
    task: dict[str, Any],
    record: dict[str, Any],
    *,
    executor: Any = None,
) -> dict[str, Any]:
    record["delegation_status"] = record["status"]
    record["delegation_exit_code"] = record["exit_code"]
    evaluation = score_result.score_result(task, record, executor=executor, root=ROOT)

    if evaluation["passed"]:
        record["status"] = "passed"
        record["exit_code"] = 0
    elif record["delegation_status"] == "completed" and record["delegation_exit_code"] == 0:
        record["status"] = "validation_failed"
        record["exit_code"] = score_result.first_failed_validation_exit_code(
            evaluation.get("validation_results", [])
        )

    record["evaluation"] = evaluation
    memory_result = save_agent_run.save_agent_result(task, record, evaluation, root=ROOT)
    record["memory_record"] = {
        "record_type": memory_result["record_type"],
        "path": memory_result["path"],
        "record_id": memory_result["record_id"],
    }
    return record


def run_task(task: dict[str, Any], *, dry_run: bool = False, executor: Any = None) -> dict[str, Any]:
    started_at = time.monotonic()
    runner = executor or subprocess.run
    try:
        validate_task(task)
        output_file = output_path_for(task["task_id"])
        command = build_codex_command(task, output_file)
        execution_command = codex_execution_command(command)

        if dry_run:
            record = result_record(
                task=task,
                status="dry_run",
                command=command,
                output_file=output_file,
                stdout="DRY RUN: codex CLI was not executed.",
                stderr="",
                exit_code=0,
                duration_sec=time.monotonic() - started_at,
            )
            record["execution_argv"] = execution_command
            append_audit(record)
            return record

        try:
            completed = runner(
                execution_command,
                cwd=ROOT,
                text=True,
                capture_output=True,
                timeout=task["max_duration_sec"],
            )
            record = result_record(
                task=task,
                status="completed" if completed.returncode == 0 else "failed",
                command=command,
                output_file=output_file,
                stdout=completed.stdout,
                stderr=completed.stderr,
                exit_code=completed.returncode,
                duration_sec=time.monotonic() - started_at,
            )
            record["execution_argv"] = execution_command
        except FileNotFoundError as exc:
            record = result_record(
                task=task,
                status="failed",
                command=command,
                output_file=output_file,
                stdout="",
                stderr=f"Codex CLI not found: {exc}",
                exit_code=127,
                duration_sec=time.monotonic() - started_at,
            )
            record["execution_argv"] = execution_command
        except PermissionError as exc:
            record = result_record(
                task=task,
                status="failed",
                command=command,
                output_file=output_file,
                stdout="",
                stderr=f"Codex CLI could not be executed: {exc}",
                exit_code=126,
                duration_sec=time.monotonic() - started_at,
            )
            record["execution_argv"] = execution_command
        except subprocess.TimeoutExpired as exc:
            record = result_record(
                task=task,
                status="timeout",
                command=command,
                output_file=output_file,
                stdout=exc.stdout or "",
                stderr=exc.stderr or f"Codex CLI timed out after {task['max_duration_sec']} seconds",
                exit_code=124,
                duration_sec=time.monotonic() - started_at,
            )
            record["execution_argv"] = execution_command

        record = finalize_delegation_record(task, record, executor=runner)
        append_audit(record)
        return record

    except ValidationError as exc:
        record = rejected_record(task, str(exc), started_at)
        append_audit(record)
        return record


def load_task(task_arg: str) -> dict[str, Any]:
    stripped = task_arg.strip()
    if stripped.startswith("{"):
        return json.loads(stripped)

    candidate = Path(task_arg)
    if candidate.exists():
        return json.loads(candidate.read_text(encoding="utf-8-sig"))
    return json.loads(stripped)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Codex CLI as a bounded audited local tool."
    )
    parser.add_argument("--task", required=True, help="Path to a task JSON file or inline JSON")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and audit the task without invoking Codex CLI",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    started_at = time.monotonic()
    try:
        task = load_task(args.task)
    except Exception as exc:
        task = {"task_id": "invalid_task", "prompt": "", "workspace": str(ROOT)}
        record = rejected_record(task, f"failed to load task JSON: {exc}", started_at)
        append_audit(record)
        print(json.dumps(record, indent=2, ensure_ascii=False, sort_keys=True))
        return int(record["exit_code"])

    record = run_task(task, dry_run=args.dry_run)
    print(json.dumps(record, indent=2, ensure_ascii=False, sort_keys=True))
    return int(record["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
