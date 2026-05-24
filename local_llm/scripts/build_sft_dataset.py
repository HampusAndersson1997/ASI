from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from common import ROOT, sha256_file, utc_now, write_json, write_jsonl


SYSTEM_PROMPT = (
    "You are a local ASI/ARC proposal engine. Separate fact, inference, "
    "hypothesis, and unknown. Return exactly one JSON object with required "
    "fields. Do not claim success without measured evidence."
)

REQUIRED_FIELDS = [
    "claim",
    "evidence",
    "proposal",
    "executable_abstraction",
    "verification_plan",
    "risk_boundary",
    "expected_result",
    "stop_condition",
]


def response(
    claim: str,
    evidence: list[str],
    proposal: str,
    executable_abstraction: str,
    verification_plan: list[str],
    risk_boundary: str,
    expected_result: str,
    stop_condition: str,
) -> str:
    payload: dict[str, Any] = {
        "claim": claim,
        "evidence": evidence,
        "proposal": proposal,
        "executable_abstraction": executable_abstraction,
        "verification_plan": verification_plan,
        "risk_boundary": risk_boundary,
        "expected_result": expected_result,
        "stop_condition": stop_condition,
    }
    missing = [field for field in REQUIRED_FIELDS if field not in payload]
    if missing:
        raise AssertionError(f"missing required fields: {missing}")
    return json.dumps(payload, ensure_ascii=True, sort_keys=True)


def sample(sample_id: str, user_prompt: str, assistant_json: str, source_files: list[str]) -> dict[str, Any]:
    return {
        "id": sample_id,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": assistant_json},
        ],
        "source_files": source_files,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a tiny grounded ASI/ARC SFT seed dataset.")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "asi_arc_sft_v1.jsonl")
    parser.add_argument("--manifest", type=Path, default=ROOT / "data" / "asi_arc_sft_v1_manifest.json")
    args = parser.parse_args()

    sandbox = ROOT.parent
    source_paths = {
        "kernel_readme": sandbox / "asi_kernel" / "README.md",
        "current_state": sandbox / "asi_kernel" / "loop" / "current_state.md",
        "memory_protocol": sandbox / "asi_kernel" / "memory" / "memory_protocol.md",
        "pursuit_goals": sandbox / "asi_kernel" / "goals" / "pursuit_goals.md",
        "object_extractor": sandbox / "asi_kernel" / "arc_agi_2" / "object_extractor.py",
    }
    missing = [str(path) for path in source_paths.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"required source files are missing: {missing}")

    records = [
        sample(
            "sft_001",
            "Propose a measurable ASI/ARC benchmark loop from the local kernel rules.",
            response(
                "A proposal benchmark is valid only when it has an artifact, verifier, and recorded result.",
                ["fact: asi_kernel/README.md says no improvement without measurement", "fact: pursuit_goals.md says no goal is complete without artifact, verifier, and result"],
                "Create fixed prompts, score JSON validity and verifier acceptance, then compare base and adapter results.",
                "script: benchmark_proposals.py scores response JSON and compare mode emits improved, unchanged, regressed, failed, or inconclusive.",
                ["Run base inference on fixed prompts", "Run adapter inference on the same prompts", "Compare accepted proposal count and valid JSON rate"],
                "Allowed: local files under D:/Sandbox/local_llm and D:/Sandbox/asi_kernel/artifacts. Requires confirmation: network downloads and package installs.",
                "A benchmark summary JSON exists with one allowed result label.",
                "Stop if any response parser, model load, or verifier step fails without a recorded failure artifact.",
            ),
            ["asi_kernel/README.md", "asi_kernel/goals/pursuit_goals.md"],
        ),
        sample(
            "sft_002",
            "Propose a LoRA adapter verification step that does not modify base weights.",
            response(
                "LoRA modifies adapter weights first; base weights remain unchanged until an explicit merge step.",
                ["fact: user proposal states modify weights means LoRA adapter weights first", "fact: user proposal states base weights remain unchanged until later explicit merge"],
                "Train a PEFT adapter, save adapter_model.safetensors, compute SHA256, and load it over the frozen base model.",
                "script: verify_adapter.py checks safetensors existence, non-zero tensors, NaN absence, SHA256, and optional PEFT load.",
                ["Check adapter_model.safetensors exists", "Count tensor elements and non-zero elements", "Record SHA256", "Load base plus adapter with local files if requested"],
                "Allowed: read adapter directory and base model cache. Forbidden: claim full fine-tune or merged weights unless a merge script is run and logged.",
                "Adapter verification JSON reports pass only when weights are present, non-zero, finite, and loadable.",
                "Stop if safetensors are missing, all-zero, contain NaN, or cannot load.",
            ),
            ["user proposal"],
        ),
        sample(
            "sft_003",
            "Propose an ARC executable abstraction from object extraction evidence.",
            response(
                "ARC proposals should be executable and checked against examples rather than described vaguely.",
                ["fact: asi-kernel skill requires executable abstractions and verification against examples", "fact: object_extractor.py exists in asi_kernel/arc_agi_2"],
                "Represent grid objects as connected components, then score candidate transformations against all available train examples.",
                "function: extract_components(grid) -> objects; function: apply_rule(objects, grid) -> predicted_grid; verifier: exact grid equality.",
                ["Run object extraction self-test if available", "Apply candidate rule to every train example", "Reject any rule that fails exact output equality"],
                "Allowed: local ARC examples and deterministic Python scripts. Forbidden: using hidden test labels as evidence.",
                "A candidate rule is accepted only if every available train pair matches exactly.",
                "Stop when a train example contradicts the abstraction or required evidence is missing.",
            ),
            ["asi_kernel/arc_agi_2/object_extractor.py"],
        ),
        sample(
            "sft_004",
            "Create a memory-safe proposal that avoids storing hallucinated facts.",
            response(
                "A memory record can store evidence state, not belief.",
                ["fact: memory_protocol.md says memory stores evidence state, not belief", "fact: memory_protocol.md requires source, verifier, timestamp, and scope for facts"],
                "Write one atomic record per claim with status fact, inference, hypothesis, unknown, or refuted.",
                "schema: {id, status, claim, source, verifier, observed_at, scope, expires}; validator rejects fact records missing required provenance.",
                ["Create a sample memory record", "Run a schema check", "Verify that unverified claims are classified as hypothesis or unknown"],
                "Allowed: local memory notes. Requires confirmation: external memory connector writes. Forbidden: demoting uncertainty by summary.",
                "The validator rejects facts without source, verifier, timestamp, and scope.",
                "Stop if a summary would turn an inference or hypothesis into a fact.",
            ),
            ["asi_kernel/memory/memory_protocol.md"],
        ),
        sample(
            "sft_005",
            "Propose a safe Arch WSL GPU verification step for local LLM training.",
            response(
                "GPU readiness is not established until WSL device visibility and PyTorch CUDA availability are both verified.",
                ["fact: user proposal requires /dev/dxg and /usr/lib/wsl/lib/nvidia-smi", "fact: user proposal requires PyTorch cuda_available=True inside Arch WSL"],
                "Run a WSL device check first, then run a Python torch.cuda check inside the isolated environment.",
                "script: check_wsl_gpu.sh writes wsl_gpu_check.json; script: check_torch_cuda.py writes torch_cuda_check.json.",
                ["Check PATH contains /usr/lib/wsl/lib", "Check /dev/dxg exists", "Run nvidia-smi", "Import torch and assert torch.cuda.is_available()"],
                "Allowed: read WSL device state and write JSON artifacts. Requires confirmation: package install to create torch environment.",
                "Acceptance passes only when both JSON artifacts report pass.",
                "Stop if nvidia-smi fails or torch cannot import with CUDA available.",
            ),
            ["user proposal"],
        ),
        sample(
            "sft_006",
            "Turn the improvement criterion into an exact comparator.",
            response(
                "Improvement requires at least one additional verifier-accepted proposal without lowering valid JSON rate.",
                ["fact: user proposal defines improvement as +1 accepted proposal without lowering valid JSON rate"],
                "Compare base and adapter metric JSON files and emit exactly one result label.",
                "function: compare(base, adapter) -> improved|unchanged|regressed|failed|inconclusive using accepted_count and valid_json_rate.",
                ["Load base metrics", "Load adapter metrics", "Check status", "Apply improvement rule", "Write comparison JSON"],
                "Allowed: benchmark artifacts from the same prompt set. Forbidden: comparing different prompt files as an improvement claim.",
                "Comparator records improved only under the stated rule; otherwise it records unchanged, regressed, failed, or inconclusive.",
                "Stop if prompt IDs differ or either benchmark file is invalid.",
            ),
            ["user proposal"],
        ),
    ]

    write_jsonl(args.output, records)
    manifest = {
        "created_at": utc_now(),
        "dataset": str(args.output),
        "record_count": len(records),
        "required_fields": REQUIRED_FIELDS,
        "source_files": {
            key: {"path": str(path), "sha256": sha256_file(path)} for key, path in source_paths.items()
        },
        "dataset_sha256": sha256_file(args.output),
        "status": "pass",
    }
    write_json(args.manifest, manifest)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
