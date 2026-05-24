from pathlib import Path
import json
from collections import Counter, defaultdict

ROOT = Path(r"C:\Users\J\Sandbox\arc_dataset_library")
DATASETS = ROOT / "datasets"
OUT_DIR = ROOT / "normalized"
OUT_DIR.mkdir(exist_ok=True)

def is_grid(x):
    return (
        isinstance(x, list)
        and all(isinstance(row, list) for row in x)
        and all(all(isinstance(v, int) for v in row) for row in x)
    )

def looks_like_arc_task(obj):
    if not isinstance(obj, dict):
        return False
    if "train" not in obj or "test" not in obj:
        return False
    if not isinstance(obj["train"], list) or not isinstance(obj["test"], list):
        return False
    for pair in obj["train"]:
        if not isinstance(pair, dict):
            return False
        if not is_grid(pair.get("input")) or not is_grid(pair.get("output")):
            return False
    for pair in obj["test"]:
        if not isinstance(pair, dict):
            return False
        if not is_grid(pair.get("input")):
            return False
    return True

def infer_source(path: Path):
    p = str(path).replace("\\", "/").lower()
    if "arc-agi-2" in p:
        return "ARC-AGI-2"
    if "arc-agi-1" in p or "arc-agi/" in p:
        return "ARC-AGI-1"
    if "conceptarc" in p:
        return "ConceptARC"
    if "mini-arc" in p:
        return "MINI-ARC"
    if "re-arc" in p:
        return "RE-ARC"
    if "arc-gen" in p:
        return "ARC-GEN"
    return "unknown"

def infer_split(path: Path):
    p = str(path).replace("\\", "/").lower()
    if "training" in p or "/train" in p or "\\train" in p:
        return "train"
    if "evaluation" in p or "/eval" in p or "\\eval" in p:
        return "eval"
    if "test" in p:
        return "test"
    return "unknown"

records = []
errors = []

for path in DATASETS.rglob("*.json"):
    if ".git" in path.parts or ".cache" in path.parts:
        continue
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        errors.append({"path": str(path), "error": f"json_load_failed: {e}"})
        continue

    # Case 1: one file = one ARC task
    if looks_like_arc_task(obj):
        task_id = path.stem
        records.append({
            "task_id": task_id,
            "source": infer_source(path),
            "split": infer_split(path),
            "path": str(path),
            "train_pairs": len(obj["train"]),
            "test_pairs": len(obj["test"]),
        })
        continue

    # Case 2: one file = dict of task_id -> task
    if isinstance(obj, dict):
        for key, value in obj.items():
            if looks_like_arc_task(value):
                records.append({
                    "task_id": str(key),
                    "source": infer_source(path),
                    "split": infer_split(path),
                    "path": str(path),
                    "train_pairs": len(value["train"]),
                    "test_pairs": len(value["test"]),
                })

out_jsonl = OUT_DIR / "arc_tasks_index.jsonl"
with out_jsonl.open("w", encoding="utf-8") as f:
    for r in records:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

summary = {
    "total_tasks_indexed": len(records),
    "by_source": dict(Counter(r["source"] for r in records)),
    "by_split": dict(Counter(r["split"] for r in records)),
    "by_source_split": {
        f"{source}/{split}": count
        for (source, split), count in Counter((r["source"], r["split"]) for r in records).items()
    },
    "errors_count": len(errors),
    "errors_sample": errors[:20],
}

(OUT_DIR / "arc_tasks_summary.json").write_text(
    json.dumps(summary, indent=2, ensure_ascii=False),
    encoding="utf-8"
)

print(json.dumps(summary, indent=2, ensure_ascii=False))