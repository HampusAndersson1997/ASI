#!/usr/bin/env python3
"""
ARC-AGI object extractor.

Prime Directive fit:
- Goal: extract grounded object features from ARC-style grids.
- Verify: `python object_extractor.py --self-test` uses deterministic synthetic cases.
- Compress: report JSON gives compact task/object statistics for downstream priors/DSL.

Assumptions, made explicit:
- ARC grids are rectangular 2D integer arrays.
- Default background color is 0.
- Default objects are same-color connected components over non-background cells.
- Connectivity defaults to 4-neighbor. Use `--connectivity 8` for diagonal adjacency.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import tempfile
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Literal

Grid = list[list[int]]
Cell = tuple[int, int]
Connectivity = Literal[4, 8]


@dataclass(frozen=True)
class BoundingBox:
    r0: int
    c0: int
    r1: int
    c1: int

    @property
    def height(self) -> int:
        return self.r1 - self.r0 + 1

    @property
    def width(self) -> int:
        return self.c1 - self.c0 + 1

    @property
    def area(self) -> int:
        return self.height * self.width


@dataclass(frozen=True)
class ExtractedObject:
    id: int
    color: int | str
    size: int
    cells: list[Cell]
    bbox: BoundingBox
    centroid: tuple[float, float]
    touches_border: bool
    perimeter_4: int
    density: float
    normalized_shape: list[Cell]


def validate_grid(grid: Any, *, name: str = "grid") -> Grid:
    """Validate and normalize an ARC-style rectangular integer grid."""
    if not isinstance(grid, list) or not grid:
        raise ValueError(f"{name} must be a non-empty list of rows")
    if not all(isinstance(row, list) and row for row in grid):
        raise ValueError(f"{name} must contain non-empty row lists")

    width = len(grid[0])
    normalized: Grid = []
    for r, row in enumerate(grid):
        if len(row) != width:
            raise ValueError(f"{name} is not rectangular: row 0 has width {width}, row {r} has width {len(row)}")
        out_row: list[int] = []
        for c, value in enumerate(row):
            if not isinstance(value, int):
                raise ValueError(f"{name}[{r}][{c}] must be int, got {type(value).__name__}")
            out_row.append(value)
        normalized.append(out_row)
    return normalized


def grid_shape(grid: Grid) -> tuple[int, int]:
    return len(grid), len(grid[0])


def iter_neighbors(r: int, c: int, rows: int, cols: int, connectivity: Connectivity) -> Iterator[Cell]:
    deltas_4 = [(-1, 0), (0, 1), (1, 0), (0, -1)]
    deltas_8 = deltas_4 + [(-1, -1), (-1, 1), (1, 1), (1, -1)]
    deltas = deltas_4 if connectivity == 4 else deltas_8
    for dr, dc in deltas:
        nr, nc = r + dr, c + dc
        if 0 <= nr < rows and 0 <= nc < cols:
            yield nr, nc


def should_include(value: int, background: int | None, include_background: bool) -> bool:
    if background is None:
        return True
    return include_background or value != background


def object_bbox(cells: Iterable[Cell]) -> BoundingBox:
    cell_list = list(cells)
    rows = [r for r, _ in cell_list]
    cols = [c for _, c in cell_list]
    return BoundingBox(min(rows), min(cols), max(rows), max(cols))


def normalize_cells(cells: Iterable[Cell]) -> list[Cell]:
    cell_list = sorted(cells)
    min_r = min(r for r, _ in cell_list)
    min_c = min(c for _, c in cell_list)
    return [(r - min_r, c - min_c) for r, c in cell_list]


def perimeter_4(cells: set[Cell]) -> int:
    p = 0
    for r, c in cells:
        for dr, dc in [(-1, 0), (0, 1), (1, 0), (0, -1)]:
            if (r + dr, c + dc) not in cells:
                p += 1
    return p


def extract_objects(
    grid: Any,
    *,
    background: int | None = 0,
    include_background: bool = False,
    connectivity: Connectivity = 4,
    by_color: bool = True,
    keep_cells: bool = True,
) -> list[ExtractedObject]:
    """
    Extract connected-component objects from an ARC grid.

    by_color=True means cells only connect to same-color cells.
    by_color=False means all included cells can connect, regardless of color.
    """
    if connectivity not in (4, 8):
        raise ValueError("connectivity must be 4 or 8")

    g = validate_grid(grid)
    rows, cols = grid_shape(g)
    visited: set[Cell] = set()
    objects: list[ExtractedObject] = []

    for sr in range(rows):
        for sc in range(cols):
            if (sr, sc) in visited:
                continue
            start_color = g[sr][sc]
            if not should_include(start_color, background, include_background):
                visited.add((sr, sc))
                continue

            stack = [(sr, sc)]
            visited.add((sr, sc))
            component: list[Cell] = []
            colors: Counter[int] = Counter()

            while stack:
                r, c = stack.pop()
                component.append((r, c))
                colors[g[r][c]] += 1

                for nr, nc in iter_neighbors(r, c, rows, cols, connectivity):
                    if (nr, nc) in visited:
                        continue
                    value = g[nr][nc]
                    if not should_include(value, background, include_background):
                        visited.add((nr, nc))
                        continue
                    if by_color and value != start_color:
                        continue
                    visited.add((nr, nc))
                    stack.append((nr, nc))

            component_sorted = sorted(component)
            bbox = object_bbox(component_sorted)
            size = len(component_sorted)
            centroid = (
                round(sum(r for r, _ in component_sorted) / size, 6),
                round(sum(c for _, c in component_sorted) / size, 6),
            )
            touches = any(r in (0, rows - 1) or c in (0, cols - 1) for r, c in component_sorted)
            color: int | str
            if by_color or len(colors) == 1:
                color = next(iter(colors.keys()))
            else:
                color = "mixed:" + ",".join(f"{k}x{v}" for k, v in sorted(colors.items()))

            objects.append(
                ExtractedObject(
                    id=len(objects),
                    color=color,
                    size=size,
                    cells=component_sorted if keep_cells else [],
                    bbox=bbox,
                    centroid=centroid,
                    touches_border=touches,
                    perimeter_4=perimeter_4(set(component_sorted)),
                    density=round(size / bbox.area, 6),
                    normalized_shape=normalize_cells(component_sorted),
                )
            )

    return objects


def object_to_json(obj: ExtractedObject) -> dict[str, Any]:
    d = asdict(obj)
    d["bbox"] = asdict(obj.bbox)
    # JSON has no tuple type; lists are intentional.
    d["cells"] = [[r, c] for r, c in obj.cells]
    d["normalized_shape"] = [[r, c] for r, c in obj.normalized_shape]
    d["centroid"] = [obj.centroid[0], obj.centroid[1]]
    return d


def color_histogram(grid: Grid) -> dict[str, int]:
    counts: Counter[int] = Counter()
    for row in grid:
        counts.update(row)
    return {str(k): v for k, v in sorted(counts.items())}


def grid_summary(grid: Any, *, background: int | None, connectivity: Connectivity, by_color: bool) -> dict[str, Any]:
    g = validate_grid(grid)
    objects = extract_objects(g, background=background, connectivity=connectivity, by_color=by_color, keep_cells=True)
    rows, cols = grid_shape(g)
    sizes = [o.size for o in objects]
    return {
        "shape": [rows, cols],
        "cell_count": rows * cols,
        "color_histogram": color_histogram(g),
        "object_count": len(objects),
        "object_count_by_color": {str(k): v for k, v in sorted(Counter(o.color for o in objects).items(), key=lambda kv: str(kv[0]))},
        "object_sizes": sizes,
        "max_object_size": max(sizes) if sizes else 0,
        "min_object_size": min(sizes) if sizes else 0,
        "objects": [object_to_json(o) for o in objects],
    }


def summarize_arc_task(task_id: str, task: dict[str, Any], *, background: int | None, connectivity: Connectivity, by_color: bool) -> dict[str, Any]:
    if not isinstance(task, dict):
        raise ValueError(f"task {task_id} must be a dict")
    result: dict[str, Any] = {"task_id": task_id, "train": [], "test": []}
    for split in ("train", "test"):
        examples = task.get(split, [])
        if not isinstance(examples, list):
            raise ValueError(f"task {task_id}.{split} must be a list")
        for idx, ex in enumerate(examples):
            if not isinstance(ex, dict) or "input" not in ex:
                raise ValueError(f"task {task_id}.{split}[{idx}] must contain an input grid")
            item: dict[str, Any] = {"index": idx, "input": grid_summary(ex["input"], background=background, connectivity=connectivity, by_color=by_color)}
            if "output" in ex:
                item["output"] = grid_summary(ex["output"], background=background, connectivity=connectivity, by_color=by_color)
            result[split].append(item)
    return result


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def discover_task_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if path.is_dir():
        return sorted(p for p in path.rglob("*.json") if p.is_file())
    raise FileNotFoundError(path)


def load_tasks(path: Path) -> dict[str, dict[str, Any]]:
    tasks: dict[str, dict[str, Any]] = {}
    for file_path in discover_task_files(path):
        data = load_json(file_path)
        if isinstance(data, dict) and "train" in data and "test" in data:
            tasks[file_path.stem] = data
        elif isinstance(data, dict) and all(isinstance(v, dict) for v in data.values()):
            for key, value in data.items():
                if "train" in value and "test" in value:
                    tasks[str(key)] = value
        else:
            raise ValueError(f"Unsupported ARC JSON shape in {file_path}")
    return tasks


def build_report(input_path: Path, *, background: int | None, connectivity: Connectivity, by_color: bool) -> dict[str, Any]:
    tasks = load_tasks(input_path)
    task_reports = [summarize_arc_task(task_id, task, background=background, connectivity=connectivity, by_color=by_color) for task_id, task in sorted(tasks.items())]
    object_counts = []
    for task_report in task_reports:
        for split in ("train", "test"):
            for ex in task_report[split]:
                object_counts.append(ex["input"]["object_count"])
                if "output" in ex:
                    object_counts.append(ex["output"]["object_count"])
    return {
        "schema_version": 1,
        "extractor": "arc_agi_2.object_extractor",
        "settings": {"background": background, "connectivity": connectivity, "by_color": by_color},
        "task_count": len(task_reports),
        "aggregate": {
            "grid_count": len(object_counts),
            "total_objects": sum(object_counts),
            "mean_objects_per_grid": round(sum(object_counts) / len(object_counts), 6) if object_counts else 0,
            "max_objects_per_grid": max(object_counts) if object_counts else 0,
        },
        "tasks": task_reports,
    }


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")


def assert_equal(actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def run_self_test() -> None:
    grid = [
        [0, 1, 1, 0, 2],
        [0, 1, 0, 0, 2],
        [3, 0, 0, 2, 2],
        [3, 3, 0, 0, 0],
    ]
    objs = extract_objects(grid)
    assert_equal(len(objs), 3, "component count")
    assert_equal([o.color for o in objs], [1, 2, 3], "scan-order colors")
    assert_equal([o.size for o in objs], [3, 4, 3], "component sizes")
    assert_equal(asdict(objs[0].bbox), {"r0": 0, "c0": 1, "r1": 1, "c1": 2}, "bbox object 0")
    assert_equal(objs[0].normalized_shape, [(0, 0), (0, 1), (1, 0)], "normalized L shape")
    assert_equal(objs[1].perimeter_4, 10, "perimeter object 1")

    diagonal = [[1, 0], [0, 1]]
    assert_equal(len(extract_objects(diagonal, connectivity=4)), 2, "4-neighbor diagonal split")
    assert_equal(len(extract_objects(diagonal, connectivity=8)), 1, "8-neighbor diagonal merge")

    mixed = [[1, 2], [0, 2]]
    mixed_objs = extract_objects(mixed, by_color=False)
    assert_equal(len(mixed_objs), 1, "mixed non-background component")
    assert_equal(mixed_objs[0].size, 3, "mixed component size")

    try:
        validate_grid([[1], [1, 2]])
    except ValueError as exc:
        assert "not rectangular" in str(exc)
    else:
        raise AssertionError("ragged grid validation should fail")

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        task = {
            "train": [{"input": grid, "output": [[1, 1], [1, 0]]}],
            "test": [{"input": diagonal}],
        }
        task_path = root / "demo_task.json"
        write_json(task_path, task)
        report = build_report(task_path, background=0, connectivity=4, by_color=True)
        assert_equal(report["task_count"], 1, "report task count")
        assert_equal(report["aggregate"]["grid_count"], 3, "report grid count")
        assert_equal(report["tasks"][0]["train"][0]["input"]["object_count"], 3, "report input object count")

    print("SELF_TEST_PASS object_extractor.py")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract ARC-AGI object features and build object statistics reports.")
    parser.add_argument("--self-test", action="store_true", help="run deterministic self-tests and exit")
    parser.add_argument("--input", type=Path, help="ARC task JSON file or directory of JSON tasks")
    parser.add_argument("--output", type=Path, default=Path("object_stats_report.json"), help="output report JSON path")
    parser.add_argument("--background", type=int, default=0, help="background color to ignore by default")
    parser.add_argument("--include-background", action="store_true", help="include background cells as objects")
    parser.add_argument("--connectivity", type=int, choices=[4, 8], default=4, help="component connectivity")
    parser.add_argument("--mixed-color-components", action="store_true", help="connect all non-background colors into mixed components")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.self_test:
        run_self_test()
        return 0

    if args.input is None:
        print("ERROR: provide --input or use --self-test", file=sys.stderr)
        return 2

    background: int | None = args.background
    if args.include_background:
        # Include every cell; background is still recorded in settings.
        background_for_report = None
    else:
        background_for_report = background

    report = build_report(
        args.input,
        background=background_for_report,
        connectivity=args.connectivity,
        by_color=not args.mixed_color_components,
    )
    write_json(args.output, report)
    print(f"WROTE {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
