from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path("D:/Sandbox/asi_kernel").resolve(strict=False)
TOOLS_MEMORY = ROOT / "tools" / "memory"
TOOLS_PYTHON = ROOT / "tools" / "python"
for import_path in (TOOLS_MEMORY, TOOLS_PYTHON):
    import_text = str(import_path)
    if import_text not in sys.path:
        sys.path.insert(0, import_text)

from classify_failure import classify_failure
from init_memory import init_memory


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def record_id(record_type: str, task_id: str, created_at: str) -> str:
    digest = hashlib.sha256(f"{record_type}:{task_id}:{created_at}".encode("utf-8")).hexdigest()
    return digest[:24]


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as jsonl_file:
        jsonl_file.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def validation_command_text(record: dict[str, Any]) -> str:
    commands: list[str] = []
    for result in record.get("validation_results", []):
        if isinstance(result, dict) and result.get("command"):
            commands.append(str(result["command"]))
    return " ".join(commands)


def content_text(record: dict[str, Any]) -> str:
    parts = [
        record.get("record_type"),
        record.get("result"),
        record.get("task_id"),
        record.get("workspace"),
        record.get("risk_level"),
        record.get("run_status"),
        record.get("failure_class"),
        record.get("output_file"),
        record.get("prompt_sha256"),
        " ".join(str(item) for item in record.get("expected_outputs", [])),
        " ".join(str(item) for item in record.get("failure_reasons", [])),
        validation_command_text(record),
    ]
    return " ".join(str(part) for part in parts if part not in (None, ""))


def insert_memory_record(conn: sqlite3.Connection, record: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO memory_records (
            record_id,
            record_type,
            created_at,
            task_id,
            status,
            score,
            failure_class,
            output_file,
            content_text,
            record_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record["record_id"],
            record["record_type"],
            record["created_at"],
            record["task_id"],
            record.get("run_status") or record.get("result"),
            record.get("score"),
            record.get("failure_class"),
            record.get("output_file"),
            content_text(record),
            json_text(record),
        ),
    )


def insert_agent_run_sqlite(db_path: Path, record: dict[str, Any]) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        insert_memory_record(conn, record)
        conn.execute(
            """
            INSERT INTO agent_runs (
                record_id,
                created_at,
                task_id,
                workspace,
                risk_level,
                run_status,
                exit_code,
                delegation_exit_code,
                score,
                output_file,
                expected_outputs_json,
                validation_results_json,
                failure_reasons_json,
                prompt_sha256,
                record_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["record_id"],
                record["created_at"],
                record["task_id"],
                record.get("workspace"),
                record.get("risk_level"),
                record.get("run_status"),
                record.get("exit_code"),
                record.get("delegation_exit_code"),
                record.get("score"),
                record.get("output_file"),
                json_text(record.get("expected_outputs", [])),
                json_text(record.get("validation_results", [])),
                json_text(record.get("failure_reasons", [])),
                record.get("prompt_sha256"),
                json_text(record),
            ),
        )
        conn.commit()


def base_record(
    task: dict[str, Any],
    run_record: dict[str, Any],
    evaluation: dict[str, Any],
    *,
    record_type: str,
) -> dict[str, Any]:
    created_at = utc_now()
    task_id = str(task.get("task_id", run_record.get("task_id", "unknown")))
    return {
        "record_id": record_id(record_type, task_id, created_at),
        "record_type": record_type,
        "created_at": created_at,
        "task_id": task_id,
        "workspace": task.get("workspace", run_record.get("workspace")),
        "risk_level": task.get("risk_level", run_record.get("risk_level")),
        "run_status": run_record.get("status"),
        "exit_code": run_record.get("exit_code"),
        "delegation_exit_code": evaluation.get("delegation_exit_code", run_record.get("delegation_exit_code")),
        "score": evaluation.get("score"),
        "output_file": run_record.get("output_file"),
        "expected_outputs": task.get("expected_outputs", []),
        "validation_results": evaluation.get("validation_results", []),
        "failure_reasons": evaluation.get("failure_reasons", []),
        "prompt_sha256": run_record.get("prompt_sha256"),
    }


def save_agent_run(
    task: dict[str, Any],
    run_record: dict[str, Any],
    evaluation: dict[str, Any],
    *,
    root: Path | str = ROOT,
) -> dict[str, Any]:
    root_path = Path(root).resolve(strict=False)
    paths = init_memory(root=root_path)
    record = base_record(task, run_record, evaluation, record_type="agent_run")
    record["result"] = "passed"
    path = Path(paths["agent_runs"])

    append_jsonl(path, record)
    insert_agent_run_sqlite(Path(paths["sqlite"]), record)
    return {
        "record_type": str(record["record_type"]),
        "path": str(path),
        "sqlite": paths["sqlite"],
        "record_id": str(record["record_id"]),
        "record": record,
    }


def save_agent_result(
    task: dict[str, Any],
    run_record: dict[str, Any],
    evaluation: dict[str, Any],
    *,
    root: Path | str = ROOT,
) -> dict[str, Any]:
    root_path = Path(root).resolve(strict=False)

    if evaluation.get("passed") is True:
        return save_agent_run(task, run_record, evaluation, root=root_path)
    else:
        from save_failure import save_failure_result

        return save_failure_result(task, run_record, evaluation, root=root_path)


def load_json_arg(value: str) -> dict[str, Any]:
    stripped = value.strip()
    if stripped.startswith("{"):
        return json.loads(stripped)
    return json.loads(Path(value).read_text(encoding="utf-8-sig"))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Save a Codex delegate run evaluation into local memory.")
    parser.add_argument("--task", required=True, help="Task JSON path or inline JSON")
    parser.add_argument("--run-record", required=True, help="Run record JSON path or inline JSON")
    parser.add_argument("--evaluation", required=True, help="Evaluation JSON path or inline JSON")
    parser.add_argument("--root", default=str(ROOT))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    result = save_agent_result(
        load_json_arg(args.task),
        load_json_arg(args.run_record),
        load_json_arg(args.evaluation),
        root=args.root,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
