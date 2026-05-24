from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from supabase import create_client


ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = ROOT / "logs"
LOG_PATH = LOG_DIR / "agent_actions.jsonl"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def log_action(event: dict[str, Any]) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    record = {"logged_at": utc_now(), **event}
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def load_metadata(args: argparse.Namespace) -> dict[str, Any]:
    if args.metadata_file:
        metadata = json.loads(Path(args.metadata_file).read_text(encoding="utf-8-sig"))
    else:
        metadata = json.loads(args.metadata_json)

    if not isinstance(metadata, dict):
        raise ValueError("metadata must decode to a JSON object")

    return metadata


def make_client() -> Any:
    load_dotenv(ROOT / ".env", override=True, encoding="utf-8-sig")
    supabase_url = require_env("SUPABASE_URL")
    supabase_key = require_env("SUPABASE_SERVICE_ROLE_KEY")
    return create_client(supabase_url, supabase_key)


def find_existing_memory(
    *,
    client: Any,
    namespace: str,
    title: str,
    content: str,
) -> dict[str, Any] | None:
    result = (
        client.table("memories")
        .select("*")
        .eq("namespace", namespace)
        .eq("title", title)
        .eq("content", content)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def save_memory(
    *,
    namespace: str,
    title: str,
    content: str,
    tags: list[str],
    confidence: float,
    metadata: dict[str, Any],
    dedupe: bool,
) -> dict[str, Any]:
    if not 0 <= confidence <= 1:
        raise ValueError("confidence must be between 0 and 1")

    client = make_client()
    digest = content_hash(content)

    log_action({
        "action": "save_memory_attempt",
        "table": "public.memories",
        "title": title,
        "namespace": namespace,
        "tags": tags,
        "content_hash": digest,
        "dedupe": dedupe,
    })

    if dedupe:
        existing = find_existing_memory(
            client=client,
            namespace=namespace,
            title=title,
            content=content,
        )
        if existing:
            log_action({
                "action": "save_memory_skipped_duplicate",
                "table": "public.memories",
                "memory_id": existing.get("id"),
                "title": existing.get("title"),
                "namespace": existing.get("namespace"),
                "content_hash": digest,
            })
            return existing

    payload = {
        "namespace": namespace,
        "title": title,
        "content": content,
        "tags": tags,
        "confidence": confidence,
        "metadata": {
            **metadata,
            "content_hash": digest,
            "saved_by": "tools/python/save_memory.py",
            "local_root": str(ROOT),
            "saved_at": utc_now(),
            "dedupe_enabled": dedupe,
        },
    }

    result = client.table("memories").insert(payload).execute()

    if not result.data:
        log_action({
            "action": "save_memory_failed",
            "reason": "Supabase insert returned no data",
            "payload_title": title,
            "content_hash": digest,
        })
        raise RuntimeError("Supabase insert returned no data")

    row = result.data[0]

    log_action({
        "action": "save_memory_success",
        "table": "public.memories",
        "memory_id": row.get("id"),
        "title": row.get("title"),
        "namespace": row.get("namespace"),
        "content_hash": digest,
    })

    return row


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Save a verified memory into ASI Kernel Supabase public.memories."
    )
    parser.add_argument("--title", required=True)
    parser.add_argument("--content", required=True)
    parser.add_argument("--namespace", default="asi_kernel")
    parser.add_argument("--tags", default="", help="Comma-separated tags")
    parser.add_argument("--confidence", type=float, default=1.0)
    parser.add_argument("--metadata-json", default="{}", help="JSON metadata object")
    parser.add_argument("--metadata-file", default=None, help="Path to JSON metadata file")
    parser.add_argument(
        "--no-dedupe",
        action="store_true",
        help="Disable duplicate detection and always insert",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        metadata = load_metadata(args)
        tags = [tag.strip() for tag in args.tags.split(",") if tag.strip()]

        row = save_memory(
            namespace=args.namespace,
            title=args.title,
            content=args.content,
            tags=tags,
            confidence=args.confidence,
            metadata=metadata,
            dedupe=not args.no_dedupe,
        )

        print(json.dumps(row, indent=2, ensure_ascii=False, sort_keys=True))
        return 0

    except Exception as exc:
        log_action({
            "action": "save_memory_exception",
            "error": repr(exc),
        })
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
