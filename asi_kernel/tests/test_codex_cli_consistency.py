from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path("D:/Sandbox/asi_kernel")
CODEX_CLI_DIR = ROOT / "tools" / "codex_cli"
WRAPPER_PATH = CODEX_CLI_DIR / "run_codex_exec.py"
SCHEMA_PATH = CODEX_CLI_DIR / "codex_task.schema.json"
TEMPLATE_PATH = CODEX_CLI_DIR / "codex_task_template.json"
REGISTRY_PATH = ROOT / "tools" / "tool_registry.json"
OUTPUT_ROOT = ROOT / "logs" / "codex_cli_outputs"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_wrapper():
    spec = importlib.util.spec_from_file_location("run_codex_exec_consistency", WRAPPER_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def validate_schema_subset(instance: dict[str, Any], schema: dict[str, Any]) -> None:
    assert schema["type"] == "object"
    assert schema.get("additionalProperties") is False
    assert sorted(set(instance) - set(schema["properties"])) == []
    assert sorted(field for field in schema["required"] if field not in instance) == []

    for field, field_schema in schema["properties"].items():
        if field not in instance:
            continue

        value = instance[field]
        expected_type = field_schema.get("type")
        if expected_type == "string":
            assert isinstance(value, str), field
            if "minLength" in field_schema:
                assert len(value) >= field_schema["minLength"], field
            if "maxLength" in field_schema:
                assert len(value) <= field_schema["maxLength"], field
            if "pattern" in field_schema:
                assert re.fullmatch(field_schema["pattern"], value), field
        elif expected_type == "integer":
            assert isinstance(value, int) and not isinstance(value, bool), field
            if "minimum" in field_schema:
                assert value >= field_schema["minimum"], field
            if "maximum" in field_schema:
                assert value <= field_schema["maximum"], field
        elif expected_type == "array":
            assert isinstance(value, list), field
            item_schema = field_schema.get("items", {})
            if item_schema.get("type") == "string":
                assert all(isinstance(item, str) for item in value), field
                min_length = item_schema.get("minLength")
                if min_length is not None:
                    assert all(len(item) >= min_length for item in value), field
        else:
            raise AssertionError(f"unsupported schema type for {field}: {expected_type}")

        if "const" in field_schema:
            assert value == field_schema["const"], field
        if "enum" in field_schema:
            assert value in field_schema["enum"], field


def codex_delegate_entries() -> list[dict[str, Any]]:
    registry = load_json(REGISTRY_PATH)
    return [entry for entry in registry if entry.get("name") == "codex_cli_delegate"]


def sample_task() -> dict[str, Any]:
    return {
        "task_id": "consistency_check",
        "prompt": "Inspect README.md only. Do not edit files.",
        "workspace": str(ROOT),
        "expected_outputs": ["logs/codex_cli_outputs/consistency_check.md"],
        "validation_commands": ["python tools\\codex_cli\\run_codex_exec.py --help"],
        "max_duration_sec": 5,
        "max_recursion_depth": 0,
        "risk_level": "low",
    }


def test_codex_task_template_validates_against_schema():
    validate_schema_subset(load_json(TEMPLATE_PATH), load_json(SCHEMA_PATH))


def test_tool_registry_has_exactly_one_codex_cli_delegate_entry():
    assert len(codex_delegate_entries()) == 1


def test_codex_cli_delegate_allowed_paths_are_bounded_to_asi_kernel():
    [delegate] = codex_delegate_entries()

    assert delegate["allowed_paths"] == ["D:\\Sandbox\\asi_kernel"]


def test_codex_cli_delegate_forbidden_flags_match_wrapper_constant():
    wrapper = load_wrapper()
    [delegate] = codex_delegate_entries()

    assert delegate["forbidden_flags"] == list(wrapper.FORBIDDEN_FLAGS)


def test_codex_cli_delegate_registry_command_remains_bounded_wrapper():
    [delegate] = codex_delegate_entries()

    assert delegate["command"] == "python tools\\codex_cli\\run_codex_exec.py --task <task_json>"


def test_codex_cli_delegate_requires_confirmation():
    [delegate] = codex_delegate_entries()

    assert delegate["requires_confirmation"] is True


def test_codex_cli_delegate_writes_audit_log():
    [delegate] = codex_delegate_entries()

    assert delegate["writes_audit_log"] is True


def test_build_codex_command_excludes_forbidden_bypass_modes():
    wrapper = load_wrapper()
    command = wrapper.build_codex_command(sample_task(), OUTPUT_ROOT / "consistency_check.md")
    command_text = " ".join(command)

    assert "--yolo" not in command
    assert "--dangerously-bypass-approvals-and-sandbox" not in command
    assert "danger-full-access" not in command_text


def test_build_codex_command_does_not_place_ask_for_approval_after_exec():
    wrapper = load_wrapper()
    command = wrapper.build_codex_command(sample_task(), OUTPUT_ROOT / "consistency_check.md")
    exec_index = command.index("exec")

    assert "--ask-for-approval" not in command[exec_index + 1 :]


def test_build_codex_command_places_global_ask_for_approval_before_exec_if_used():
    wrapper = load_wrapper()
    command = wrapper.build_codex_command(sample_task(), OUTPUT_ROOT / "consistency_check.md")
    exec_index = command.index("exec")

    if "--ask-for-approval" in command:
        approval_index = command.index("--ask-for-approval")
        assert approval_index < exec_index
        assert command[approval_index + 1] == "on-request"


def test_build_codex_command_places_config_approval_policy_after_exec_if_used():
    wrapper = load_wrapper()
    command = wrapper.build_codex_command(sample_task(), OUTPUT_ROOT / "consistency_check.md")
    exec_index = command.index("exec")

    if "-c" in command:
        config_index = command.index("-c")
        assert config_index > exec_index
        assert command[config_index + 1] == 'approval_policy="on-request"'


def test_build_codex_command_sets_a_working_approval_policy_form():
    wrapper = load_wrapper()
    command = wrapper.build_codex_command(sample_task(), OUTPUT_ROOT / "consistency_check.md")

    assert "--ask-for-approval" in command or "-c" in command


def test_output_path_for_stays_under_codex_cli_outputs():
    wrapper = load_wrapper()

    output_path = wrapper.output_path_for("consistency_check")

    assert output_path.is_relative_to(OUTPUT_ROOT)
    assert output_path.name == "consistency_check.md"
