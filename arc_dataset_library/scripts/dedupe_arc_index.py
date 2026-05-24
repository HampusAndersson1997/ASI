from pathlib import Path
import json
import hashlib
from collections import Counter

ROOT = Path(r"C:\Users\J\Sandbox\arc_dataset_library")
IN_PATH = ROOT / "normalized" / "arc_tasks_index.jsonl"
OUT_PATH = ROOT / "normalized" / "arc_tasks_index_dedup.jsonl"
SUMMARY_PATH = ROOT / "normalized" / "arc_tasks_dedup_summary.json"
DUPES_PATH = ROOT / "normalized" / "arc_tasks_duplicates.jsonl"

def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))

def load_task(record):
    path = Path(record["path"])
    obj = load_json(path)

    # one file = one ARC task
    if isinstance(obj, dict) and "train" in obj and "test" in obj:
        return obj

    # one file = dict of task_id -> task
    task_id = record["task_id"]
    if isinstance(obj, dict) and task_id in obj:
        return obj[task_id]

    raise ValueError(f"Could not locate task_id={task_id} in {path}")

def canonical_hash(task):
    s = json.dumps(task, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

records = []
with IN_PATH.open("r", encoding="utf-8") as f:
    for line in f:
        if line.strip():
            records.append(json.loads(line))

seen = {}
deduped = []
duplicates = []
errors = []

for r in records:
    try:
        task = load_task(r)
        h = canonical_hash(task)
    except Exception as e:
        errors.append({"record": r, "error": str(e)})
        continue

    r2 = dict(r)
    r2["task_sha256"] = h

    # Dedupe within source/split/content.
    # This keeps ARC-AGI-1 separate from ARC-AGI-2 even if some task content matched by accident.
    key = (r2["source"], r2["split"], h)

    if key in seen:
        duplicates.append({
            "kept": seen[key],
            "duplicate": r2
        })
    else:
        seen[key] = r2
        deduped.append(r2)

with OUT_PATH.open("w", encoding="utf-8") as f:
    for r in deduped:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

with DUPES_PATH.open("w", encoding="utf-8") as f:
    for d in duplicates:
        f.write(json.dumps(d, ensure_ascii=False) + "\n")

unknown_parent_dirs = Counter(
    str(Path(r["path"]).parent)
    for r in records
    if r.get("source") == "unknown"
)

summary = {
    "input_records": len(records),
    "deduped_records": len(deduped),
    "duplicates_removed": len(duplicates),
    "errors_count": len(errors),
    "errors_sample": errors[:20],
    "deduped_by_source": dict(Counter(r["source"] for r in deduped)),
    "deduped_by_split": dict(Counter(r["split"] for r in deduped)),
    "deduped_by_source_split": {
        f"{source}/{split}": count
        for (source, split), count in Counter((r["source"], r["split"]) for r in deduped).items()
    },
    "unknown_parent_dirs_top_30": unknown_parent_dirs.most_common(30),
    "outputs": {
        "dedup_index": str(OUT_PATH),
        "duplicates": str(DUPES_PATH),
        "summary": str(SUMMARY_PATH)
    }
}

SUMMARY_PATH.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps(summary, indent=2, ensure_ascii=False))
