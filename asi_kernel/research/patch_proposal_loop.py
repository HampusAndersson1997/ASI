from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUDIT_PATH = ROOT / "logs" / "research" / "patch_proposal_runs.jsonl"
DEFAULT_PROPOSAL_DIR = ROOT / "logs" / "research" / "patch_proposals"
MAX_CYCLES = 3

IGNORED_SNAPSHOT_PARTS = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    "logs",
}

LOW_RISK_PREFIXES = (
    "docs/",
    "tests/",
    "dashboards/",
    "verification/",
)
LOW_RISK_FILES = {
    "README.md",
}
MEDIUM_RISK_PREFIXES = (
    "research/",
    "safety/",
    "tools/",
    "loop/",
    "benchmarks/",
)
HIGH_RISK_FRAGMENTS = (
    ".env",
    "codex exec",
    "subprocess",
    "requests",
    "urllib",
    "http://",
    "https://",
    "socket",
    "supabase",
    "remove-item",
    "rm -rf",
    "shutil.rmtree",
    ".unlink(",
    "os.remove",
    "rmdir",
)

FULL_PYTEST_COMMAND = r".venv\Scripts\python.exe -B -m pytest -p no:cacheprovider -q"


@dataclass(frozen=True)
class PatchCandidate:
    title: str
    rationale: str
    target_files: list[str]
    patch_text: str


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def stable_file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def production_snapshot() -> dict[str, str]:
    snapshot: dict[str, str] = {}
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        if path.name == ".env":
            continue
        if any(part in IGNORED_SNAPSHOT_PARTS for part in rel.parts):
            continue
        snapshot[str(rel).replace("\\", "/")] = stable_file_hash(path)
    return snapshot


def changed_files(before: dict[str, str], after: dict[str, str]) -> list[str]:
    keys = set(before) | set(after)
    return sorted(k for k in keys if before.get(k) != after.get(k))


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def patch_sha256(patch_text: str) -> str:
    return hashlib.sha256(patch_text.encode("utf-8")).hexdigest()


def build_safe_boundary_patch() -> PatchCandidate:
    target = "verification/safe_autonomy_boundary.md"
    after_lines = [
        "# Safe Autonomy Boundary",
        "",
        "- Stage 6c patch proposals remain review-only until human approval is recorded.",
        "- Generated patch artifacts are reversible unified diffs and are never auto-applied by the proposal loop.",
    ]
    patch_lines = list(
        difflib.unified_diff(
            [],
            after_lines,
            fromfile="/dev/null",
            tofile=f"b/{target}",
            n=3,
            lineterm="",
        )
    )
    return PatchCandidate(
        title="Document the safe autonomy review boundary",
        rationale=(
            "The dashboard currently treats verification/safe_autonomy_boundary.md as evidence for "
            "the Safety tools layer. This proposed docs-only patch adds that boundary without changing "
            "runtime behavior."
        ),
        target_files=[target],
        patch_text="\n".join(patch_lines) + "\n",
    )


def path_class(path: str) -> str:
    normalized = path.replace("\\", "/")
    if normalized in LOW_RISK_FILES or normalized.endswith(".md") or normalized.startswith(LOW_RISK_PREFIXES):
        return "low"
    if normalized.startswith(MEDIUM_RISK_PREFIXES):
        return "medium"
    return "unknown"


def classify_risk(touched_files: list[str], *, patch_text: str) -> dict[str, Any]:
    reasons: list[str] = []
    normalized_patch = patch_text.lower()

    high_fragments = [fragment for fragment in HIGH_RISK_FRAGMENTS if fragment in normalized_patch]
    if high_fragments:
        reasons.append("patch text contains high-risk fragment(s): " + ", ".join(high_fragments))

    classes = {path: path_class(path) for path in touched_files}
    unknown_paths = [path for path, klass in classes.items() if klass == "unknown"]
    if unknown_paths:
        reasons.append("patch touches unknown path(s): " + ", ".join(unknown_paths))

    if len(touched_files) > 3:
        reasons.append("patch touches more than three files, treated as broad refactor risk")

    if reasons:
        return {"risk_classification": "high", "risk_reasons": reasons}

    if all(klass == "low" for klass in classes.values()):
        return {
            "risk_classification": "low",
            "risk_reasons": ["docs/tests/dashboard-only or small non-runtime-safe change"],
        }

    if all(klass in {"low", "medium"} for klass in classes.values()):
        return {
            "risk_classification": "medium",
            "risk_reasons": ["runtime logic change under allowlisted path"],
        }

    return {"risk_classification": "high", "risk_reasons": ["unable to classify patch target path(s)"]}


def select_tests(touched_files: list[str]) -> list[str]:
    commands: list[str] = []
    normalized = [path.replace("\\", "/") for path in touched_files]

    if any(path.startswith("verification/") for path in normalized):
        commands.append(
            r".venv\Scripts\python.exe -B -m pytest -p no:cacheprovider -q tests\test_safe_autonomous_researcher.py"
        )
    if any(path.startswith("dashboards/") for path in normalized):
        commands.append(
            r".venv\Scripts\python.exe -B -m pytest -p no:cacheprovider -q tests\test_stage6c_patch_proposal_loop.py"
        )
    if any(path.startswith("research/") for path in normalized):
        commands.append(
            r".venv\Scripts\python.exe -B -m pytest -p no:cacheprovider -q tests\test_stage6c_patch_proposal_loop.py"
        )

    commands.append(FULL_PYTEST_COMMAND)
    return list(dict.fromkeys(commands))


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_proposal(
    *,
    candidate: PatchCandidate,
    cycle_index: int,
    cycles_completed: int,
    suite: str,
    proposal_path: Path,
    patch_path: Path,
    production_changed_files: list[str],
) -> dict[str, Any]:
    risk = classify_risk(candidate.target_files, patch_text=candidate.patch_text)
    tests_selected = select_tests(candidate.target_files)
    return {
        "stage": "6c",
        "ok": production_changed_files == [],
        "cycle": cycle_index,
        "cycles_completed": cycles_completed,
        "suite": suite,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "proposal_path": str(proposal_path),
        "patch_path": str(patch_path),
        "patch_sha256": patch_sha256(candidate.patch_text),
        "title": candidate.title,
        "rationale": candidate.rationale,
        "target_files": candidate.target_files,
        "risk_classification": risk["risk_classification"],
        "risk_reasons": risk["risk_reasons"],
        "tests_selected": tests_selected,
        "human_approval_required": True,
        "auto_applied": False,
        "changed_files": production_changed_files,
        "decision": "recommend_review" if production_changed_files == [] else "blocked_or_failed",
        "review_notes": [
            "Patch artifact is a proposal only and has not been applied to the working tree.",
            "Apply only after human review, then run the selected verification commands.",
        ],
    }


def run_cycle(cycle_index: int, cycles_completed: int, suite: str, proposal_dir: Path) -> dict[str, Any]:
    candidate = build_safe_boundary_patch()
    stamp = utc_timestamp()
    stem = f"stage6c-{stamp}-c{cycle_index}"
    patch_path = proposal_dir / f"{stem}.patch"
    proposal_path = proposal_dir / f"{stem}.json"

    before = production_snapshot()
    write_text(patch_path, candidate.patch_text)
    after_patch = production_snapshot()
    production_changed = changed_files(before, after_patch)

    proposal = build_proposal(
        candidate=candidate,
        cycle_index=cycle_index,
        cycles_completed=cycles_completed,
        suite=suite,
        proposal_path=proposal_path,
        patch_path=patch_path,
        production_changed_files=production_changed,
    )
    write_text(proposal_path, json.dumps(proposal, ensure_ascii=False, indent=2, sort_keys=True) + "\n")

    after_proposal = production_snapshot()
    final_changed = changed_files(before, after_proposal)
    if final_changed != proposal["changed_files"]:
        proposal = {**proposal, "ok": final_changed == [], "changed_files": final_changed}
        proposal = {
            **proposal,
            "decision": "recommend_review" if final_changed == [] else "blocked_or_failed",
        }
        write_text(proposal_path, json.dumps(proposal, ensure_ascii=False, indent=2, sort_keys=True) + "\n")

    return proposal


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage 6c safe patch proposal loop.")
    parser.add_argument("--cycles", type=int, default=1)
    parser.add_argument("--suite", default="smoke")
    parser.add_argument("--audit-path", default=str(DEFAULT_AUDIT_PATH))
    parser.add_argument("--proposal-dir", default=str(DEFAULT_PROPOSAL_DIR))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.cycles < 1:
        print(json.dumps({"ok": False, "error": "cycles must be >= 1"}), file=__import__("sys").stderr)
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
            file=__import__("sys").stderr,
        )
        return 2

    started = time.time()
    audit_path = Path(args.audit_path)
    proposal_dir = Path(args.proposal_dir)
    proposals: list[dict[str, Any]] = []

    for i in range(1, args.cycles + 1):
        proposal = run_cycle(
            cycle_index=i,
            cycles_completed=args.cycles,
            suite=args.suite,
            proposal_dir=proposal_dir,
        )
        proposals.append(proposal)
        append_jsonl(
            audit_path,
            {
                "stage": "6c",
                "event": "patch_proposal_cycle",
                "timestamp_unix": time.time(),
                "proposal": proposal,
            },
        )

    latest = proposals[-1]
    summary = {
        "stage": "6c",
        "ok": all(proposal["ok"] for proposal in proposals),
        "name": "safe patch proposal loop",
        "cycles_requested": args.cycles,
        "cycles_completed": len(proposals),
        "suite": args.suite,
        "proposal_path": latest["proposal_path"],
        "patch_path": latest["patch_path"],
        "risk_classification": latest["risk_classification"],
        "risk_reasons": latest["risk_reasons"],
        "tests_selected": latest["tests_selected"],
        "human_approval_required": True,
        "auto_applied": False,
        "changed_files": sorted({path for proposal in proposals for path in proposal["changed_files"]}),
        "decision": "recommend_review"
        if all(proposal["ok"] for proposal in proposals)
        else "blocked_or_failed",
        "duration_sec": round(time.time() - started, 4),
    }

    append_jsonl(
        audit_path,
        {
            "stage": "6c",
            "event": "patch_proposal_summary",
            "timestamp_unix": time.time(),
            "summary": summary,
        },
    )

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
