from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from common import ROOT, sha256_file, utc_now, write_json


def card_value(card_data: Any, key: str) -> Any:
    if card_data is None:
        return None
    if isinstance(card_data, dict):
        return card_data.get(key)
    return getattr(card_data, key, None)


def iter_snapshot_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if ".cache" in path.parts:
            continue
        files.append(path)
    return sorted(files)


def main() -> int:
    parser = argparse.ArgumentParser(description="Download model snapshot and record provenance/checksums.")
    parser.add_argument("--model-id", default="Qwen/Qwen3.5-4B")
    parser.add_argument("--revision", default="main")
    parser.add_argument("--local-dir", type=Path, default=ROOT / "models" / "Qwen--Qwen3.5-4B")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "model_manifest_qwen3_5_4b.json")
    parser.add_argument("--local-files-only", action="store_true")
    parser.add_argument("--metadata-only", action="store_true", help="Record Hugging Face metadata without downloading files.")
    args = parser.parse_args()

    try:
        from huggingface_hub import HfApi, snapshot_download
    except Exception as exc:  # pragma: no cover - dependency is installed in WSL env
        raise SystemExit(f"huggingface_hub import failed: {type(exc).__name__}: {exc}") from exc

    api = HfApi()
    info = api.model_info(args.model_id, revision=args.revision, files_metadata=True)
    card_data = getattr(info, "card_data", None)

    manifest: dict[str, Any] = {
        "created_at": utc_now(),
        "model_id": args.model_id,
        "source_url": f"https://huggingface.co/{args.model_id}",
        "requested_revision": args.revision,
        "resolved_revision": getattr(info, "sha", None),
        "license": card_value(card_data, "license"),
        "pipeline_tag": getattr(info, "pipeline_tag", None),
        "tags": getattr(info, "tags", []),
        "local_dir": str(args.local_dir),
        "metadata_only": args.metadata_only,
        "local_files_only": args.local_files_only,
        "files": [],
        "status": "metadata_recorded" if args.metadata_only else "failed",
    }

    if not args.metadata_only:
        snapshot_path = Path(
            snapshot_download(
                repo_id=args.model_id,
                revision=args.revision,
                local_dir=str(args.local_dir),
                local_files_only=args.local_files_only,
            )
        )
        files = []
        for file_path in iter_snapshot_files(snapshot_path):
            files.append(
                {
                    "path": str(file_path),
                    "relative_path": str(file_path.relative_to(snapshot_path)),
                    "size_bytes": file_path.stat().st_size,
                    "sha256": sha256_file(file_path),
                }
            )
        manifest["local_dir"] = str(snapshot_path)
        manifest["files"] = files
        manifest["file_count"] = len(files)
        manifest["status"] = "pass" if files else "failed"

    write_json(args.output, manifest)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0 if manifest["status"] in {"pass", "metadata_recorded"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
