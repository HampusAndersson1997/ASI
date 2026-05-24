from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "safety" / "research_policy.json"


class PolicyError(ValueError):
    pass


def load_policy(path: Path = POLICY_PATH) -> dict:
    if not path.exists():
        raise PolicyError(f"Missing policy file: {path}")

    with path.open("r", encoding="utf-8") as f:
        policy = json.load(f)

    required = [
        "max_cycles_hard_limit",
        "timeout_seconds",
        "network_allowed",
        "secrets_allowed",
        "destructive_actions_allowed",
        "auto_apply_patches",
        "allowed_commands",
        "forbidden_fragments",
    ]

    for key in required:
        if key not in policy:
            raise PolicyError(f"Policy missing required key: {key}")

    return policy


def normalize_command(command: list[str]) -> list[str]:
    return [str(part).replace("\\", "/") for part in command]


def command_is_allowed(command: list[str], policy: dict) -> bool:
    normalized = normalize_command(command)
    allowed = [normalize_command(cmd) for cmd in policy["allowed_commands"]]
    joined = " ".join(command)

    for fragment in policy["forbidden_fragments"]:
        if fragment.lower() in joined.lower():
            return False

    return normalized in allowed


def validate_command(command: list[str], policy: dict) -> None:
    if not command:
        raise PolicyError("Empty command blocked")

    if not command_is_allowed(command, policy):
        raise PolicyError(f"Command blocked by safety policy: {command}")


def validate_cycles(cycles: int, policy: dict) -> None:
    hard_limit = int(policy["max_cycles_hard_limit"])

    if cycles < 1:
        raise PolicyError("cycles must be >= 1")

    if cycles > hard_limit:
        raise PolicyError(f"cycles={cycles} exceeds hard limit={hard_limit}")


def assert_safe_policy(policy: dict) -> None:
    if policy.get("network_allowed") is not False:
        raise PolicyError("network must remain disabled for Stage 6a")

    if policy.get("secrets_allowed") is not False:
        raise PolicyError("secrets must remain disabled for Stage 6a")

    if policy.get("destructive_actions_allowed") is not False:
        raise PolicyError("destructive actions must remain disabled for Stage 6a")

    if policy.get("auto_apply_patches") is not False:
        raise PolicyError("auto patch application must remain disabled for Stage 6a")
