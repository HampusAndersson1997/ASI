from pathlib import Path
import json
from collections import Counter

ROOT = Path(r"C:\Users\J\Sandbox\arc_dataset_library")
INDEX = ROOT / "normalized" / "arc_tasks_index_dedup.jsonl"
OUT = ROOT / "normalized" / "verifier_selftest_summary.json"

def is_grid(x):
    return (
        isinstance(x, list)
        and len(x) > 0
        and all(isinstance(row, list) and len(row) > 0 for row in x)
        and all(len(row) == len(x[0]) for row in x)
        and all(all(isinstance(v, int) and 0 <= v <= 9 for v in row) for row in x)
    )

def grid_shape(g):
    return [len(g), len(g[0])] if is_grid(g) else None

def exact_match(a, b):
    return a == b

def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))

def load_task(record):
    path = Path(record["path"])
    obj = load_json(path)

    if isinstance(obj, dict) and "train" in obj and "test" in obj:
        return obj

    task_id = record["task_id"]
    if isinstance(obj, dict) and task_id in obj:
        return obj[task_id]

    raise ValueError(f"Could not locate task_id={task_id} in {path}")

def validate_task_schema(task):
    errors = []

    if not isinstance(task, dict):
        return ["task_not_dict"]

    if "train" not in task:
        errors.append("missing_train")
    if "test" not in task:
        errors.append("missing_test")

    for split in ["train", "test"]:
        pairs = task.get(split)
        if not isinstance(pairs, list) or not pairs:
            errors.append(f"{split}_not_nonempty_list")
            continue

        for i, pair in enumerate(pairs):
            if not isinstance(pair, dict):
                errors.append(f"{split}_{i}_pair_not_dict")
                continue

            if not is_grid(pair.get("input")):
                errors.append(f"{split}_{i}_bad_input_grid")

            if split == "train":
                if not is_grid(pair.get("output")):
                    errors.append(f"{split}_{i}_bad_output_grid")
            else:
                # Some public eval/test examples include output, some do not.
                if "output" in pair and not is_grid(pair.get("output")):
                    errors.append(f"{split}_{i}_bad_optional_output_grid")

    return errors

def score_prediction(prediction, expected):
    if not is_grid(prediction):
        return {
            "valid": False,
            "exact": False,
            "error": "prediction_not_valid_grid",
            "pred_shape": None,
            "expected_shape": grid_shape(expected),
        }

    if not is_grid(expected):
        return {
            "valid": False,
            "exact": False,
            "error": "expected_not_valid_grid",
            "pred_shape": grid_shape(prediction),
            "expected_shape": None,
        }

    return {
        "valid": True,
        "exact": exact_match(prediction, expected),
        "error": None,
        "pred_shape": grid_shape(prediction),
        "expected_shape": grid_shape(expected),
    }

records = []
with INDEX.open("r", encoding="utf-8") as f:
    for line in f:
        if line.strip():
            records.append(json.loads(line))

schema_errors = []
shape_counter = Counter()
source_counter = Counter()

for r in records:
    try:
        task = load_task(r)
        errors = validate_task_schema(task)
    except Exception as e:
        schema_errors.append({
            "record": r,
            "errors": [f"load_failed: {e}"],
        })
        continue

    if errors:
        schema_errors.append({
            "record": r,
            "errors": errors,
        })

    source_counter[r["source"]] += 1

    for pair in task.get("train", []):
        if is_grid(pair.get("input")) and is_grid(pair.get("output")):
            shape_counter[
                f"{grid_shape(pair['input'])}->{grid_shape(pair['output'])}"
            ] += 1

summary = {
    "records_checked": len(records),
    "schema_error_records": len(schema_errors),
    "schema_error_sample": schema_errors[:25],
    "by_source": dict(source_counter),
    "top_train_shape_mappings": shape_counter.most_common(30),
    "verifier_functions": [
        "is_grid",
        "grid_shape",
        "exact_match",
        "validate_task_schema",
        "score_prediction"
    ]
}

OUT.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps(summary, indent=2, ensure_ascii=False))