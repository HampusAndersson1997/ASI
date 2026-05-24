from __future__ import annotations

import argparse
import json
import sqlite3
import sys
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
from save_agent_run import append_jsonl, base_record, insert_memory_record, json_text


def insert_failure_sqlite(db_path: Path, record: dict[str, Any]) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        insert_memory_record(conn, record)
        conn.execute(
            """
            INSERT INTO failures (
                record_id,
                classified_at,
                created_at,
                task_id,
                workspace,
                risk_level,
                run_status,
                exit_code,
                delegation_exit_code,
                score,
                output_file,
                failure_class,
                expected_outputs_json,
                validation_results_json,
                failure_reasons_json,
                failed_validation_commands_json,
                prompt_sha256,
                record_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["record_id"],
                record.get("classified_at"),
                record["created_at"],
                record["task_id"],
                record.get("workspace"),
                record.get("risk_level"),
                record.get("run_status"),
                record.get("exit_code"),
                record.get("delegation_exit_code"),
                record.get("score"),
                record.get("output_file"),
                record.get("failure_class", "unknown_failure"),
                json_text(record.get("expected_outputs", [])),
                json_text(record.get("validation_results", [])),
                json_text(record.get("failure_reasons", [])),
                json_text(record.get("failed_validation_commands", [])),
                record.get("prompt_sha256"),
                json_text(record),
            ),
        )
        conn.commit()


def save_failure_result(
    task: dict[str, Any],
    run_record: dict[str, Any],
    evaluation: dict[str, Any] | None = None,
    *,
    root: Path | str = ROOT,
) -> dict[str, Any]:
    root_path = Path(root).resolve(strict=False)
    paths = init_memory(root=root_path)
    evaluation = evaluation or {}
    failure = classify_failure(run_record, evaluation)
    record = base_record(task, run_record, evaluation, record_type="failure")
    record["result"] = "failed"
    record.update(failure)
    path = Path(paths["failures"])

    append_jsonl(path, record)
    insert_failure_sqlite(Path(paths["sqlite"]), record)
    return {
        "record_type": str(record["record_type"]),
        "path": str(path),
        "sqlite": paths["sqlite"],
        "record_id": str(record["record_id"]),
        "record": record,
    }


def load_json_arg(value: str) -> dict[str, Any]:
    stripped = value.strip()
    if stripped.startswith("{"):
        return json.loads(stripped)
    return json.loads(Path(value).read_text(encoding="utf-8-sig"))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Save a failed Codex delegate result into local SQLite memory.")
    parser.add_argument("--task", required=True, help="Task JSON path or inline JSON")
    parser.add_argument("--run-record", required=True, help="Run record JSON path or inline JSON")
    parser.add_argument("--evaluation", help="Evaluation JSON path or inline JSON")
    parser.add_argument("--root", default=str(ROOT))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    result = save_failure_result(
        load_json_arg(args.task),
        load_json_arg(args.run_record),
        load_json_arg(args.evaluation) if args.evaluation else {},
        root=args.root,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
