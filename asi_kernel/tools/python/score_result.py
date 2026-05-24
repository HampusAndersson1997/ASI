from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


ROOT = Path("D:/Sandbox/asi_kernel").resolve(strict=False)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def norm_text(value: Path | str) -> str:
    return os.path.normcase(str(value))


def is_under(path: Path, root: Path) -> bool:
    path_text = norm_text(path.resolve(strict=False))
    root_text = norm_text(root.resolve(strict=False))
    return path_text == root_text or path_text.startswith(root_text + os.sep)


def resolve_path(path_text: str, root: Path) -> Path:
    path = Path(path_text)
    if not path.is_absolute():
        path = root / path
    return path.resolve(strict=False)


def shell_command(command: str) -> list[str]:
    shell = shutil.which("pwsh") or shutil.which("powershell") or "powershell"
    shell_name = Path(shell).name.lower()
    args = [shell, "-NoProfile"]
    if shell_name.startswith("powershell"):
        args.extend(["-ExecutionPolicy", "Bypass"])
    args.extend(["-Command", command])
    return args


def text_from_timeout(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def run_validation_command(
    command: str,
    *,
    workspace: Path,
    timeout_sec: int,
    executor: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    runner = executor or subprocess.run
    started_at = time.monotonic()
    argv = shell_command(command)
    try:
        completed = runner(
            argv,
            cwd=workspace,
            text=True,
            capture_output=True,
            timeout=timeout_sec,
        )
        exit_code = int(completed.returncode)
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
    except subprocess.TimeoutExpired as exc:
        exit_code = 124
        stdout = text_from_timeout(exc.stdout)
        stderr = text_from_timeout(exc.stderr) or f"validation timed out after {timeout_sec} seconds"
    except FileNotFoundError as exc:
        exit_code = 127
        stdout = ""
        stderr = f"validation shell not found: {exc}"

    return {
        "command": command,
        "argv": argv,
        "cwd": str(workspace),
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "duration_sec": round(time.monotonic() - started_at, 3),
    }


def expected_output_status(task: dict[str, Any], root: Path) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for output in task.get("expected_outputs", []):
        path = resolve_path(str(output), root)
        results.append({
            "path": str(path),
            "exists": path.exists(),
            "under_root": is_under(path, root),
        })
    return results


def output_file_status(run_record: dict[str, Any], root: Path) -> dict[str, Any]:
    output_file = run_record.get("output_file")
    if not output_file:
        return {"path": None, "exists": False, "under_outputs_dir": False}

    path = resolve_path(str(output_file), root)
    output_root = (root / "logs" / "codex_cli_outputs").resolve(strict=False)
    return {
        "path": str(path),
        "exists": path.exists(),
        "under_outputs_dir": is_under(path, output_root),
    }


def first_failed_validation_exit_code(validation_results: list[dict[str, Any]]) -> int:
    for result in validation_results:
        exit_code = int(result.get("exit_code", 1))
        if exit_code != 0:
            return exit_code
    return 1


def score_result(
    task: dict[str, Any],
    run_record: dict[str, Any],
    *,
    executor: Callable[..., Any] | None = None,
    root: Path | str = ROOT,
) -> dict[str, Any]:
    root_path = Path(root).resolve(strict=False)
    workspace = resolve_path(str(task.get("workspace", root_path)), root_path)
    validation_commands = [str(command) for command in task.get("validation_commands", [])]
    max_duration_sec = int(task.get("max_duration_sec", 300))
    validation_timeout = max(1, min(max_duration_sec, 300))
    delegation_exit_code = int(run_record.get("exit_code", 1))
    delegation_status = str(run_record.get("status", "unknown"))

    validation_results: list[dict[str, Any]] = []
    failure_reasons: list[str] = []
    expected_outputs = expected_output_status(task, root_path)
    output_file = output_file_status(run_record, root_path)

    if delegation_exit_code != 0 or delegation_status in {"failed", "timeout"}:
        failure_reasons.append(f"delegation failed with exit code {delegation_exit_code}")
    else:
        if not validation_commands:
            failure_reasons.append("no validation commands configured")
        for command in validation_commands:
            result = run_validation_command(
                command,
                workspace=workspace,
                timeout_sec=validation_timeout,
                executor=executor,
            )
            validation_results.append(result)
            if result["exit_code"] != 0:
                failure_reasons.append(f"validation command failed: {command}")

    for output in expected_outputs:
        if not output["under_root"]:
            failure_reasons.append(f"expected output outside root: {output['path']}")
        if not output["exists"]:
            failure_reasons.append(f"expected output missing: {output['path']}")

    if not output_file["under_outputs_dir"]:
        failure_reasons.append("codex output file is outside logs/codex_cli_outputs")
    if not output_file["exists"]:
        failure_reasons.append(f"codex output file missing: {output_file['path']}")

    passed = not failure_reasons
    return {
        "evaluated_at": utc_now(),
        "task_id": task.get("task_id"),
        "passed": passed,
        "score": 1.0 if passed else 0.0,
        "delegation_status": delegation_status,
        "delegation_exit_code": delegation_exit_code,
        "validation_results": validation_results,
        "expected_outputs": expected_outputs,
        "output_file": output_file,
        "failure_reasons": failure_reasons,
    }


def load_json_arg(value: str) -> dict[str, Any]:
    stripped = value.strip()
    if stripped.startswith("{"):
        return json.loads(stripped)
    return json.loads(Path(value).read_text(encoding="utf-8-sig"))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score a Codex CLI delegation result with validation commands.")
    parser.add_argument("--task", required=True, help="Task JSON path or inline JSON")
    parser.add_argument("--run-record", required=True, help="Run record JSON path or inline JSON")
    parser.add_argument("--output", help="Optional path to write evaluation JSON")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    task = load_json_arg(args.task)
    run_record = load_json_arg(args.run_record)
    evaluation = score_result(task, run_record)
    payload = json.dumps(evaluation, indent=2, ensure_ascii=False, sort_keys=True)
    if args.output:
        output_path = resolve_path(args.output, ROOT)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload + "\n", encoding="utf-8")
    print(payload)
    return 0 if evaluation["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
