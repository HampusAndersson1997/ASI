from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from build_sft_dataset import REQUIRED_FIELDS, response, sample
from common import ROOT, read_jsonl, sha256_file, utc_now, write_json, write_jsonl


SYSTEM_PROMPT_V21 = (
    "You are a local ASI/ARC proposal engine. Return exactly one compact JSON "
    "object with fields claim, evidence, proposal, executable_abstraction, "
    "verification_plan, risk_boundary, expected_result, and stop_condition. "
    "Evidence labels must be lowercase fact:, inference:, hypothesis:, or "
    "unknown:. End immediately after the final JSON brace."
)


def v21_sample(sample_id: str, user_prompt: str, assistant_json: str, source_files: list[str]) -> dict[str, Any]:
    row = sample(sample_id, user_prompt, assistant_json, source_files)
    row["messages"][0]["content"] = SYSTEM_PROMPT_V21
    return row


def targeted_records() -> list[dict[str, Any]]:
    return [
        v21_sample(
            "sft_v2_1_001",
            "Write a LoRA snapshot anomaly validator that hashes initial and final adapter tensors and rejects non-finite values.",
            response(
                "LoRA snapshot validation passes only when tensor hashes, finite checks, and nonzero deltas are recorded.",
                [
                    "fact: adapter_init.safetensors stores the initial adapter state",
                    "fact: adapter_final.safetensors stores the final adapter state",
                    "inference: a missing hash or non-finite tensor makes the run unauditable",
                ],
                "Load both snapshots, hash every tensor, check NaN and Inf counts, compute deltas, and reject missing tensors.",
                "function: validate_lora_snapshots(init_path,final_path)->pass|failed using sha256, nan_count, inf_count, and nonzero_delta.",
                [
                    "Run tensor loading",
                    "Check tensor names match",
                    "Check every tensor is finite",
                    "Compare per-tensor hashes",
                    "Verify any_nonzero_delta is true",
                ],
                "Allowed: read local adapter snapshots. Forbidden: claim training changed weights without nonzero deltas. Stop on missing file, NaN, Inf, or hash failure.",
                "The validator writes a pass or failed result with per-tensor hashes and finite-value counts.",
                "Stop after writing the JSON object and do not append chat text.",
            ),
            ["scripts/common.py", "scripts/train_lora.py"],
        ),
        v21_sample(
            "sft_v2_1_002",
            "Create a deterministic classifier for failed proposal outputs using parser, schema, verifier, safety, and leakage categories.",
            response(
                "A failed proposal response must map to a fixed category before any improvement claim is made.",
                [
                    "fact: parser failures include invalid JSON and truncated output",
                    "fact: schema failures include missing required fields",
                    "inference: fixed categories make regressions comparable across runs",
                ],
                "Classify strict JSON failures first, required-field failures second, semantic verifier failures third, then leakage and verifier bugs.",
                "function: classify_failure(strict_reason,missing_fields,verifier_reasons)->invalid JSON|truncated output|missing required field|weak verification plan|weak risk boundary|prompt/data leakage|verifier bug.",
                [
                    "Run strict JSON parse",
                    "Check required fields",
                    "Score verification plan",
                    "Score risk boundary",
                    "Check leakage flags",
                    "Write one primary category",
                ],
                "Allowed: deterministic local scoring. Forbidden: invent uncataloged success from a rejected response. Stop on unmapped failure or verifier bug.",
                "Each rejected response has one primary category and optional secondary categories.",
                "Stop after the single JSON object; no second object, transcript text, or think block follows.",
            ),
            ["scripts/benchmark_proposals.py"],
        ),
        v21_sample(
            "sft_v2_1_003",
            "Specify an output contract that fails any response with text after the closing JSON brace.",
            response(
                "Exact JSON means optional whitespace around one top-level object and no other text.",
                [
                    "fact: trailing chat text can hide after a parseable object",
                    "fact: strict parsing rejects more than one top-level JSON object",
                    "inference: exact JSON metrics expose formatter regressions",
                ],
                "Use a strict parser that accepts one object only, records exact_json, and marks trailing text as invalid JSON.",
                "validator: extract_single_json_object_with_reason(text) returns object|not_exactly_one_json_object|unterminated_json_object.",
                [
                    "Run parser tests",
                    "Check trailing text case",
                    "Check two-object case",
                    "Check top-level array case",
                    "Verify exact_json_rate is recorded",
                ],
                "Allowed: local verifier code and saved response files. Forbidden: accept a first object when extra text remains. Stop on strict parse failure.",
                "Metrics include exact_json_count, exact_json_rate, and extra_text_after_json_count.",
                "Stop immediately after the closing brace.",
            ),
            ["scripts/common.py", "scripts/benchmark_proposals.py"],
        ),
        v21_sample(
            "sft_v2_1_004",
            "Design a calibration replay for saved responses under a stricter verifier.",
            response(
                "Replaying saved responses under a new verifier is verifier calibration, not model improvement.",
                [
                    "fact: saved response files contain response_hash values",
                    "fact: metric files record verifier_version",
                    "inference: identical response hashes isolate the measurement instrument change",
                ],
                "Score the saved response JSONL with the new verifier and compare old and new metrics using verifier-vs-verifier mode.",
                "script: benchmark_proposals.py compare --mode verifier-vs-verifier checks response_hashes and sets verifier_calibration true.",
                [
                    "Check response hashes match",
                    "Check prompt hashes match",
                    "Score with strict verifier",
                    "Compare old and new metrics",
                    "Record calibration result",
                ],
                "Allowed: re-score immutable saved outputs. Forbidden: report verifier-only movement as adapter progress. Stop if response hashes differ.",
                "The comparison result is inconclusive or unchanged with verifier_calibration true and model_improvement_claim false.",
                "Stop after the exact JSON object.",
            ),
            ["scripts/benchmark_proposals.py", "artifacts/runs"],
        ),
        v21_sample(
            "sft_v2_1_005",
            "Summarize a held-out local adapter comparison without overstating progress.",
            response(
                "A held-out comparison is improved only when accepted count rises without a valid JSON rate drop under matched metadata.",
                [
                    "fact: comparator result labels are improved, unchanged, regressed, failed, or inconclusive",
                    "fact: model revision, prompt hashes, decoding settings, and verifier version gate comparisons",
                    "inference: JSON formatting gains alone are insufficient if accepted count does not rise",
                ],
                "Report accepted counts, exact JSON rates, verifier version, metadata match status, and the final comparator label.",
                "function: summarize_comparison(metrics_a,metrics_b,comparison)->markdown using only measured fields.",
                [
                    "Load metric JSON",
                    "Check verifier version",
                    "Compare accepted counts",
                    "Compare exact JSON rates",
                    "Verify result label",
                ],
                "Allowed: cite local artifacts. Forbidden: claim ASI progress from an inconclusive comparison. Stop if manifests or metrics are missing.",
                "The summary contains the allowed result label and separates facts from inferences.",
                "Stop after the JSON object with no trailing prose.",
            ),
            ["scripts/benchmark_proposals.py", "asi_kernel/artifacts/local_llm"],
        ),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the strict JSON v2.1 SFT dataset.")
    parser.add_argument("--base", type=Path, default=ROOT / "data" / "asi_arc_sft_v2.jsonl")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "asi_arc_sft_v2_1.jsonl")
    parser.add_argument("--manifest", type=Path, default=ROOT / "data" / "asi_arc_sft_v2_1_manifest.json")
    args = parser.parse_args()

    base_rows = read_jsonl(args.base)
    rows = base_rows + targeted_records()
    ids = [row["id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate SFT ids in v2.1 dataset")

    write_jsonl(args.output, rows)
    manifest = {
        "created_at": utc_now(),
        "dataset": str(args.output),
        "base_dataset": str(args.base),
        "base_dataset_sha256": sha256_file(args.base),
        "dataset_sha256": sha256_file(args.output),
        "record_count": len(rows),
        "base_record_count": len(base_rows),
        "targeted_record_count": len(rows) - len(base_rows),
        "required_fields": REQUIRED_FIELDS,
        "targeted_topics": [
            "strict_json_termination",
            "lora_snapshot_anomaly",
            "failure_classifier",
            "verifier_calibration",
            "non_overclaiming_summary",
        ],
        "status": "pass",
    }
    write_json(args.manifest, manifest)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
