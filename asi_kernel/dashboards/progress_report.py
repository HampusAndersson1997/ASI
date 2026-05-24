from __future__ import annotations

import argparse
import ast
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path("D:/Sandbox/asi_kernel").resolve(strict=False)
REPORT_RELATIVE_PATH = Path("dashboards/progress_report.md")
HARNESS_LAYERS = [
    "Search/research tools",
    "Local shell tools",
    "Memory tools",
    "Benchmark tools",
    "Evaluator",
    "Refiner",
    "Safety tools",
    "Dashboard",
]
RESOLVED_STATUSES = {"completed", "dry_run", "passed", "success"}
UNRESOLVED_STATUSES = {"error", "failed", "rejected", "timeout", "validation_failed"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def rel_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def newest_key(record: dict[str, Any]) -> str:
    return str(record.get("created_at") or record.get("logged_at") or "")


def latest_time(record: dict[str, Any]) -> str:
    return str(record.get("logged_at") or record.get("created_at") or record.get("evaluated_at") or "")


def output_summary(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": record.get("task_id"),
        "result": record.get("result"),
        "created_at": record.get("created_at"),
        "output_file": record.get("output_file"),
        "score": record.get("score"),
        "failure_class": record.get("failure_class"),
    }


def summarize_tests(root: Path) -> dict[str, Any]:
    tests_dir = root / "tests"
    files = sorted(tests_dir.rglob("test*.py")) if tests_dir.exists() else []
    file_summaries: list[dict[str, Any]] = []
    parse_errors: list[dict[str, str]] = []
    test_count = 0
    test_class_count = 0

    for path in files:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        except (OSError, SyntaxError, UnicodeDecodeError) as exc:
            parse_errors.append({"path": rel_path(path, root), "error": str(exc)})
            continue

        file_tests = sum(
            1
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_")
        )
        file_classes = sum(1 for node in ast.walk(tree) if isinstance(node, ast.ClassDef) and node.name.startswith("Test"))
        test_count += file_tests
        test_class_count += file_classes
        file_summaries.append({"path": rel_path(path, root), "test_count": file_tests, "test_classes": file_classes})

    return {
        "path": rel_path(tests_dir, root),
        "test_files": len(files),
        "test_count": test_count,
        "test_classes": test_class_count,
        "files": file_summaries,
        "parse_errors": parse_errors,
    }


def summarize_preflight(root: Path) -> dict[str, Any]:
    path = root / "logs" / "codex_cli_preflight.json"
    data = read_json(path, default=None)
    if not isinstance(data, dict):
        return {
            "path": rel_path(path, root),
            "exists": path.exists(),
            "status": "missing",
            "ready": False,
            "current_path_ok": False,
            "checked_at": None,
            "codex_version": None,
            "checks": [],
            "missing_or_failed_checks": ["codex_cli_preflight.json"],
        }

    checks = data.get("checks") if isinstance(data.get("checks"), dict) else {}
    check_summaries: list[dict[str, Any]] = []
    missing_or_failed: list[str] = []
    for name, check in sorted(checks.items()):
        check_data = check if isinstance(check, dict) else {}
        available = bool(check_data.get("available"))
        exit_code = check_data.get("exit_code")
        if not available or (exit_code not in (None, 0)):
            missing_or_failed.append(str(name))
        check_summaries.append(
            {
                "name": name,
                "available": available,
                "exit_code": exit_code,
                "stdout": check_data.get("stdout"),
                "source": check_data.get("source"),
            }
        )

    ready = bool(data.get("ready"))
    current_path_ok = bool(data.get("current_path_ok"))
    codex_version = checks.get("codex_version") if isinstance(checks.get("codex_version"), dict) else {}
    return {
        "path": rel_path(path, root),
        "exists": True,
        "status": "ready" if ready else "not ready",
        "ready": ready,
        "current_path_ok": current_path_ok,
        "checked_at": data.get("checked_at"),
        "codex_version": codex_version.get("stdout"),
        "checks": check_summaries,
        "missing_or_failed_checks": missing_or_failed,
    }


def summarize_codex_run(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": record.get("task_id"),
        "logged_at": record.get("logged_at"),
        "created_at": record.get("created_at"),
        "status": record.get("status") or record.get("result"),
        "exit_code": record.get("exit_code"),
        "risk_level": record.get("risk_level"),
        "duration_sec": record.get("duration_sec"),
        "output_file": record.get("output_file"),
        "failure_class": record.get("failure_class"),
        "stderr": record.get("stderr"),
    }


def summarize_codex_runs(root: Path, newest_limit: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records = read_jsonl(root / "logs" / "codex_cli_runs.jsonl")
    records = sorted(records, key=latest_time, reverse=True)
    return records, [summarize_codex_run(record) for record in records[:newest_limit]]


def summarize_patch_proposal_runs(root: Path) -> dict[str, Any]:
    path = root / "logs" / "research" / "patch_proposal_runs.jsonl"
    records = read_jsonl(path)
    summary_records = [
        record
        for record in records
        if record.get("stage") == "6c"
        and record.get("event") == "patch_proposal_summary"
        and isinstance(record.get("summary"), dict)
    ]
    if not summary_records:
        return {
            "path": rel_path(path, root),
            "exists": path.exists(),
            "status": "missing",
            "stage": "6c",
            "ok": False,
            "cycles_completed": 0,
            "proposal_path": None,
            "patch_path": None,
            "risk_classification": None,
            "risk_reasons": [],
            "tests_selected": [],
            "human_approval_required": None,
            "auto_applied": None,
            "changed_files": [],
            "decision": None,
            "record_count": len(records),
        }

    latest = max(summary_records, key=lambda record: float(record.get("timestamp_unix") or 0.0))
    summary = latest["summary"]
    proposal_path = Path(str(summary.get("proposal_path"))) if summary.get("proposal_path") else None
    patch_path = Path(str(summary.get("patch_path"))) if summary.get("patch_path") else None

    return {
        "path": rel_path(path, root),
        "exists": True,
        "status": "ok" if summary.get("ok") else "not ok",
        "stage": summary.get("stage") or "6c",
        "ok": bool(summary.get("ok")),
        "cycles_completed": summary.get("cycles_completed"),
        "proposal_path": rel_path(proposal_path, root) if proposal_path else None,
        "patch_path": rel_path(patch_path, root) if patch_path else None,
        "risk_classification": summary.get("risk_classification"),
        "risk_reasons": summary.get("risk_reasons") or [],
        "tests_selected": summary.get("tests_selected") or [],
        "human_approval_required": summary.get("human_approval_required"),
        "auto_applied": summary.get("auto_applied"),
        "changed_files": summary.get("changed_files") or [],
        "decision": summary.get("decision"),
        "record_count": len(records),
        "timestamp_unix": latest.get("timestamp_unix"),
    }


def summarize_tool_registry(root: Path) -> list[dict[str, Any]]:
    registry = read_json(root / "tools" / "tool_registry.json", default=[])
    if not isinstance(registry, list):
        return []
    entries: list[dict[str, Any]] = []
    for entry in registry:
        if not isinstance(entry, dict):
            continue
        entries.append(
            {
                "name": entry.get("name"),
                "purpose": entry.get("purpose"),
                "risk": entry.get("risk"),
                "command": entry.get("command"),
                "allowed_paths": entry.get("allowed_paths", []),
                "requires_confirmation": entry.get("requires_confirmation"),
                "writes_audit_log": entry.get("writes_audit_log"),
                "forbidden_flags": entry.get("forbidden_flags", []),
            }
        )
    return entries


def summarize_skills(root: Path) -> dict[str, Any]:
    skills_dir = root / "skills"
    skill_files = sorted(skills_dir.rglob("SKILL.md")) if skills_dir.exists() else []
    return {
        "path": rel_path(skills_dir, root),
        "skill_count": len(skill_files),
        "skills": [rel_path(path.parent, root) for path in skill_files],
    }


def summarize_verification(root: Path) -> dict[str, Any]:
    verification_dir = root / "verification"
    files = sorted(path for path in verification_dir.rglob("*") if path.is_file()) if verification_dir.exists() else []
    return {
        "path": rel_path(verification_dir, root),
        "file_count": len(files),
        "files": [rel_path(path, root) for path in files],
        "has_evidence_ledger": (verification_dir / "evidence_ledger.md").exists(),
        "has_benchmarks_dir": (verification_dir / "benchmarks").exists(),
        "has_tests_dir": (verification_dir / "tests").exists(),
    }


def sqlite_tables(db_path: Path) -> set[str]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {str(row[0]) for row in rows}


def sqlite_count(conn: sqlite3.Connection, table: str, tables: set[str]) -> int:
    if table not in tables:
        return 0
    row = conn.execute(f"SELECT count(*) FROM {table}").fetchone()
    return int(row[0]) if row else 0


def summarize_memory_database(root: Path, newest_limit: int) -> dict[str, Any]:
    db_path = root / "memory" / "asi_kernel.sqlite"
    if not db_path.exists():
        return {
            "path": rel_path(db_path, root),
            "exists": False,
            "schema_version": None,
            "tables": [],
            "total_records": 0,
            "agent_runs": 0,
            "failures": 0,
            "failure_classes": {},
            "latest_records": [],
        }

    try:
        tables = sqlite_tables(db_path)
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            schema_row = (
                conn.execute("SELECT value FROM schema_meta WHERE key = 'schema_version'").fetchone()
                if "schema_meta" in tables
                else None
            )
            failure_rows = (
                conn.execute(
                    "SELECT failure_class, count(*) AS count FROM failures GROUP BY failure_class ORDER BY failure_class"
                ).fetchall()
                if "failures" in tables
                else []
            )
            latest_rows = (
                conn.execute(
                    """
                    SELECT created_at, task_id, record_type, status, score, failure_class, output_file
                    FROM memory_records
                    ORDER BY created_at DESC, task_id DESC
                    LIMIT ?
                    """,
                    (newest_limit,),
                ).fetchall()
                if "memory_records" in tables
                else []
            )
            return {
                "path": rel_path(db_path, root),
                "exists": True,
                "schema_version": str(schema_row["value"]) if schema_row else None,
                "tables": sorted(tables),
                "total_records": sqlite_count(conn, "memory_records", tables),
                "agent_runs": sqlite_count(conn, "agent_runs", tables),
                "failures": sqlite_count(conn, "failures", tables),
                "failure_classes": {str(row["failure_class"]): int(row["count"]) for row in failure_rows},
                "latest_records": [dict(row) for row in latest_rows],
            }
    except sqlite3.Error as exc:
        return {
            "path": rel_path(db_path, root),
            "exists": True,
            "schema_version": None,
            "tables": [],
            "total_records": 0,
            "agent_runs": 0,
            "failures": 0,
            "failure_classes": {},
            "latest_records": [],
            "error": str(exc),
        }


def is_unresolved(record: dict[str, Any]) -> bool:
    status = str(record.get("status") or record.get("result") or "").lower()
    exit_code = record.get("exit_code")
    if status in UNRESOLVED_STATUSES:
        return True
    if record.get("failure_class"):
        return True
    if isinstance(exit_code, int) and exit_code != 0 and status not in RESOLVED_STATUSES:
        return True
    return False


def failure_reason(record: dict[str, Any]) -> str:
    if record.get("failure_class"):
        return str(record["failure_class"])
    evaluation = record.get("evaluation")
    if isinstance(evaluation, dict) and evaluation.get("failure_reasons"):
        return "; ".join(str(item) for item in evaluation["failure_reasons"])
    if record.get("stderr"):
        return str(record["stderr"])
    if record.get("status"):
        return str(record["status"])
    return "unknown"


def summarize_unresolved_failures(
    codex_run_records: list[dict[str, Any]],
    memory_failures: list[dict[str, Any]],
    *,
    newest_limit: int,
) -> list[dict[str, Any]]:
    combined: list[dict[str, Any]] = []
    for record in codex_run_records:
        if is_unresolved(record):
            item = summarize_codex_run(record)
            item["source"] = "logs/codex_cli_runs.jsonl"
            item["reason"] = failure_reason(record)
            combined.append(item)
    for record in memory_failures:
        item = output_summary(record)
        item["source"] = "memory/failures.jsonl"
        item["status"] = record.get("status") or record.get("failure_class") or "failure"
        item["exit_code"] = record.get("exit_code")
        item["reason"] = failure_reason(record)
        item["logged_at"] = record.get("logged_at")
        item["created_at"] = record.get("created_at")
        combined.append(item)
    combined.sort(key=latest_time, reverse=True)
    return combined[:newest_limit]


def progress_row(layer: str, checks: list[tuple[bool, str]]) -> dict[str, Any]:
    passed = [label for ok, label in checks if ok]
    gaps = [label for ok, label in checks if not ok]
    percent = round((len(passed) / len(checks)) * 100) if checks else 0
    return {
        "layer": layer,
        "percent": percent,
        "evidence": passed,
        "gaps": gaps,
    }


def build_harness_progress(
    *,
    root: Path,
    tests: dict[str, Any],
    preflight: dict[str, Any],
    codex_runs: list[dict[str, Any]],
    tool_entries: list[dict[str, Any]],
    skills: dict[str, Any],
    verification: dict[str, Any],
    memory_database: dict[str, Any],
    failures: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    memory_dir = root / "memory"
    local_llm_benchmark = root / "artifacts" / "local_llm" / "benchmark_comparison.json"
    benchmark_result = read_json(local_llm_benchmark, default={}) if local_llm_benchmark.exists() else {}
    score_result = root / "tools" / "python" / "score_result.py"
    classify_failure = root / "tools" / "python" / "classify_failure.py"
    safe_boundary = root / "verification" / "safe_autonomy_boundary.md"
    dashboard_script = root / "dashboards" / "progress_report.py"
    dashboard_output = root / REPORT_RELATIVE_PATH

    return [
        progress_row(
            "Search/research tools",
            [
                (bool(tool_entries), "tool registry has entries"),
                (skills["skill_count"] > 0, "local skills are discoverable"),
                (verification["has_evidence_ledger"], "verification evidence ledger exists"),
                ((root / "tools" / "tool_inventory.md").exists(), "tool inventory artifact exists"),
            ],
        ),
        progress_row(
            "Local shell tools",
            [
                (preflight["exists"], "Codex CLI preflight artifact exists"),
                (preflight["ready"], "Codex CLI preflight is ready"),
                (tests["test_count"] > 0, "pytest tests are present"),
                (bool(codex_runs), "Codex CLI audit log has records"),
            ],
        ),
        progress_row(
            "Memory tools",
            [
                ((memory_dir / "memory_protocol.md").exists(), "memory protocol exists"),
                ((memory_dir / "agent_memory_index.json").exists(), "agent memory index exists"),
                (memory_database["exists"], "SQLite memory database exists"),
                ("memory_records" in memory_database["tables"], "SQLite memory_records table exists"),
                ((memory_dir / "agent_runs.jsonl").exists(), "agent run memory log exists"),
                ((memory_dir / "failures.jsonl").exists(), "failure memory log exists"),
            ],
        ),
        progress_row(
            "Benchmark tools",
            [
                (verification["has_benchmarks_dir"], "verification benchmarks directory exists"),
                (local_llm_benchmark.exists(), "local LLM benchmark comparison artifact exists"),
                (bool(benchmark_result.get("result")), "benchmark comparison has a recorded result"),
                (verification["has_tests_dir"], "verification tests directory exists"),
            ],
        ),
        progress_row(
            "Evaluator",
            [
                (score_result.exists(), "score_result evaluator exists"),
                (any(isinstance(record.get("evaluation"), dict) for record in codex_runs), "Codex runs include evaluation records"),
                (any(record.get("validation_commands") for record in codex_runs), "validation commands are audited"),
                (tests["test_count"] > 0, "evaluator behavior is covered by tests"),
            ],
        ),
        progress_row(
            "Refiner",
            [
                (classify_failure.exists(), "failure classifier exists"),
                (bool(failures), "failure records exist for analysis"),
                (skills["skill_count"] > 0, "local skill refinement surface exists"),
                ((root / "verification" / "regression_tests.md").exists(), "regression-test refinement artifact exists"),
            ],
        ),
        progress_row(
            "Safety tools",
            [
                (any(entry.get("requires_confirmation") is True for entry in tool_entries), "registry requires confirmation for bounded tools"),
                (any(entry.get("forbidden_flags") for entry in tool_entries), "registry records forbidden Codex flags"),
                (preflight["current_path_ok"], "preflight current path is bounded to repo"),
                (safe_boundary.exists(), "safe autonomy boundary artifact exists"),
            ],
        ),
        progress_row(
            "Dashboard",
            [
                (dashboard_script.exists(), "dashboard generator exists"),
                (tests["test_count"] > 0, "dashboard input test inventory is available"),
                (dashboard_output.exists(), "progress_report.md already exists"),
                (True, "dashboard output path is bounded to repo"),
            ],
        ),
    ]


def recommend_next_tasks(report: dict[str, Any], root: Path) -> list[str]:
    tasks: list[str] = []
    if report["tests"]["parse_errors"]:
        tasks.append("Fix test parse errors so the dashboard test count is complete.")
    if not report["memory_database"]["exists"]:
        tasks.append("Initialize memory\\asi_kernel.sqlite with tools\\memory\\init_memory.py.")
    if not report["codex_cli_preflight"]["ready"]:
        tasks.append("Run tools\\codex_cli\\check_codex_cli.ps1 and resolve failed preflight checks.")
    if report["unresolved_failures"]:
        tasks.append("Triage unresolved Codex CLI failures and classify which are expected safety rejections versus real regressions.")
    if not (root / "tools" / "tool_inventory.md").exists():
        tasks.append("Create tools\\tool_inventory.md with verified capability status for search/research, shell, memory, and safety tools.")
    if not (root / "verification" / "safe_autonomy_boundary.md").exists():
        tasks.append("Write verification\\safe_autonomy_boundary.md to make autonomy permissions and stop conditions executable.")
    if not report.get("stage6c_patch_proposal", {}).get("ok"):
        tasks.append("Run research\\patch_proposal_loop.py --suite smoke --cycles 1 and review the generated Stage 6c patch proposal.")
    if not (root / "verification" / "asi_success_criteria.md").exists():
        tasks.append("Write verification\\asi_success_criteria.md with explicit non-goals and evidence thresholds.")
    if any(row["layer"] == "Benchmark tools" and row["percent"] < 100 for row in report["harness_progress"]):
        tasks.append("Expand benchmark coverage with held-out tasks and record results under verification or artifacts.")
    if not tasks:
        tasks.append("Run the next measured improvement cycle and record the result before changing progress percentages.")
    return tasks


def build_report(*, root: Path | str = ROOT, newest_limit: int = 5, timestamp: str | None = None) -> dict[str, Any]:
    root_path = Path(root).resolve(strict=False)
    memory_dir = root_path / "memory"
    agent_runs = read_jsonl(memory_dir / "agent_runs.jsonl")
    failures = read_jsonl(memory_dir / "failures.jsonl")
    total_runs = len(agent_runs) + len(failures)
    passed_runs = len(agent_runs)
    failed_runs = len(failures)
    pass_rate = passed_runs / total_runs if total_runs else 0.0
    failure_classes = Counter(str(record.get("failure_class", "unknown_failure")) for record in failures)
    combined = sorted(agent_runs + failures, key=newest_key, reverse=True)
    tests = summarize_tests(root_path)
    preflight = summarize_preflight(root_path)
    codex_run_records, latest_codex_runs = summarize_codex_runs(root_path, newest_limit)
    patch_proposal_runs = summarize_patch_proposal_runs(root_path)
    tool_entries = summarize_tool_registry(root_path)
    skills = summarize_skills(root_path)
    verification = summarize_verification(root_path)
    memory_database = summarize_memory_database(root_path, newest_limit)
    unresolved_failures = summarize_unresolved_failures(codex_run_records, failures, newest_limit=newest_limit)
    harness_progress = build_harness_progress(
        root=root_path,
        tests=tests,
        preflight=preflight,
        codex_runs=codex_run_records,
        tool_entries=tool_entries,
        skills=skills,
        verification=verification,
        memory_database=memory_database,
        failures=failures,
    )

    report = {
        "timestamp": timestamp or utc_now(),
        "root": str(root_path),
        "tests": tests,
        "codex_cli_preflight": preflight,
        "latest_codex_cli_runs": latest_codex_runs,
        "stage6c_patch_proposal": patch_proposal_runs,
        "tool_registry_entries": tool_entries,
        "skills": skills,
        "verification": verification,
        "memory_database": memory_database,
        "harness_progress": harness_progress,
        "unresolved_failures": unresolved_failures,
        "total_runs": total_runs,
        "passed_runs": passed_runs,
        "failed_runs": failed_runs,
        "pass_rate": pass_rate,
        "failure_classes": dict(sorted(failure_classes.items())),
        "newest_outputs": [output_summary(record) for record in combined[:newest_limit]],
    }
    report["next_recommended_tasks"] = recommend_next_tasks(report, root_path)
    return report


def md_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, list):
        value = "; ".join(str(item) for item in value)
    return str(value).replace("\n", " ").replace("|", "\\|")


def append_table(lines: list[str], headers: list[str], rows: list[list[Any]]) -> None:
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    for row in rows:
        lines.append("| " + " | ".join(md_cell(value) for value in row) + " |")


def format_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# ASI Kernel Progress Report",
        "",
        f"- Timestamp: {report['timestamp']}",
        f"- Root: {report['root']}",
        "- Scope: executable harness progress only; this is not evidence of AGI or ASI.",
        "",
        "## Test Count Summary",
        "",
        f"- Test files: {report['tests']['test_files']}",
        f"- Test functions: {report['tests']['test_count']}",
        f"- Test classes: {report['tests']['test_classes']}",
    ]

    if report["tests"]["parse_errors"]:
        lines.extend(["", "Test parse errors:"])
        for item in report["tests"]["parse_errors"]:
            lines.append(f"- {item['path']}: {item['error']}")

    lines.extend(["", "## Codex CLI Preflight", ""])
    preflight = report["codex_cli_preflight"]
    lines.extend(
        [
            f"- Status: {preflight['status']}",
            f"- Ready: {md_cell(preflight['ready'])}",
            f"- Current path OK: {md_cell(preflight['current_path_ok'])}",
            f"- Checked at: {preflight.get('checked_at') or ''}",
            f"- Codex version: {preflight.get('codex_version') or ''}",
        ]
    )
    if preflight["checks"]:
        lines.append("")
        append_table(
            lines,
            ["Check", "Available", "Exit", "Stdout", "Source"],
            [
                [item["name"], item["available"], item["exit_code"], item.get("stdout"), item.get("source")]
                for item in preflight["checks"]
            ],
        )

    lines.extend(["", "## Latest Codex CLI Runs", ""])
    if report["latest_codex_cli_runs"]:
        append_table(
            lines,
            ["Time", "Task", "Status", "Exit", "Risk", "Output"],
            [
                [
                    item.get("logged_at") or item.get("created_at"),
                    item.get("task_id"),
                    item.get("status"),
                    item.get("exit_code"),
                    item.get("risk_level"),
                    item.get("output_file"),
                ]
                for item in report["latest_codex_cli_runs"]
            ],
        )
    else:
        lines.append("- none")

    lines.extend(["", "## Tool Registry Entries", ""])
    if report["tool_registry_entries"]:
        append_table(
            lines,
            ["Name", "Risk", "Confirm", "Audit", "Command"],
            [
                [
                    item.get("name"),
                    item.get("risk"),
                    item.get("requires_confirmation"),
                    item.get("writes_audit_log"),
                    item.get("command"),
                ]
                for item in report["tool_registry_entries"]
            ],
        )
    else:
        lines.append("- none")

    lines.extend(["", "## Current Harness Progress", ""])
    lines.append("Percentages are artifact-backed milestone coverage for this harness, not AGI or ASI capability.")
    lines.append("")
    append_table(
        lines,
        ["Layer", "Progress", "Evidence", "Gaps"],
        [
            [row["layer"], f"{row['percent']}%", row["evidence"] or "none", row["gaps"] or "none"]
            for row in report["harness_progress"]
        ],
    )

    stage6c = report["stage6c_patch_proposal"]
    lines.extend(["", "## Stage 6c Patch Proposal Evidence", ""])
    lines.extend(
        [
            f"- Status: {stage6c['status']}",
            f"- Audit path: {stage6c['path']}",
            f"- Cycles completed: {md_cell(stage6c.get('cycles_completed'))}",
            f"- Decision: {stage6c.get('decision') or ''}",
            f"- Risk classification: {stage6c.get('risk_classification') or ''}",
            f"- Risk reasons: {md_cell(stage6c.get('risk_reasons') or [])}",
            f"- Proposal path: {stage6c.get('proposal_path') or ''}",
            f"- Patch path: {stage6c.get('patch_path') or ''}",
            f"- Human approval required: {md_cell(stage6c.get('human_approval_required'))}",
            f"- Auto applied: {md_cell(stage6c.get('auto_applied'))}",
            f"- Changed files: {md_cell(stage6c.get('changed_files')) if stage6c.get('changed_files') else '[]'}",
            f"- Tests selected: {md_cell(stage6c.get('tests_selected') or [])}",
        ]
    )

    lines.extend(["", "## Unresolved Failures", ""])
    if report["unresolved_failures"]:
        append_table(
            lines,
            ["Time", "Task", "Status", "Exit", "Source", "Reason"],
            [
                [
                    item.get("logged_at") or item.get("created_at"),
                    item.get("task_id"),
                    item.get("status"),
                    item.get("exit_code"),
                    item.get("source"),
                    item.get("reason"),
                ]
                for item in report["unresolved_failures"]
            ],
        )
    else:
        lines.append("- none")

    lines.extend(["", "## Codex Delegate Memory Summary", ""])
    lines.extend(
        [
            f"- Total memory runs: {report['total_runs']}",
            f"- Passed memory runs: {report['passed_runs']}",
            f"- Failed memory runs: {report['failed_runs']}",
            f"- Memory pass rate: {report['pass_rate']:.2%}",
            "",
            "Failure classes:",
        ]
    )
    if report["failure_classes"]:
        for name, count in report["failure_classes"].items():
            lines.append(f"- {name}: {count}")
    else:
        lines.append("- none: 0")

    lines.extend(["", "## Memory DB Stats", ""])
    memory_db = report["memory_database"]
    lines.extend(
        [
            f"- Path: {memory_db['path']}",
            f"- Exists: {md_cell(memory_db['exists'])}",
            f"- Schema version: {memory_db.get('schema_version') or ''}",
            f"- Total SQLite records: {memory_db['total_records']}",
            f"- SQLite agent runs: {memory_db['agent_runs']}",
            f"- SQLite failures: {memory_db['failures']}",
        ]
    )
    if memory_db.get("error"):
        lines.append(f"- Error: {memory_db['error']}")

    lines.extend(["", "SQLite failure classes:"])
    if memory_db["failure_classes"]:
        for name, count in memory_db["failure_classes"].items():
            lines.append(f"- {name}: {count}")
    else:
        lines.append("- none: 0")

    lines.extend(["", "Latest SQLite memory records:"])
    if memory_db["latest_records"]:
        append_table(
            lines,
            ["Time", "Task", "Type", "Status", "Score", "Failure", "Output"],
            [
                [
                    item.get("created_at"),
                    item.get("task_id"),
                    item.get("record_type"),
                    item.get("status"),
                    item.get("score"),
                    item.get("failure_class"),
                    item.get("output_file"),
                ]
                for item in memory_db["latest_records"]
            ],
        )
    else:
        lines.append("- none")

    lines.extend(["", "## Next Recommended Tasks", ""])
    for task in report["next_recommended_tasks"]:
        lines.append(f"- {task}")
    return "\n".join(lines) + "\n"


def resolve_output_path(root: Path, output: str | Path | None = None) -> Path:
    root_path = root.resolve(strict=False)
    output_path = Path(output) if output is not None else root_path / REPORT_RELATIVE_PATH
    if not output_path.is_absolute():
        output_path = root_path / output_path
    output_path = output_path.resolve(strict=False)
    if not output_path.is_relative_to(root_path):
        raise ValueError(f"output path must stay under {root_path}: {output_path}")
    return output_path


def write_report(report: dict[str, Any], *, root: Path | str = ROOT, output: str | Path | None = None) -> Path:
    root_path = Path(root).resolve(strict=False)
    output_path = resolve_output_path(root_path, output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(format_markdown(report), encoding="utf-8")
    return output_path


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate the ASI Kernel progress report.")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--output", default=str(REPORT_RELATIVE_PATH), help="Markdown output path under the root")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of Markdown and do not write the report")
    parser.add_argument("--newest-limit", type=int, default=5)
    parser.add_argument("--stdout", action="store_true", help="Print Markdown after writing the report")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    report = build_report(root=args.root, newest_limit=args.newest_limit)
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        output_path = write_report(report, root=args.root, output=args.output)
        if args.stdout:
            print(format_markdown(report), end="")
        else:
            print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
