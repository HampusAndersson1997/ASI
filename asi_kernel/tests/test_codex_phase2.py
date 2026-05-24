from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path
from types import SimpleNamespace


ROOT = Path("D:/Sandbox/asi_kernel")


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def base_task(task_id: str, **overrides):
    task = {
        "task_id": task_id,
        "prompt": "Inspect README.md only. Do not edit files.",
        "workspace": str(ROOT),
        "expected_outputs": [f"logs/codex_cli_outputs/{task_id}.md"],
        "validation_commands": ["python -c \"print('validation ok')\""],
        "max_duration_sec": 10,
        "max_recursion_depth": 0,
        "risk_level": "low",
    }
    task.update(overrides)
    return task


def read_jsonl(path: Path):
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class FakeRunner:
    def __init__(self, validation_exit_code: int = 0):
        self.validation_exit_code = validation_exit_code
        self.calls: list[object] = []

    def __call__(self, command, *, cwd=None, text=True, capture_output=True, timeout=None):
        self.calls.append(command)
        command_parts = [str(part) for part in command] if isinstance(command, list) else [str(command)]
        command_text = " ".join(command_parts)

        if "codex" in command_text and "--output-last-message" in command_text:
            if "--output-last-message" in command_parts:
                output_flag_index = command_parts.index("--output-last-message")
                output_path = Path(command_parts[output_flag_index + 1])
            else:
                marker = "'--output-last-message' '"
                assert marker in command_text
                output_path_text = command_text.split(marker, 1)[1].split("'", 1)[0]
                output_path = Path(output_path_text)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text("delegated output\n", encoding="utf-8")
            return SimpleNamespace(returncode=0, stdout="codex ok", stderr="")

        if self.validation_exit_code == 0:
            return SimpleNamespace(returncode=0, stdout=f"ran {command_text}", stderr="")
        return SimpleNamespace(returncode=self.validation_exit_code, stdout="", stderr="validation failed")


def test_score_result_runs_validation_and_scores_pass(tmp_path):
    scorer = load_module("score_result", ROOT / "tools" / "python" / "score_result.py")
    output_path = tmp_path / "logs" / "codex_cli_outputs" / "score-pass.md"
    output_path.parent.mkdir(parents=True)
    output_path.write_text("delegated output\n", encoding="utf-8")
    task = {
        "task_id": "score-pass",
        "workspace": str(tmp_path),
        "validation_commands": ["python -c \"print('ok')\""],
        "expected_outputs": [str(output_path)],
    }
    run_record = {"task_id": "score-pass", "status": "completed", "exit_code": 0, "output_file": str(output_path)}
    fake = FakeRunner(validation_exit_code=0)

    evaluation = scorer.score_result(task, run_record, executor=fake, root=tmp_path)

    assert evaluation["passed"] is True
    assert evaluation["score"] == 1.0
    assert evaluation["validation_results"][0]["exit_code"] == 0
    assert "python -c" in evaluation["validation_results"][0]["command"]


def test_classify_failure_identifies_failed_validation():
    classifier = load_module("classify_failure", ROOT / "tools" / "python" / "classify_failure.py")
    run_record = {"task_id": "failed-validation", "status": "validation_failed", "exit_code": 1}
    evaluation = {
        "passed": False,
        "failure_reasons": ["validation command failed"],
        "validation_results": [{"command": "python -m pytest", "exit_code": 1, "stderr": "failed"}],
    }

    failure = classifier.classify_failure(run_record, evaluation)

    assert failure["failure_class"] == "validation_failed"
    assert failure["failed_validation_commands"] == ["python -m pytest"]


def test_memory_init_and_save_records_pass_and_failure(tmp_path):
    init_memory = load_module("init_memory", ROOT / "tools" / "memory" / "init_memory.py")
    save_agent_run = load_module("save_agent_run", ROOT / "tools" / "memory" / "save_agent_run.py")
    paths = init_memory.init_memory(root=tmp_path)

    assert Path(paths["agent_runs"]).exists()
    assert Path(paths["failures"]).exists()

    task = {"task_id": "memory-pass", "risk_level": "low", "workspace": str(tmp_path)}
    run_record = {"task_id": "memory-pass", "status": "passed", "exit_code": 0, "output_file": "out.md"}
    passed = {"passed": True, "score": 1.0, "validation_results": []}
    pass_result = save_agent_run.save_agent_result(task, run_record, passed, root=tmp_path)

    failed_eval = {
        "passed": False,
        "score": 0.0,
        "failure_reasons": ["validation command failed"],
        "validation_results": [{"command": "python -m pytest", "exit_code": 1}],
    }
    fail_result = save_agent_run.save_agent_result(
        {"task_id": "memory-fail", "risk_level": "low", "workspace": str(tmp_path)},
        {"task_id": "memory-fail", "status": "validation_failed", "exit_code": 1, "output_file": "out.md"},
        failed_eval,
        root=tmp_path,
    )

    assert pass_result["record_type"] == "agent_run"
    assert fail_result["record_type"] == "failure"
    assert read_jsonl(tmp_path / "memory" / "agent_runs.jsonl")[0]["task_id"] == "memory-pass"
    assert read_jsonl(tmp_path / "memory" / "failures.jsonl")[0]["failure_class"] == "validation_failed"


def test_wrapper_non_dry_run_logs_validation_and_agent_memory():
    wrapper = load_module("run_codex_exec", ROOT / "tools" / "codex_cli" / "run_codex_exec.py")
    task_id = f"phase2_pass_{time.time_ns()}"
    task = base_task(task_id)
    fake = FakeRunner(validation_exit_code=0)

    result = wrapper.run_task(task, dry_run=False, executor=fake)

    assert result["status"] == "passed"
    assert result["evaluation"]["passed"] is True
    assert len(result["evaluation"]["validation_results"]) == 1
    assert result["command"][0] == "codex"
    assert "powershell" in str(fake.calls[0][0]).lower() or "pwsh" in str(fake.calls[0][0]).lower()
    assert "powershell" in str(fake.calls[1][0]).lower() or "pwsh" in str(fake.calls[1][0]).lower()
    assert any(record["task_id"] == task_id for record in read_jsonl(ROOT / "logs" / "codex_cli_runs.jsonl"))
    assert any(record["task_id"] == task_id for record in read_jsonl(ROOT / "memory" / "agent_runs.jsonl"))


def test_wrapper_resolves_codex_cli_through_powershell():
    wrapper = load_module("run_codex_exec", ROOT / "tools" / "codex_cli" / "run_codex_exec.py")
    command = wrapper.build_codex_command(base_task("phase2_resolution"), ROOT / "logs" / "codex_cli_outputs" / "phase2_resolution.md")

    execution_command = wrapper.codex_execution_command(command)

    assert "powershell" in str(execution_command[0]).lower() or "pwsh" in str(execution_command[0]).lower()
    assert "codex" in " ".join(str(part) for part in execution_command)


def test_wrapper_places_approval_policy_before_exec_for_current_cli():
    wrapper = load_module("run_codex_exec", ROOT / "tools" / "codex_cli" / "run_codex_exec.py")
    command = wrapper.build_codex_command(base_task("phase2_approval_order"), ROOT / "logs" / "codex_cli_outputs" / "phase2_approval_order.md")

    assert command.index("--ask-for-approval") < command.index("exec")


def test_wrapper_failed_validation_creates_failure_memory():
    wrapper = load_module("run_codex_exec", ROOT / "tools" / "codex_cli" / "run_codex_exec.py")
    task_id = f"phase2_fail_{time.time_ns()}"
    task = base_task(task_id)
    fake = FakeRunner(validation_exit_code=7)

    result = wrapper.run_task(task, dry_run=False, executor=fake)

    assert result["status"] == "validation_failed"
    assert result["exit_code"] == 7
    assert result["evaluation"]["passed"] is False
    failures = [record for record in read_jsonl(ROOT / "memory" / "failures.jsonl") if record["task_id"] == task_id]
    assert failures
    assert failures[-1]["failure_class"] == "validation_failed"


def test_dashboard_reports_runs_pass_rate_failures_and_outputs(tmp_path):
    dashboard = load_module("progress_report", ROOT / "dashboards" / "progress_report.py")
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir(parents=True)
    (memory_dir / "agent_runs.jsonl").write_text(
        json.dumps({"task_id": "pass-1", "created_at": "2026-05-24T01:00:00+00:00", "output_file": "out/pass.md"}) + "\n",
        encoding="utf-8",
    )
    (memory_dir / "failures.jsonl").write_text(
        json.dumps({"task_id": "fail-1", "created_at": "2026-05-24T02:00:00+00:00", "failure_class": "validation_failed", "output_file": "out/fail.md"}) + "\n"
        + json.dumps({"task_id": "fail-2", "created_at": "2026-05-24T03:00:00+00:00", "failure_class": "timeout", "output_file": "out/timeout.md"}) + "\n",
        encoding="utf-8",
    )

    report = dashboard.build_report(root=tmp_path)

    assert report["total_runs"] == 3
    assert report["passed_runs"] == 1
    assert report["pass_rate"] == 1 / 3
    assert report["failure_classes"] == {"validation_failed": 1, "timeout": 1}
    assert report["newest_outputs"][0]["task_id"] == "fail-2"


def test_dashboard_builds_required_progress_report_sections(tmp_path):
    dashboard = load_module("progress_report_required", ROOT / "dashboards" / "progress_report.py")
    (tmp_path / "logs").mkdir(parents=True)
    (tmp_path / "tests").mkdir(parents=True)
    (tmp_path / "tools").mkdir(parents=True)
    (tmp_path / "skills" / "codex_cli_tool").mkdir(parents=True)
    (tmp_path / "verification").mkdir(parents=True)

    (tmp_path / "tests" / "test_sample.py").write_text(
        "def test_one():\n"
        "    assert True\n\n"
        "class TestSample:\n"
        "    def test_two(self):\n"
        "        assert True\n",
        encoding="utf-8",
    )
    (tmp_path / "logs" / "codex_cli_preflight.json").write_text(
        json.dumps(
            {
                "checked_at": "2026-05-24T02:00:00+00:00",
                "ready": True,
                "current_path_ok": True,
                "checks": {
                    "codex_version": {"available": True, "stdout": "codex-cli 0.133.0"},
                    "node_version": {"available": True, "stdout": "v24.15.0"},
                },
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "logs" / "codex_cli_runs.jsonl").write_text(
        json.dumps({"task_id": "older-pass", "logged_at": "2026-05-24T01:00:00+00:00", "status": "passed", "exit_code": 0}) + "\n"
        + json.dumps(
            {
                "task_id": "latest-fail",
                "logged_at": "2026-05-24T03:00:00+00:00",
                "status": "validation_failed",
                "exit_code": 7,
                "stderr": "validation failed",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "tools" / "tool_registry.json").write_text(
        json.dumps(
            [
                {
                    "name": "codex_cli_delegate",
                    "purpose": "Delegate bounded work.",
                    "risk": "medium",
                    "command": "python tools\\codex_cli\\run_codex_exec.py --task <task_json>",
                    "requires_confirmation": True,
                    "writes_audit_log": True,
                }
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "skills" / "codex_cli_tool" / "SKILL.md").write_text("# Codex CLI Tool\n", encoding="utf-8")
    (tmp_path / "verification" / "evidence_ledger.md").write_text("# Evidence Ledger\n", encoding="utf-8")

    report = dashboard.build_report(
        root=tmp_path,
        newest_limit=2,
        timestamp="2026-05-24T04:00:00+00:00",
    )
    markdown = dashboard.format_markdown(report)

    assert report["timestamp"] == "2026-05-24T04:00:00+00:00"
    assert report["tests"]["test_files"] == 1
    assert report["tests"]["test_count"] == 2
    assert report["codex_cli_preflight"]["ready"] is True
    assert report["latest_codex_cli_runs"][0]["task_id"] == "latest-fail"
    assert report["tool_registry_entries"][0]["name"] == "codex_cli_delegate"
    assert report["unresolved_failures"][0]["task_id"] == "latest-fail"
    assert {row["layer"] for row in report["harness_progress"]} == set(dashboard.HARNESS_LAYERS)
    for heading in [
        "## Test Count Summary",
        "## Codex CLI Preflight",
        "## Latest Codex CLI Runs",
        "## Tool Registry Entries",
        "## Current Harness Progress",
        "## Unresolved Failures",
        "## Next Recommended Tasks",
    ]:
        assert heading in markdown

    output_path = dashboard.write_report(
        report,
        root=tmp_path,
    )

    assert output_path == tmp_path / "dashboards" / "progress_report.md"
    assert output_path.exists()
