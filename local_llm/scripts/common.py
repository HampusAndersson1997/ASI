from __future__ import annotations

import hashlib
import importlib.metadata as importlib_metadata
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(os.environ.get("LOCAL_LLM_ROOT", Path(__file__).resolve().parents[1])).resolve()
CONFIG_PATH = ROOT / "configs" / "proposal_engine.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def run_id_now(label: str = "run") -> str:
    safe_label = "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in label).strip("-")
    suffix = uuid.uuid4().hex[:8]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}_{safe_label or 'run'}_{suffix}"


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
        fh.write("\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSONL: {exc}") from exc
    return rows


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=True, sort_keys=True))
            fh.write("\n")


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def file_metadata(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return {
        "path": str(path),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def load_config() -> dict[str, Any]:
    return read_json(CONFIG_PATH)


def jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    if isinstance(value, set):
        return sorted(jsonable(item) for item in value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def resolve_run_dir(run_id: str | None = None, run_dir: Path | None = None, label: str = "run") -> Path:
    if run_dir is not None:
        path = run_dir
    else:
        path = ROOT / "artifacts" / "runs" / (run_id or run_id_now(label))
    path.mkdir(parents=True, exist_ok=True)
    return path


def update_run_manifest(run_dir: Path, updates: dict[str, Any]) -> dict[str, Any]:
    manifest_path = run_dir / "run_manifest.json"
    if manifest_path.exists():
        manifest = read_json(manifest_path)
    else:
        manifest = {"created_at": utc_now(), "run_id": run_dir.name}
    for key, value in jsonable(updates).items():
        if isinstance(manifest.get(key), dict) and isinstance(value, dict):
            manifest[key].update(value)
        else:
            manifest[key] = value
    manifest["run_id"] = manifest.get("run_id") or run_dir.name
    manifest["updated_at"] = utc_now()
    write_json(manifest_path, manifest)
    return manifest


def package_versions(packages: Iterable[str] | None = None) -> dict[str, str | None]:
    names = list(
        packages
        or [
            "accelerate",
            "bitsandbytes",
            "datasets",
            "huggingface_hub",
            "peft",
            "safetensors",
            "torch",
            "transformers",
            "trl",
        ]
    )
    versions: dict[str, str | None] = {}
    for name in names:
        try:
            versions[name] = importlib_metadata.version(name)
        except importlib_metadata.PackageNotFoundError:
            versions[name] = None
    return versions


def cuda_status() -> dict[str, Any]:
    try:
        import torch
    except Exception as exc:  # pragma: no cover - depends on runtime env
        return {"torch_import": "failed", "error": f"{type(exc).__name__}: {exc}"}

    status: dict[str, Any] = {
        "torch_import": "pass",
        "torch_version": getattr(torch, "__version__", None),
        "cuda_available": bool(torch.cuda.is_available()),
        "cuda_version": getattr(torch.version, "cuda", None),
        "device_count": int(torch.cuda.device_count()) if torch.cuda.is_available() else 0,
    }
    if torch.cuda.is_available():
        current = int(torch.cuda.current_device())
        status.update(
            {
                "current_device": current,
                "device_name": torch.cuda.get_device_name(current),
                "bf16_supported": bool(torch.cuda.is_bf16_supported()),
            }
        )
    return status


def model_revision_metadata(model_path: str | Path | None = None) -> dict[str, Any]:
    manifest_path = ROOT / "artifacts" / "model_manifest_qwen3_5_4b.json"
    metadata: dict[str, Any] = {"model_path": str(model_path) if model_path is not None else None}
    if manifest_path.exists():
        manifest = read_json(manifest_path)
        metadata.update(
            {
                "manifest_path": str(manifest_path),
                "model_id": manifest.get("model_id"),
                "requested_revision": manifest.get("requested_revision"),
                "resolved_revision": manifest.get("resolved_revision"),
                "source_url": manifest.get("source_url"),
                "manifest_status": manifest.get("status"),
            }
        )
    else:
        metadata["manifest_path"] = None
    return metadata


def command_metadata(args: Any) -> dict[str, Any]:
    return {
        "argv": sys.argv[:],
        "args": jsonable(vars(args) if hasattr(args, "__dict__") else args),
    }


def extract_json_object_with_reason(text: str) -> tuple[dict[str, Any] | None, str | None]:
    """Return the first parseable JSON object and a parse failure reason when absent."""
    start = text.find("{")
    if start == -1:
        return None, "no_json_object_start"
    last_reason = "no_parseable_json_object"
    while start != -1:
        depth = 0
        in_string = False
        escape = False
        saw_balanced_object = False
        for idx in range(start, len(text)):
            char = text[idx]
            if in_string:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    saw_balanced_object = True
                    candidate = text[start : idx + 1]
                    try:
                        parsed = json.loads(candidate)
                    except json.JSONDecodeError as exc:
                        last_reason = f"json_decode_error: {exc.msg}"
                        break
                    if isinstance(parsed, dict):
                        return parsed, None
                    last_reason = "top_level_json_not_object"
                    break
        if not saw_balanced_object and depth > 0:
            last_reason = "unterminated_json_object"
        start = text.find("{", start + 1)
    return None, last_reason


def extract_json_object(text: str) -> dict[str, Any] | None:
    """Return the first parseable JSON object in model text, including fenced text."""
    parsed, _reason = extract_json_object_with_reason(text)
    return parsed


def _balanced_json_object_end(text: str, start: int) -> tuple[int | None, str | None]:
    depth = 0
    in_string = False
    escape = False
    for idx in range(start, len(text)):
        char = text[idx]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return idx + 1, None
            if depth < 0:
                return None, "json_decode_error: unmatched closing brace"
    if depth > 0 or in_string:
        return None, "unterminated_json_object"
    return None, "no_json_object_start"


def extract_single_json_object_with_reason(text: str) -> tuple[dict[str, Any] | None, str | None]:
    """Return one top-level JSON object only when the whole text is that object."""
    stripped = text.strip()
    if not stripped:
        return None, "no_json_object_start"
    if not stripped.startswith("{"):
        return None, "not_exactly_one_json_object"

    object_end, scan_reason = _balanced_json_object_end(stripped, 0)
    if object_end is None:
        return None, scan_reason
    if stripped[object_end:].strip():
        return None, "not_exactly_one_json_object"

    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError as exc:
        return None, f"json_decode_error: {exc.msg}"
    if not isinstance(parsed, dict):
        return None, "not_exactly_one_json_object"
    return parsed, None


def has_text_after_first_json_object(text: str) -> bool:
    stripped = text.strip()
    if not stripped.startswith("{"):
        return False
    object_end, _reason = _balanced_json_object_end(stripped, 0)
    return object_end is not None and bool(stripped[object_end:].strip())


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return json.dumps(value, ensure_ascii=True, sort_keys=True)


def save_safetensors_state(state: dict[str, Any], path: Path) -> None:
    from safetensors.torch import save_file

    clean = {name: tensor.detach().cpu().contiguous() for name, tensor in state.items()}
    path.parent.mkdir(parents=True, exist_ok=True)
    save_file(clean, str(path))


def tensor_sha256(tensor: Any) -> str:
    import torch

    cpu_tensor = tensor.detach().cpu().contiguous()
    digest = hashlib.sha256()
    digest.update(str(cpu_tensor.dtype).encode("utf-8"))
    digest.update(json.dumps(list(cpu_tensor.shape)).encode("utf-8"))
    try:
        raw = cpu_tensor.view(torch.uint8).numpy().tobytes()
    except Exception:
        raw = cpu_tensor.to(torch.float32).numpy().tobytes()
    digest.update(raw)
    return digest.hexdigest()


def tensor_counts(tensor: Any) -> dict[str, int]:
    import torch

    cpu_tensor = tensor.detach().cpu()
    total = int(cpu_tensor.numel())
    nonzero = int(torch.count_nonzero(cpu_tensor).item()) if total else 0
    floating = cpu_tensor.float() if total else cpu_tensor
    if total and cpu_tensor.is_floating_point():
        nan_count = int(torch.isnan(floating).sum().item())
        inf_count = int(torch.isinf(floating).sum().item())
    else:
        nan_count = 0
        inf_count = 0
    return {
        "total_count": total,
        "zero_count": total - nonzero,
        "nonzero_count": nonzero,
        "nan_count": nan_count,
        "inf_count": inf_count,
    }


def adapter_diff_metrics(init_path: Path, final_path: Path, output_path: Path | None = None) -> dict[str, Any]:
    import torch
    from safetensors.torch import load_file

    init_tensors = load_file(str(init_path), device="cpu")
    final_tensors = load_file(str(final_path), device="cpu")
    tensor_names = sorted(set(init_tensors) | set(final_tensors))
    per_tensor: dict[str, Any] = {}
    missing = []
    total_l2 = 0.0
    any_nonzero_delta = False
    total_nan = 0
    total_inf = 0

    for name in tensor_names:
        if name not in init_tensors or name not in final_tensors:
            missing.append(name)
            continue
        init = init_tensors[name]
        final = final_tensors[name]
        init_float = init.float().reshape(-1)
        final_float = final.float().reshape(-1)
        delta = final_float - init_float
        delta_abs = delta.abs()
        l2_norm = float(torch.linalg.vector_norm(delta).item()) if delta.numel() else 0.0
        max_abs_delta = float(delta_abs.max().item()) if delta_abs.numel() else 0.0
        mean_abs_delta = float(delta_abs.mean().item()) if delta_abs.numel() else 0.0
        init_norm = float(torch.linalg.vector_norm(init_float).item()) if init_float.numel() else 0.0
        final_norm = float(torch.linalg.vector_norm(final_float).item()) if final_float.numel() else 0.0
        if init_norm == 0.0 and final_norm == 0.0:
            cosine_similarity = 1.0
        elif init_norm == 0.0 or final_norm == 0.0:
            cosine_similarity = 0.0
        else:
            cosine_similarity = float(torch.nn.functional.cosine_similarity(init_float, final_float, dim=0).item())

        delta_counts = tensor_counts(delta)
        init_counts = tensor_counts(init)
        final_counts = tensor_counts(final)
        any_nonzero_delta = any_nonzero_delta or delta_counts["nonzero_count"] > 0
        total_l2 += l2_norm
        total_nan += init_counts["nan_count"] + final_counts["nan_count"] + delta_counts["nan_count"]
        total_inf += init_counts["inf_count"] + final_counts["inf_count"] + delta_counts["inf_count"]

        per_tensor[name] = {
            "shape": list(init.shape),
            "dtype_initial": str(init.dtype),
            "dtype_final": str(final.dtype),
            "initial_sha256": tensor_sha256(init),
            "final_sha256": tensor_sha256(final),
            "l2_norm": l2_norm,
            "max_abs_delta": max_abs_delta,
            "mean_abs_delta": mean_abs_delta,
            "cosine_similarity": cosine_similarity,
            "initial_counts": init_counts,
            "final_counts": final_counts,
            "delta_counts": delta_counts,
        }

    metrics = {
        "created_at": utc_now(),
        "status": "pass" if not missing and total_nan == 0 and total_inf == 0 else "failed",
        "adapter_init": file_metadata(init_path),
        "adapter_final": file_metadata(final_path),
        "tensor_count": len(per_tensor),
        "missing_tensors": missing,
        "summary": {
            "total_l2_norm_sum": total_l2,
            "any_nonzero_delta": any_nonzero_delta,
            "nan_count": total_nan,
            "inf_count": total_inf,
        },
        "per_tensor": per_tensor,
    }
    if output_path is not None:
        write_json(output_path, metrics)
    return metrics
