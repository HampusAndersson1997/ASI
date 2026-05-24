from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from benchmark_proposals import VERIFIER_VERSION
from common import ROOT, command_metadata, cuda_status, package_versions, resolve_run_dir, sha256_file, update_run_manifest, utc_now, write_json


def summarize_safetensors(path: Path) -> dict[str, Any]:
    import torch
    from safetensors.torch import load_file

    tensors = load_file(str(path), device="cpu")
    tensor_count = len(tensors)
    total_elements = 0
    nonzero_elements = 0
    has_nan = False
    has_inf = False
    nan_count = 0
    inf_count = 0
    for tensor in tensors.values():
        total_elements += int(tensor.numel())
        nonzero_elements += int(torch.count_nonzero(tensor).item())
        tensor_float = tensor.float()
        tensor_nan_count = int(torch.isnan(tensor_float).sum().item())
        tensor_inf_count = int(torch.isinf(tensor_float).sum().item())
        nan_count += tensor_nan_count
        inf_count += tensor_inf_count
        if tensor_nan_count:
            has_nan = True
        if tensor_inf_count:
            has_inf = True
    return {
        "path": str(path),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "tensor_count": tensor_count,
        "total_elements": total_elements,
        "nonzero_elements": nonzero_elements,
        "has_nan": has_nan,
        "has_inf": has_inf,
        "nan_count": nan_count,
        "inf_count": inf_count,
    }


def load_check(args: argparse.Namespace) -> dict[str, Any]:
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoModelForImageTextToText

    dtype = torch.bfloat16 if torch.cuda.is_available() and torch.cuda.is_bf16_supported() else torch.float16
    kwargs = {
        "device_map": "auto",
        "torch_dtype": dtype,
        "local_files_only": args.local_files_only,
        "trust_remote_code": args.trust_remote_code,
    }
    try:
        base = AutoModelForImageTextToText.from_pretrained(args.model, **kwargs)
        loader = "AutoModelForImageTextToText"
    except Exception as primary_exc:
        base = AutoModelForCausalLM.from_pretrained(args.model, **kwargs)
        loader = f"AutoModelForCausalLM fallback after {type(primary_exc).__name__}"
    model = PeftModel.from_pretrained(base, args.adapter_dir, is_trainable=False)
    model.eval()
    return {"adapter_load": "pass", "loader": loader}


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify LoRA adapter artifacts.")
    parser.add_argument("--adapter-dir", type=Path, default=ROOT / "adapters" / "asi_arc_lora_v1")
    parser.add_argument("--model", default=str(ROOT / "models" / "Qwen--Qwen3.5-4B"))
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "adapter_verification.json")
    parser.add_argument("--skip-load", action="store_true")
    parser.add_argument("--local-files-only", action="store_true")
    parser.add_argument("--trust-remote-code", action="store_true")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--run-dir", type=Path, default=None)
    args = parser.parse_args()

    run_dir = resolve_run_dir(args.run_id or None, args.run_dir, label="verify_adapter")
    safetensors_path = args.adapter_dir / "adapter_model.safetensors"
    result: dict[str, Any] = {
        "created_at": utc_now(),
        "adapter_dir": str(args.adapter_dir),
        "adapter_model_safetensors": str(safetensors_path),
        "status": "failed",
        "checks": [],
    }

    if not safetensors_path.exists():
        result["error"] = "adapter_model.safetensors missing"
        result["failure_category"] = "adapter load failure"
        write_json(args.output, result)
        update_run_manifest(
            run_dir,
            {
                "verifier_version": VERIFIER_VERSION,
                "adapter_path": str(args.adapter_dir),
                "package_versions": package_versions(),
                "cuda_status": cuda_status(),
                "command": command_metadata(args),
                "adapter_verification": {"status": "failed", "output": str(args.output), "failure_category": "adapter load failure"},
            },
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 2

    tensor_summary = summarize_safetensors(safetensors_path)
    result["safetensors"] = tensor_summary
    if tensor_summary["total_elements"] <= 0:
        result["checks"].append("failed: no tensor elements")
    if tensor_summary["nonzero_elements"] <= 0:
        result["checks"].append("failed: all adapter weights are zero")
    if tensor_summary["has_nan"]:
        result["checks"].append("failed: adapter contains NaN")
    if tensor_summary["has_inf"]:
        result["checks"].append("failed: adapter contains Inf")
    if not result["checks"]:
        result["checks"].append("pass: adapter weights exist, are non-zero, and contain no NaN/Inf")

    if not args.skip_load:
        try:
            result.update(load_check(args))
            result["checks"].append("pass: base model plus adapter loaded")
        except Exception as exc:  # pragma: no cover - depends on local model/deps
            result["checks"].append(f"failed: adapter load failed: {type(exc).__name__}: {exc}")

    result["status"] = "pass" if all(check.startswith("pass") for check in result["checks"]) else "failed"
    if result["status"] == "failed":
        result["failure_category"] = "weight anomaly" if tensor_summary["has_nan"] or tensor_summary["has_inf"] or tensor_summary["nonzero_elements"] <= 0 else "adapter load failure"
    write_json(args.output, result)
    update_run_manifest(
        run_dir,
        {
            "verifier_version": VERIFIER_VERSION,
            "adapter_path": str(args.adapter_dir),
            "package_versions": package_versions(),
            "cuda_status": cuda_status(),
            "command": command_metadata(args),
            "adapter_verification": {
                "status": result["status"],
                "output": str(args.output),
                "failure_category": result.get("failure_category"),
            },
        },
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
