from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from common import (
    ROOT,
    command_metadata,
    cuda_status,
    extract_single_json_object_with_reason,
    file_metadata,
    has_text_after_first_json_object,
    load_config,
    normalize_text,
    package_versions,
    read_json,
    read_jsonl,
    resolve_run_dir,
    update_run_manifest,
    utc_now,
    write_json,
)


VERIFIER_VERSION = "2026-05-23.strict-json-v2"
RESULT_LABELS = {"improved", "unchanged", "regressed", "failed", "inconclusive"}
FAILURE_TAXONOMY = [
    "invalid JSON",
    "truncated output",
    "missing required field",
    "unclassified evidence",
    "non-executable abstraction",
    "weak verification plan",
    "weak risk boundary",
    "adapter load failure",
    "weight anomaly",
    "prompt/data leakage",
    "verifier bug",
]
EXECUTABLE_TERMS = {"script", "function", "validator", "test", "schema", "algorithm", "rule", "verifier"}
RISK_TERMS = {
    "allowed",
    "requires",
    "forbidden",
    "stop",
    "boundary",
    "confirmation",
    "requires confirmation",
    "risk",
    "mitigation",
    "do not",
    "limit",
    "limited",
    "block",
    "reject",
}
COMPARISON_MODES = {
    "base-vs-adapter",
    "adapter-train-vs-heldout",
    "adapter-vs-adapter",
    "verifier-vs-verifier",
    "checkpoint-series",
}


def has_any(text: str, terms: set[str]) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in terms)


def failure_categories_for(reasons: list[str], parse_failure_reason: str | None = None) -> list[str]:
    categories: list[str] = []
    if parse_failure_reason:
        if parse_failure_reason == "unterminated_json_object":
            categories.append("truncated output")
        else:
            categories.append("invalid JSON")
    reason_map = {
        "not_exactly_one_json_object": "invalid JSON",
        "missing_or_empty_required_fields": "missing required field",
        "evidence_not_classified": "unclassified evidence",
        "executable_abstraction_not_executable": "non-executable abstraction",
        "verification_plan_not_actionable": "weak verification plan",
        "risk_boundary_missing_boundary_terms": "weak risk boundary",
        "adapter_load_failure": "adapter load failure",
        "weight_anomaly": "weight anomaly",
        "prompt_data_leakage": "prompt/data leakage",
        "verifier_bug": "verifier bug",
    }
    for reason in reasons:
        category = reason_map.get(reason)
        if category and category not in categories:
            categories.append(category)
    return categories


def score_response(text: str, required_fields: list[str]) -> dict[str, Any]:
    parsed, parse_failure_reason = extract_single_json_object_with_reason(text)
    json_trailing_text = has_text_after_first_json_object(text)
    if parsed is None:
        reasons = [parse_failure_reason or "no_parseable_json_object"]
        categories = failure_categories_for(reasons, parse_failure_reason)
        return {
            "valid_json": False,
            "exact_json": False,
            "json_trailing_text": json_trailing_text,
            "accepted": False,
            "missing_fields": required_fields,
            "reasons": reasons,
            "parse_failure_reason": parse_failure_reason,
            "strict_parse_failure_reason": parse_failure_reason,
            "failure_category": categories[0],
            "failure_categories": categories,
        }

    missing = [field for field in required_fields if not normalize_text(parsed.get(field))]
    reasons: list[str] = []
    if missing:
        reasons.append("missing_or_empty_required_fields")

    evidence_text = normalize_text(parsed.get("evidence"))
    executable_text = normalize_text(parsed.get("executable_abstraction"))
    verification_text = normalize_text(parsed.get("verification_plan"))
    risk_text = normalize_text(parsed.get("risk_boundary"))

    if not has_any(evidence_text, {"fact", "inference", "hypothesis", "unknown"}):
        reasons.append("evidence_not_classified")
    if not has_any(executable_text, EXECUTABLE_TERMS):
        reasons.append("executable_abstraction_not_executable")
    if not has_any(verification_text, {"run", "check", "verify", "compare", "test", "score"}):
        reasons.append("verification_plan_not_actionable")
    if not has_any(risk_text, RISK_TERMS):
        reasons.append("risk_boundary_missing_boundary_terms")

    categories = failure_categories_for(reasons)
    return {
        "valid_json": True,
        "exact_json": True,
        "json_trailing_text": False,
        "accepted": not missing and not reasons,
        "missing_fields": missing,
        "reasons": reasons,
        "parse_failure_reason": None,
        "strict_parse_failure_reason": None,
        "failure_category": categories[0] if categories else None,
        "failure_categories": categories,
        "parsed": parsed,
    }


def stable_unique(values: list[Any]) -> list[Any]:
    unique: list[Any] = []
    seen: set[str] = set()
    for value in values:
        key = normalize_text(value)
        if key in seen:
            continue
        seen.add(key)
        unique.append(value)
    return unique


def collect_response_metadata(responses: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "prompt_hashes": [row.get("prompt_hash") for row in responses],
        "prompt_file_sha256": stable_unique([row.get("prompt_file_sha256") for row in responses if row.get("prompt_file_sha256")]),
        "response_hashes": [row.get("response_hash") for row in responses],
        "model": stable_unique([row.get("model") for row in responses if row.get("model")]),
        "model_revision": stable_unique([row.get("model_revision") for row in responses if row.get("model_revision")]),
        "adapter": stable_unique([row.get("adapter") for row in responses if row.get("adapter")]),
        "decoding_settings": stable_unique([row.get("decoding_settings") for row in responses if row.get("decoding_settings")]),
        "verifier_version": stable_unique([row.get("verifier_version") for row in responses if row.get("verifier_version")]),
    }


def score_file(responses_path: Path, output_path: Path) -> dict[str, Any]:
    config = load_config()
    required_fields = list(config["benchmark"]["required_fields"])
    responses = read_jsonl(responses_path)
    details = []
    for row in responses:
        score = score_response(str(row.get("response", "")), required_fields)
        details.append(
            {
                "id": row.get("id"),
                "prompt_hash": row.get("prompt_hash"),
                "response_hash": row.get("response_hash"),
                "status": "accepted" if score["accepted"] else "rejected",
                "failure_category": score.get("failure_category"),
                "score": score,
            }
        )

    total = len(details)
    valid = sum(1 for item in details if item["score"]["valid_json"])
    exact_json = sum(1 for item in details if item["score"]["exact_json"])
    extra_text_after_json = sum(1 for item in details if item["score"]["json_trailing_text"])
    accepted = sum(1 for item in details if item["score"]["accepted"])
    failure_counts = {category: 0 for category in FAILURE_TAXONOMY}
    for item in details:
        category = item.get("failure_category")
        if category:
            failure_counts[category] = failure_counts.get(category, 0) + 1
    metrics = {
        "created_at": utc_now(),
        "verifier_version": VERIFIER_VERSION,
        "responses_path": str(responses_path),
        "prompt_ids": [item["id"] for item in details],
        "measurement_metadata": collect_response_metadata(responses),
        "total": total,
        "valid_json_count": valid,
        "valid_json_rate": valid / total if total else 0.0,
        "exact_json_count": exact_json,
        "exact_json_rate": exact_json / total if total else 0.0,
        "extra_text_after_json_count": extra_text_after_json,
        "required_field_completion_rate": (
            sum(1 for item in details if not item["score"]["missing_fields"]) / total if total else 0.0
        ),
        "accepted_proposal_count": accepted,
        "failure_taxonomy": FAILURE_TAXONOMY,
        "failure_counts": failure_counts,
        "details": details,
        "status": "pass" if total else "failed",
    }
    write_json(output_path, metrics)
    return metrics


def metadata_single(metrics: dict[str, Any], key: str) -> Any:
    values = metrics.get("measurement_metadata", {}).get(key, [])
    if isinstance(values, list) and len(values) == 1:
        return values[0]
    return None


def missing_comparison_metadata(metrics: dict[str, Any], keys: list[str]) -> list[str]:
    missing = []
    for key in keys:
        value = metrics.get("measurement_metadata", {}).get(key)
        if not value:
            missing.append(key)
    return missing


def compare(base_path: Path, adapter_path: Path, output_path: Path, mode: str = "base-vs-adapter") -> dict[str, Any]:
    if mode not in COMPARISON_MODES:
        raise ValueError(f"unknown comparison mode: {mode}")

    base = read_json(base_path)
    adapter = read_json(adapter_path)
    result = "inconclusive"
    reasons: list[str] = []
    model_improvement_claim = mode in {"base-vs-adapter", "adapter-vs-adapter", "checkpoint-series"}
    verifier_calibration = False

    if base.get("status") != "pass" or adapter.get("status") != "pass":
        result = "failed"
        reasons.append("one_or_both_metric_files_failed")
    else:
        required_keys = ["prompt_hashes", "model_revision", "decoding_settings"]
        if mode != "verifier-vs-verifier":
            required_keys.append("verifier_version")
        missing = {
            "base": missing_comparison_metadata(base, required_keys),
            "adapter": missing_comparison_metadata(adapter, required_keys),
        }
        if missing["base"] or missing["adapter"]:
            result = "inconclusive"
            reasons.append(f"missing_required_comparison_metadata:{missing}")
        elif mode != "adapter-train-vs-heldout" and base.get("prompt_ids") != adapter.get("prompt_ids"):
            result = "inconclusive"
            reasons.append("prompt_ids_differ")
        elif mode != "adapter-train-vs-heldout" and base["measurement_metadata"].get("prompt_hashes") != adapter["measurement_metadata"].get("prompt_hashes"):
            result = "inconclusive"
            reasons.append("prompt_hashes_differ")
        elif mode == "adapter-train-vs-heldout" and base["measurement_metadata"].get("prompt_hashes") == adapter["measurement_metadata"].get("prompt_hashes"):
            result = "inconclusive"
            reasons.append("train_and_heldout_prompt_hashes_match")
        elif metadata_single(base, "model_revision") != metadata_single(adapter, "model_revision"):
            result = "inconclusive"
            reasons.append("model_revision_differs")
        elif metadata_single(base, "decoding_settings") != metadata_single(adapter, "decoding_settings"):
            result = "inconclusive"
            reasons.append("decoding_settings_differ")
        elif mode == "verifier-vs-verifier":
            model_improvement_claim = False
            verifier_calibration = True
            if base["measurement_metadata"].get("response_hashes") != adapter["measurement_metadata"].get("response_hashes"):
                result = "inconclusive"
                reasons.append("response_hashes_differ")
            elif base.get("verifier_version") == adapter.get("verifier_version"):
                result = "unchanged"
                reasons.append("same_verifier_version")
            else:
                result = "inconclusive"
                reasons.append("verifier_changed_measurement_instrument")
        elif base.get("verifier_version") != adapter.get("verifier_version"):
            result = "inconclusive"
            reasons.append("verifier_version_differs")
            model_improvement_claim = False
            verifier_calibration = True
        else:
            base_valid = float(base["valid_json_rate"])
            adapter_valid = float(adapter["valid_json_rate"])
            base_accepted = int(base["accepted_proposal_count"])
            adapter_accepted = int(adapter["accepted_proposal_count"])
            if adapter_valid < base_valid:
                result = "regressed"
                reasons.append("valid_json_rate_decreased")
            elif adapter_accepted >= base_accepted + 1:
                result = "improved"
                reasons.append("accepted_count_increased_without_valid_json_drop")
            elif adapter_accepted < base_accepted:
                result = "regressed"
                reasons.append("accepted_count_decreased")
            else:
                result = "unchanged"
                reasons.append("no_required_metric_improvement")

    comparison = {
        "created_at": utc_now(),
        "comparison_mode": mode,
        "verifier_version": VERIFIER_VERSION,
        "base_metrics": str(base_path),
        "adapter_metrics": str(adapter_path),
        "result": result,
        "allowed_result_labels": sorted(RESULT_LABELS),
        "reasons": reasons,
        "model_improvement_claim": model_improvement_claim and result == "improved",
        "verifier_calibration": verifier_calibration,
        "base": {
            "valid_json_rate": base.get("valid_json_rate"),
            "accepted_proposal_count": base.get("accepted_proposal_count"),
            "measurement_metadata": base.get("measurement_metadata"),
        },
        "adapter": {
            "valid_json_rate": adapter.get("valid_json_rate"),
            "accepted_proposal_count": adapter.get("accepted_proposal_count"),
            "measurement_metadata": adapter.get("measurement_metadata"),
        },
        "improvement_rule": load_config()["benchmark"]["improvement_rule"],
        "debug_rules": [
            "training_loss_alone_is_not_improvement_evidence",
            "prompt_set_verifier_model_revision_and_decoding_settings_must_match_for_model_comparisons",
            "verifier_changes_are_measurement_instrument_changes",
        ],
    }
    if result not in RESULT_LABELS:
        comparison["result"] = "failed"
        comparison["reasons"].append("comparator_emitted_invalid_result_label")
    write_json(output_path, comparison)
    return comparison


def compact_manifest_value(value: Any) -> Any:
    if not value:
        return None
    if isinstance(value, list) and len(value) == 1:
        return value[0]
    return value


def safe_manifest_key(value: str) -> str:
    safe = "".join(char if char.isalnum() else "_" for char in value).strip("_")
    return safe or "output"


def score_manifest_updates(args: argparse.Namespace, payload: dict[str, Any]) -> dict[str, Any]:
    metadata = payload.get("measurement_metadata", {})
    score_key = f"benchmark_score_{safe_manifest_key(args.output.stem)}"
    updates = {
        "verifier_version": VERIFIER_VERSION,
        "package_versions": package_versions(),
        "cuda_status": cuda_status(),
        "command": command_metadata(args),
        "prompt_hash": compact_manifest_value(metadata.get("prompt_file_sha256") or metadata.get("prompt_hashes")),
        "model_revision": compact_manifest_value(metadata.get("model_revision")),
        score_key: {
            "command": args.cmd,
            "responses": file_metadata(args.responses),
            "output": str(args.output),
            "output_file": file_metadata(args.output),
            "status": payload.get("status", "pass"),
            "verifier_version": payload.get("verifier_version"),
            "prompt_ids": payload.get("prompt_ids"),
        },
    }
    adapter_path = compact_manifest_value(metadata.get("adapter"))
    if adapter_path is not None:
        updates["adapter_path"] = adapter_path
    return updates


def comparison_metadata_value(payload: dict[str, Any], key: str) -> Any:
    values: list[Any] = []
    for side in ("base", "adapter"):
        metadata = payload.get(side, {}).get("measurement_metadata", {})
        raw = metadata.get(key)
        if isinstance(raw, list):
            values.extend(raw)
        elif raw:
            values.append(raw)
    return compact_manifest_value(stable_unique(values))


def compare_manifest_updates(args: argparse.Namespace, payload: dict[str, Any]) -> dict[str, Any]:
    updates = {
        "verifier_version": VERIFIER_VERSION,
        "package_versions": package_versions(),
        "cuda_status": cuda_status(),
        "command": command_metadata(args),
        "prompt_hash": comparison_metadata_value(payload, "prompt_file_sha256")
        or comparison_metadata_value(payload, "prompt_hashes"),
        "model_revision": comparison_metadata_value(payload, "model_revision"),
        "benchmark_compare": {
            "command": args.cmd,
            "comparison_mode": args.mode,
            "base_metrics": file_metadata(args.base),
            "adapter_metrics": file_metadata(args.adapter),
            "output": str(args.output),
            "output_file": file_metadata(args.output),
            "status": payload.get("status", "pass"),
            "result": payload.get("result"),
            "reasons": payload.get("reasons"),
        },
    }
    adapter_path = comparison_metadata_value(payload, "adapter")
    if adapter_path is not None:
        updates["adapter_path"] = adapter_path
    return updates


def main() -> int:
    parser = argparse.ArgumentParser(description="Score or compare ASI/ARC proposal benchmark outputs.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    score_parser = sub.add_parser("score")
    score_parser.add_argument("--responses", type=Path, required=True)
    score_parser.add_argument("--output", type=Path, required=True)
    score_parser.add_argument("--run-id", default="")
    score_parser.add_argument("--run-dir", type=Path, default=None)

    compare_parser = sub.add_parser("compare")
    compare_parser.add_argument("--base", type=Path, required=True)
    compare_parser.add_argument("--adapter", type=Path, required=True)
    compare_parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "benchmark_comparison.json")
    compare_parser.add_argument("--mode", choices=sorted(COMPARISON_MODES), default="base-vs-adapter")
    compare_parser.add_argument("--run-id", default="")
    compare_parser.add_argument("--run-dir", type=Path, default=None)

    args = parser.parse_args()
    run_dir = resolve_run_dir(args.run_id or None, args.run_dir, label=f"benchmark_{args.cmd}")
    if args.cmd == "score":
        payload = score_file(args.responses, args.output)
        manifest_updates = score_manifest_updates(args, payload)
    else:
        payload = compare(args.base, args.adapter, args.output, mode=args.mode)
        manifest_updates = compare_manifest_updates(args, payload)
    update_run_manifest(run_dir, manifest_updates)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload.get("status", "pass") != "failed" and payload.get("result") != "failed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
