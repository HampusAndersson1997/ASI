from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any


ROOT = Path("D:/Sandbox/asi_kernel").resolve(strict=False)
TOOLS_MEMORY = ROOT / "tools" / "memory"
if str(TOOLS_MEMORY) not in sys.path:
    sys.path.insert(0, str(TOOLS_MEMORY))

from init_memory import memory_db_path


VALID_RECORD_TYPES = {"agent_run", "failure"}


def decode_record(row: sqlite3.Row) -> dict[str, Any]:
    record = json.loads(str(row["record_json"]))
    record["record_type"] = str(row["record_type"])
    record["record_id"] = str(row["record_id"])
    record["created_at"] = str(row["created_at"])
    return record


def search_memory(
    query: str,
    *,
    root: Path | str = ROOT,
    record_type: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    if record_type is not None and record_type not in VALID_RECORD_TYPES:
        raise ValueError(f"record_type must be one of: {', '.join(sorted(VALID_RECORD_TYPES))}")
    if limit < 1:
        raise ValueError("limit must be at least 1")

    db_path = memory_db_path(root)
    if not db_path.exists():
        return []

    like_query = f"%{query}%"
    sql = """
        SELECT record_id, record_type, created_at, record_json
        FROM memory_records
        WHERE (
            ? = ''
            OR task_id LIKE ?
            OR status LIKE ?
            OR failure_class LIKE ?
            OR output_file LIKE ?
            OR content_text LIKE ?
            OR record_json LIKE ?
        )
    """
    params: list[Any] = [query, like_query, like_query, like_query, like_query, like_query, like_query]
    if record_type is not None:
        sql += " AND record_type = ?"
        params.append(record_type)
    sql += " ORDER BY created_at DESC, task_id DESC LIMIT ?"
    params.append(limit)

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, params).fetchall()
    return [decode_record(row) for row in rows]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search local ASI Kernel SQLite memory.")
    parser.add_argument("query")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--record-type", choices=sorted(VALID_RECORD_TYPES))
    parser.add_argument("--limit", type=int, default=10)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    results = search_memory(args.query, root=args.root, record_type=args.record_type, limit=args.limit)
    print(json.dumps(results, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
