from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUDIT_PATH = ROOT / "logs" / "research" / "autonomous_improvement_runs.jsonl"
MAX_CYCLES = 3

IGNORED_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    "logs",
}

SAFE_SMOKE_CODE = "print('stage6b-smoke-ok')"


@dataclass(frozen=True)
class CommandResult:
    command: list[str]
    exit_code: int
    stdout: str
    stderr: str
    duration_sec: float
    timed_out: bool = False


@dataclass(frozen=True)
class ImprovementCycle:
    cycle: int
    suite: str
    hypothesis: str
    proposed_change: str
    safety_policy: dict[str, Any]
    command_result: CommandResult
    decision: str
    human_approval_required: bool
    auto_applied: bool


def stable_file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def repo_snapshot() -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        if any(part in IGNORED_DIRS for part in rel.parts):
            continue
        snapshot[str(rel).replace("\\", "/")] = stable_file_hash(path)
    return snapshot


def changed_files(before: dict[str, str], after: dict[str, str]) -> list[str]:
    keys = set(before) | set(after)
    return sorted(k for k in keys if before.get(k) != after.get(k))


def is_allowed_command(command: list[str]) -> bool:
    if not command:
        return False

    exe_name = Path(command[0]).name.lower()
    if not exe_name.startswith("python"):
        return False

    allowed_smoke = ["-c", SAFE_SMOKE_CODE]
    allowed_pytest = ["-B", "-m", "pytest", "-p", "no:cacheprovider", "-q"]

    tail = command[1:]
    return tail == allowed_smoke or tail == allowed_pytest


def run_allowed(command: list[str], timeout_sec: int) -> CommandResult:
    if not is_allowed_command(command):
        raise PermissionError(f"Blocked non-allowlisted command: {command!r}")

    env = os.environ.copy()
    env["PYTHONNOUSERSITE"] = "1"
    env["ASI_KERNEL_NO_NETWORK"] = "1"

    started = time.time()
    try:
        proc = subprocess.run(
            command,
            cwd=str(ROOT),
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_sec,
            shell=False,
            check=False,
        )
        return CommandResult(
            command=command,
            exit_code=proc.returncode,
            stdout=proc.stdout[-4000:],
            stderr=proc.stderr[-4000:],
            duration_sec=round(time.time() - started, 4),
            timed_out=False,
        )
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            command=command,
            exit_code=124,
            stdout=(exc.stdout or "")[-4000:] if isinstance(exc.stdout, str) else "",
            stderr=(exc.stderr or "")[-4000:] if isinstance(exc.stderr, str) else "",
            duration_sec=round(time.time() - started, 4),
            timed_out=True,
        )


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def build_cycle(cycle_index: int, suite: str, timeout_sec: int, run_pytest: bool) -> ImprovementCycle:
    command = [sys.executable, "-B", "-m", "pytest", "-p", "no:cacheprovider", "-q"] if run_pytest else [
        sys.executable,
        "-c",
        SAFE_SMOKE_CODE,
    ]

    result = run_allowed(command, timeout_sec=timeout_sec)

    decision = "recommend_review" if result.exit_code == 0 else "blocked_or_failed"

    return ImprovementCycle(
        cycle=cycle_index,
        suite=suite,
        hypothesis=(
            "A safe improvement loop should generate an improvement candidate, "
            "run a bounded allowlisted verification command, write audit evidence, "
            "and avoid applying code changes without human approval."
        ),
        proposed_change=(
            "No code change auto-applied. Candidate is evidence-only until a human approves "
            "a concrete patch in a separate step."
        ),
        safety_policy={
            "max_cycles": MAX_CYCLES,
            "shell": False,
            "network": "disabled by policy/environment flag",
            "secrets": "not read",
            "auto_apply_changes": False,
            "human_approval_required": True,
            "allowlisted_commands_only": True,
        },
        command_result=result,
        decision=decision,
        human_approval_required=True,
        auto_applied=False,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Stage 6b safe autonomous improvement-loop scaffold."
    )
    parser.add_argument("--cycles", type=int, default=1)
    parser.add_argument("--suite", default="smoke")
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--audit-path", default=str(DEFAULT_AUDIT_PATH))
    parser.add_argument(
        "--run-pytest",
        action="store_true",
        help="Use the allowlisted full pytest command as the bounded verification command.",
    )
    args = parser.parse_args(argv)

    if args.cycles < 1:
        print(json.dumps({"ok": False, "error": "cycles must be >= 1"}), file=sys.stderr)
        return 2

    if args.cycles > MAX_CYCLES:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": f"cycles exceeds hard safety limit of {MAX_CYCLES}",
                    "cycles_requested": args.cycles,
                    "max_cycles": MAX_CYCLES,
                }
            ),
            file=sys.stderr,
        )
        return 2

    audit_path = Path(args.audit_path)
    before = repo_snapshot()
    cycles: list[ImprovementCycle] = []

    started = time.time()

    for i in range(1, args.cycles + 1):
        cycle = build_cycle(i, suite=args.suite, timeout_sec=args.timeout, run_pytest=args.run_pytest)
        cycles.append(cycle)
        append_jsonl(
            audit_path,
            {
                "stage": "6b",
                "event": "improvement_cycle",
                "timestamp_unix": time.time(),
                "root": str(ROOT),
                "cycle": asdict(cycle),
            },
        )

    after = repo_snapshot()
    changed = changed_files(before, after)

    ok = all(c.command_result.exit_code == 0 for c in cycles) and changed == []

    summary = {
        "ok": ok,
        "stage": "6b",
        "name": "safe autonomous improvement-loop scaffold",
        "cycles_requested": args.cycles,
        "cycles_completed": len(cycles),
        "suite": args.suite,
        "audit_path": str(audit_path),
        "changed_files": changed,
        "auto_applied": False,
        "human_approval_required": True,
        "duration_sec": round(time.time() - started, 4),
        "cycle_decisions": [c.decision for c in cycles],
        "command_exit_codes": [c.command_result.exit_code for c in cycles],
    }

    append_jsonl(
        audit_path,
        {
            "stage": "6b",
            "event": "improvement_loop_summary",
            "timestamp_unix": time.time(),
            "summary": summary,
        },
    )

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
