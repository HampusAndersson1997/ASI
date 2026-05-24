from __future__ import annotations

import argparse
import json
import os
import platform
import sys
from pathlib import Path

from common import utc_now, write_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Record PyTorch CUDA visibility.")
    parser.add_argument("--output", type=Path, default=Path("/mnt/d/Sandbox/local_llm/artifacts/torch_cuda_check.json"))
    parser.add_argument("--allow-missing", action="store_true")
    args = parser.parse_args()

    result = {
        "checked_at": utc_now(),
        "python": sys.version,
        "platform": platform.platform(),
        "path_has_wsl_lib": "/usr/lib/wsl/lib" in os.environ.get("PATH", "").split(":"),
        "cuda_available": False,
        "status": "failed"
    }

    try:
        import torch
    except Exception as exc:  # pragma: no cover - depends on local env
        result["error"] = f"torch_import_failed: {type(exc).__name__}: {exc}"
        write_json(args.output, result)
        return 0 if args.allow_missing else 2

    result.update(
        {
            "torch_version": getattr(torch, "__version__", "unknown"),
            "torch_cuda_version": getattr(torch.version, "cuda", None),
            "cuda_available": bool(torch.cuda.is_available()),
            "device_count": int(torch.cuda.device_count()) if torch.cuda.is_available() else 0,
            "devices": [
                torch.cuda.get_device_name(index) for index in range(torch.cuda.device_count())
            ]
            if torch.cuda.is_available()
            else []
        }
    )
    result["status"] = "pass" if result["cuda_available"] else "failed"
    write_json(args.output, result)
    return 0 if result["cuda_available"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
