from __future__ import annotations

import importlib.util
import json
import sqlite3
from pathlib import Path
from typing import Any


ROOT = Path("D:/Sandbox/asi_kernel")
MEMORY_TOOLS = ROOT / "tools" / "memory"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sqlite_tables(db_path: Path) -> set[str]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("select name from sqlite_master where type = 'table'").fetchall()
    return {str(row[0]) for row in rows}


def count_rows(db_path: Path, table: str) -> int:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(f"select count(*) from {table}").fetchone()
    assert row is not None
    return int(row[0])


def fetch_one(db_path: Path, table: str, task_id: str) -> sqlite3.Row:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(f"select * from {table} where task_id = ?", (task_id,)).fetchone()
    assert row is not None
    return row


def pass_task(tmp_path: Path, task_id: str = "memory-pass") -> dict[str, Any]:
    return {
        "task_id": task_id,
        "risk_level": "low",
        "workspace": str(tmp_path),
        "expected_outputs": [f"logs/codex_cli_outputs/{task_id}.md"],
    }


def pass_run(task_id: str = "memory-pass") -> dict[str, Any]:
    return {
        "task_id": task_id,
        "status": "passed",
        "exit_code": 0,
        "output_file": f"logs/codex_cli_outputs/{task_id}.md",
        "prompt_sha256": "abc123",
    }


def pass_eval() -> dict[str, Any]:
    return {
        "passed": True,
        "score": 1.0,
        "validation_results": [{"command": "python -m pytest", "exit_code": 0}],
        "failure_reasons": [],
    }


def fail_eval() -> dict[str, Any]:
    return {
        "passed": False,
        "score": 0.0,
        "failure_reasons": ["validation command failed"],
        "validation_results": [{"command": "python -m pytest tests/test_memory_tools.py", "exit_code": 3}],
    }


def test_init_memory_creates_sqlite_schema_and_index(tmp_path):
    init_memory = load_module("init_memory_v1", MEMORY_TOOLS / "init_memory.py")

    paths = init_memory.init_memory(root=tmp_path)
    db_path = Path(paths["sqlite"])
    index = json.loads(Path(paths["index"]).read_text(encoding="utf-8"))

    assert db_path == tmp_path / "memory" / "asi_kernel.sqlite"
    assert db_path.exists()
    assert {"schema_meta", "memory_records", "agent_runs", "failures"}.issubset(sqlite_tables(db_path))
    assert index["records"]["sqlite"] == str(db_path)
    assert index["schema_version"] == 1

    with sqlite3.connect(db_path) as conn:
        row = conn.execute("select value from schema_meta where key = 'schema_version'").fetchone()
    assert row == ("1",)


def test_init_memory_imports_existing_jsonl_records_into_sqlite(tmp_path):
    init_memory = load_module("init_memory_import_v1", MEMORY_TOOLS / "init_memory.py")
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir(parents=True)
    pass_record = {
        "record_id": "import-pass-001",
        "record_type": "agent_run",
        "created_at": "2026-05-24T04:00:00+00:00",
        "task_id": "import-pass",
        "workspace": str(tmp_path),
        "risk_level": "low",
        "run_status": "passed",
        "exit_code": 0,
        "delegation_exit_code": 0,
        "score": 1.0,
        "output_file": "logs/codex_cli_outputs/import-pass.md",
        "expected_outputs": ["logs/codex_cli_outputs/import-pass.md"],
        "validation_results": [{"command": "python -m pytest", "exit_code": 0}],
        "failure_reasons": [],
        "prompt_sha256": "passhash",
        "result": "passed",
    }
    fail_record = {
        "record_id": "import-fail-001",
        "record_type": "failure",
        "classified_at": "2026-05-24T04:05:00+00:00",
        "created_at": "2026-05-24T04:05:00+00:00",
        "task_id": "import-fail",
        "workspace": str(tmp_path),
        "risk_level": "low",
        "run_status": "validation_failed",
        "exit_code": 7,
        "delegation_exit_code": 0,
        "score": 0.0,
        "output_file": "logs/codex_cli_outputs/import-fail.md",
        "expected_outputs": ["logs/codex_cli_outputs/import-fail.md"],
        "validation_results": [{"command": "python -m pytest", "exit_code": 7}],
        "failure_reasons": ["validation command failed"],
        "failed_validation_commands": ["python -m pytest"],
        "failure_class": "validation_failed",
        "prompt_sha256": "failhash",
        "result": "failed",
    }
    (memory_dir / "agent_runs.jsonl").write_text(json.dumps(pass_record) + "\n", encoding="utf-8")
    (memory_dir / "failures.jsonl").write_text(json.dumps(fail_record) + "\n", encoding="utf-8")

    paths = init_memory.init_memory(root=tmp_path)
    init_memory.init_memory(root=tmp_path)
    db_path = Path(paths["sqlite"])

    assert count_rows(db_path, "memory_records") == 2
    assert count_rows(db_path, "agent_runs") == 1
    assert count_rows(db_path, "failures") == 1
    assert fetch_one(db_path, "agent_runs", "import-pass")["record_id"] == "import-pass-001"
    assert fetch_one(db_path, "failures", "import-fail")["failure_class"] == "validation_failed"


def test_save_agent_result_writes_pass_to_jsonl_and_sqlite(tmp_path):
    save_agent_run = load_module("save_agent_run_v1", MEMORY_TOOLS / "save_agent_run.py")
    task = pass_task(tmp_path)

    result = save_agent_run.save_agent_result(task, pass_run(), pass_eval(), root=tmp_path)
    db_path = tmp_path / "memory" / "asi_kernel.sqlite"
    row = fetch_one(db_path, "agent_runs", "memory-pass")
    memory_row = fetch_one(db_path, "memory_records", "memory-pass")

    assert result["record_type"] == "agent_run"
    assert result["sqlite"] == str(db_path)
    assert row["record_id"] == result["record_id"]
    assert row["score"] == 1.0
    assert json.loads(row["validation_results_json"])[0]["exit_code"] == 0
    assert memory_row["record_type"] == "agent_run"
    assert read_jsonl(tmp_path / "memory" / "agent_runs.jsonl")[0]["task_id"] == "memory-pass"
    assert count_rows(db_path, "failures") == 0


def test_save_failure_writes_failure_to_jsonl_and_sqlite(tmp_path):
    save_failure = load_module("save_failure_v1", MEMORY_TOOLS / "save_failure.py")
    task = pass_task(tmp_path, task_id="memory-fail")
    run_record = {
        "task_id": "memory-fail",
        "status": "validation_failed",
        "exit_code": 3,
        "output_file": "logs/codex_cli_outputs/memory-fail.md",
    }

    result = save_failure.save_failure_result(task, run_record, fail_eval(), root=tmp_path)
    db_path = tmp_path / "memory" / "asi_kernel.sqlite"
    row = fetch_one(db_path, "failures", "memory-fail")
    memory_row = fetch_one(db_path, "memory_records", "memory-fail")

    assert result["record_type"] == "failure"
    assert result["sqlite"] == str(db_path)
    assert row["failure_class"] == "validation_failed"
    assert json.loads(row["failed_validation_commands_json"]) == ["python -m pytest tests/test_memory_tools.py"]
    assert memory_row["record_type"] == "failure"
    assert read_jsonl(tmp_path / "memory" / "failures.jsonl")[0]["failure_class"] == "validation_failed"
    assert count_rows(db_path, "agent_runs") == 0


def test_save_agent_result_routes_failed_evaluations_to_failure_store(tmp_path):
    save_agent_run = load_module("save_agent_run_route_v1", MEMORY_TOOLS / "save_agent_run.py")
    task = pass_task(tmp_path, task_id="routed-fail")
    run_record = {
        "task_id": "routed-fail",
        "status": "validation_failed",
        "exit_code": 3,
        "output_file": "logs/codex_cli_outputs/routed-fail.md",
    }

    result = save_agent_run.save_agent_result(task, run_record, fail_eval(), root=tmp_path)

    assert result["record_type"] == "failure"
    assert fetch_one(tmp_path / "memory" / "asi_kernel.sqlite", "failures", "routed-fail")["failure_class"] == "validation_failed"


def test_search_memory_finds_agent_runs_and_failures_from_sqlite(tmp_path):
    save_agent_run = load_module("save_agent_run_search_v1", MEMORY_TOOLS / "save_agent_run.py")
    save_failure = load_module("save_failure_search_v1", MEMORY_TOOLS / "save_failure.py")
    search_memory = load_module("search_memory_v1", MEMORY_TOOLS / "search_memory.py")

    save_agent_run.save_agent_result(pass_task(tmp_path, "passing-pytest-run"), pass_run("passing-pytest-run"), pass_eval(), root=tmp_path)
    save_failure.save_failure_result(
        pass_task(tmp_path, "failing-pytest-run"),
        {
            "task_id": "failing-pytest-run",
            "status": "validation_failed",
            "exit_code": 3,
            "output_file": "logs/codex_cli_outputs/failing-pytest-run.md",
        },
        fail_eval(),
        root=tmp_path,
    )

    results = search_memory.search_memory("pytest", root=tmp_path, limit=10)
    failures = search_memory.search_memory("validation_failed", root=tmp_path, record_type="failure", limit=10)

    assert {item["task_id"] for item in results} == {"passing-pytest-run", "failing-pytest-run"}
    assert all(item["record_type"] in {"agent_run", "failure"} for item in results)
    assert [item["task_id"] for item in failures] == ["failing-pytest-run"]
    assert failures[0]["failure_class"] == "validation_failed"


def test_dashboard_includes_sqlite_memory_stats(tmp_path):
    save_agent_run = load_module("save_agent_run_dashboard_v1", MEMORY_TOOLS / "save_agent_run.py")
    save_failure = load_module("save_failure_dashboard_v1", MEMORY_TOOLS / "save_failure.py")
    dashboard = load_module("progress_report_memory_v1", ROOT / "dashboards" / "progress_report.py")

    save_agent_run.save_agent_result(pass_task(tmp_path, "dashboard-pass"), pass_run("dashboard-pass"), pass_eval(), root=tmp_path)
    save_failure.save_failure_result(
        pass_task(tmp_path, "dashboard-fail"),
        {
            "task_id": "dashboard-fail",
            "status": "validation_failed",
            "exit_code": 3,
            "output_file": "logs/codex_cli_outputs/dashboard-fail.md",
        },
        fail_eval(),
        root=tmp_path,
    )

    report = dashboard.build_report(root=tmp_path, timestamp="2026-05-24T04:30:00+00:00")
    markdown = dashboard.format_markdown(report)

    assert report["memory_database"]["exists"] is True
    assert report["memory_database"]["schema_version"] == "1"
    assert report["memory_database"]["agent_runs"] == 1
    assert report["memory_database"]["failures"] == 1
    assert report["memory_database"]["total_records"] == 2
    assert "## Memory DB Stats" in markdown
    assert "asi_kernel.sqlite" in markdown
