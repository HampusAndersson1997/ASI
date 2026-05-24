from pathlib import Path
import json
from collections import Counter, defaultdict

ROOT = Path(r"C:\Users\J\Sandbox\arc_dataset_library")
INDEX = ROOT / "normalized" / "arc_tasks_index_dedup.jsonl"
OUT = ROOT / "normalized" / "baseline_report.json"

def is_grid(x):
    return (
        isinstance(x, list)
        and len(x) > 0
        and all(isinstance(row, list) and len(row) > 0 for row in x)
        and all(len(row) == len(x[0]) for row in x)
        and all(all(isinstance(v, int) and 0 <= v <= 9 for v in row) for row in x)
    )

def shape(g):
    return (len(g), len(g[0]))

def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def load_task(record):
    obj = load_json(record["path"])
    if isinstance(obj, dict) and "train" in obj and "test" in obj:
        return obj
    return obj[record["task_id"]]

def flatten(g):
    return [v for row in g for v in row]

def most_common_color(g):
    return Counter(flatten(g)).most_common(1)[0][0]

def fill_like_input(inp, color):
    h, w = shape(inp)
    return [[color for _ in range(w)] for _ in range(h)]

def identity(inp):
    return [row[:] for row in inp]

def zero_fill(inp):
    return fill_like_input(inp, 0)

def mode_fill(inp):
    return fill_like_input(inp, most_common_color(inp))

BASELINES = {
    "identity": identity,
    "zero_fill": zero_fill,
    "mode_fill": mode_fill,
}

def exact(a, b):
    return a == b

records = []
with INDEX.open("r", encoding="utf-8") as f:
    for line in f:
        if line.strip():
            records.append(json.loads(line))

# Keep benchmark clean: official ARC only.
official = [
    r for r in records
    if r["source"] in {"ARC-AGI-1", "ARC-AGI-2"}
]

stats = defaultdict(lambda: defaultdict(lambda: {
    "tasks": 0,
    "pairs": 0,
    "exact_pairs": 0,
    "exact_tasks": 0,
}))

fail_samples = []

for r in official:
    task = load_task(r)

    for baseline_name, fn in BASELINES.items():
        task_all_train_exact = True

        for pair in task["train"]:
            pred = fn(pair["input"])
            ok = exact(pred, pair["output"])

            key = f"{r['source']}/{r['split']}/train_pairs"
            s = stats[baseline_name][key]
            s["pairs"] += 1
            s["exact_pairs"] += int(ok)

            if not ok:
                task_all_train_exact = False

        key_task = f"{r['source']}/{r['split']}/train_tasks"
        stats[baseline_name][key_task]["tasks"] += 1
        stats[baseline_name][key_task]["exact_tasks"] += int(task_all_train_exact)

        # Score known test outputs only when present.
        known_test_pairs = [
            p for p in task["test"]
            if "output" in p and is_grid(p["output"])
        ]

        if known_test_pairs:
            task_all_test_exact = True

            for pair in known_test_pairs:
                pred = fn(pair["input"])
                ok = exact(pred, pair["output"])

                key = f"{r['source']}/{r['split']}/test_pairs_known"
                s = stats[baseline_name][key]
                s["pairs"] += 1
                s["exact_pairs"] += int(ok)

                if not ok:
                    task_all_test_exact = False

            key_task = f"{r['source']}/{r['split']}/test_tasks_known"
            stats[baseline_name][key_task]["tasks"] += 1
            stats[baseline_name][key_task]["exact_tasks"] += int(task_all_test_exact)

def add_rates(d):
    out = {}
    for baseline, groups in d.items():
        out[baseline] = {}
        for group, s in groups.items():
            s = dict(s)
            if s["pairs"]:
                s["pair_accuracy"] = s["exact_pairs"] / s["pairs"]
            if s["tasks"]:
                s["task_accuracy"] = s["exact_tasks"] / s["tasks"]
            out[baseline][group] = s
    return out

report = {
    "scope": "official ARC-AGI-1 and ARC-AGI-2 only",
    "records_used": len(official),
    "baselines": list(BASELINES.keys()),
    "results": add_rates(stats),
    "notes": [
        "identity copies input grid as output",
        "zero_fill outputs same input shape filled with 0",
        "mode_fill outputs same input shape filled with input's most common color",
        "These are floor baselines, not serious solvers"
    ],
}

OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))