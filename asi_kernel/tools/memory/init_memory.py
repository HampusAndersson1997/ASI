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
SCHEMA_VERSION = "1"
SQLITE_NAME = "asi_kernel.sqlite"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def touch_jsonl(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(exist_ok=True)


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not path.exists():
        return records
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if line.strip():
            record = json.loads(line)
            if isinstance(record, dict):
                records.append(record)
    return records


def record_id_for(record_type: str, task_id: str, created_at: str) -> str:
    digest = hashlib.sha256(f"{record_type}:{task_id}:{created_at}".encode("utf-8")).hexdigest()
    return digest[:24]


def canonical_record(record: dict[str, Any], record_type: str) -> dict[str, Any]:
    created_at = str(record.get("created_at") or utc_now())
    task_id = str(record.get("task_id") or "unknown")
    normalized = dict(record)
    normalized["record_type"] = record_type
    normalized["created_at"] = created_at
    normalized["task_id"] = task_id
    normalized["record_id"] = str(record.get("record_id") or record_id_for(record_type, task_id, created_at))
    return normalized


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


def memory_db_path(root: Path | str = ROOT) -> Path:
    return Path(root).resolve(strict=False) / "memory" / SQLITE_NAME


def init_sqlite(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_records (
                record_id TEXT PRIMARY KEY,
                record_type TEXT NOT NULL CHECK (record_type IN ('agent_run', 'failure')),
                created_at TEXT NOT NULL,
                task_id TEXT NOT NULL,
                status TEXT,
                score REAL,
                failure_class TEXT,
                output_file TEXT,
                content_text TEXT NOT NULL,
                record_json TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_runs (
                record_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                task_id TEXT NOT NULL,
                workspace TEXT,
                risk_level TEXT,
                run_status TEXT,
                exit_code INTEGER,
                delegation_exit_code INTEGER,
                score REAL,
                output_file TEXT,
                expected_outputs_json TEXT NOT NULL,
                validation_results_json TEXT NOT NULL,
                failure_reasons_json TEXT NOT NULL,
                prompt_sha256 TEXT,
                record_json TEXT NOT NULL,
                FOREIGN KEY (record_id) REFERENCES memory_records(record_id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS failures (
                record_id TEXT PRIMARY KEY,
                classified_at TEXT,
                created_at TEXT NOT NULL,
                task_id TEXT NOT NULL,
                workspace TEXT,
                risk_level TEXT,
                run_status TEXT,
                exit_code INTEGER,
                delegation_exit_code INTEGER,
                score REAL,
                output_file TEXT,
                failure_class TEXT NOT NULL,
                expected_outputs_json TEXT NOT NULL,
                validation_results_json TEXT NOT NULL,
                failure_reasons_json TEXT NOT NULL,
                failed_validation_commands_json TEXT NOT NULL,
                prompt_sha256 TEXT,
                record_json TEXT NOT NULL,
                FOREIGN KEY (record_id) REFERENCES memory_records(record_id) ON DELETE CASCADE
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_records_created_at ON memory_records(created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_records_task_id ON memory_records(task_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_records_type ON memory_records(record_type)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_failures_class ON failures(failure_class)")
        conn.execute(
            """
            INSERT INTO schema_meta (key, value, updated_at)
            VALUES ('schema_version', ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (SCHEMA_VERSION, utc_now()),
        )
        conn.commit()


def insert_memory_record(conn: sqlite3.Connection, record: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO memory_records (
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


def insert_agent_run_record(conn: sqlite3.Connection, record: dict[str, Any]) -> None:
    insert_memory_record(conn, record)
    conn.execute(
        """
        INSERT OR IGNORE INTO agent_runs (
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


def insert_failure_record(conn: sqlite3.Connection, record: dict[str, Any]) -> None:
    insert_memory_record(conn, record)
    conn.execute(
        """
        INSERT OR IGNORE INTO failures (
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


def import_jsonl_memory(*, db_path: Path, agent_runs: Path, failures: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        for record in read_jsonl(agent_runs):
            insert_agent_run_record(conn, canonical_record(record, "agent_run"))
        for record in read_jsonl(failures):
            insert_failure_record(conn, canonical_record(record, "failure"))
        conn.commit()


def init_memory(*, root: Path | str = ROOT) -> dict[str, str]:
    root_path = Path(root).resolve(strict=False)
    memory_dir = root_path / "memory"
    agent_runs = memory_dir / "agent_runs.jsonl"
    failures = memory_dir / "failures.jsonl"
    index = memory_dir / "agent_memory_index.json"
    sqlite = memory_db_path(root_path)

    touch_jsonl(agent_runs)
    touch_jsonl(failures)
    init_sqlite(sqlite)
    import_jsonl_memory(db_path=sqlite, agent_runs=agent_runs, failures=failures)
    index_payload: dict[str, Any] = {
        "updated_at": utc_now(),
        "purpose": "Local memory for bounded Codex CLI delegate outcomes.",
        "schema_version": int(SCHEMA_VERSION),
        "records": {
            "agent_runs": str(agent_runs),
            "failures": str(failures),
            "sqlite": str(sqlite),
        },
    }
    index.write_text(json.dumps(index_payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")

    return {
        "memory_dir": str(memory_dir),
        "agent_runs": str(agent_runs),
        "failures": str(failures),
        "index": str(index),
        "sqlite": str(sqlite),
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Initialize local Codex delegate memory JSONL files.")
    parser.add_argument("--root", default=str(ROOT))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    paths = init_memory(root=args.root)
    print(json.dumps(paths, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
