I inspected read-only. I did not run pytest because the current tests write `logs/` and `memory/` artifacts.

**File Tree**
- Root: [README.md](</D:/Sandbox/asi_kernel/README.md>), `.env`, `.env.example`, `.gitignore`, `.git/`, `.venv/`.
- Core code: [arc_agi_2/object_extractor.py](</D:/Sandbox/asi_kernel/arc_agi_2/object_extractor.py>), [dashboards/progress_report.py](</D:/Sandbox/asi_kernel/dashboards/progress_report.py>).
- Harness tools: `tools/codex_cli/` wrapper, schema, template, PowerShell preflight; `tools/python/` scoring/failure/memory helpers; `tools/memory/` JSONL memory helpers.
- State/docs: `goals/`, `loop/`, `verification/`, `skills/`.
- Run data: `logs/`, `memory/`, `artifacts/`.
- Empty/scaffold dirs: `data/arc_agi_2`, `projects/arc_agi_2`, `verification/benchmarks`, `verification/tests`, `tools/kaggle`, `tools/llama_cpp`, `tools/powershell`, `memory/quarantine`, `arc_agi_2/reports`.

Observed inventory excluding `.git/.venv` contents: 61 files, 34 dirs. Main languages: Python, PowerShell, Markdown, JSON/JSONL.

**Existing Tests**
Two pytest files with 15 test functions:
- [tests/test_codex_cli_wrapper.py](</D:/Sandbox/asi_kernel/tests/test_codex_cli_wrapper.py>): wrapper path/risk/flag rejection, dry-run command shape, audit log, output path, preflight generation.
- [tests/test_codex_phase2.py](</D:/Sandbox/asi_kernel/tests/test_codex_phase2.py>): scoring pass path, one failure classifier path, memory pass/failure write, fake non-dry-run wrapper flow, dashboard summary.

**Missing Tests**
- No pytest coverage for [arc_agi_2/object_extractor.py](</D:/Sandbox/asi_kernel/arc_agi_2/object_extractor.py>) despite a substantial 425-line extractor. Its self-test should be promoted into pytest coverage for grid validation, 4/8 connectivity, background inclusion, mixed-color components, JSON task loading, and CLI report output.
- [tools/python/save_memory.py](</D:/Sandbox/asi_kernel/tools/python/save_memory.py>) has no tests. It needs mocked Supabase/env tests for insert/update behavior, metadata loading, tag/confidence handling, and failure logging.
- Wrapper validation has partial negative coverage only. Missing cases include missing fields, wrong types, empty arrays, duration/depth bounds, escaped expected output paths, absolute paths outside root inside validation commands, and schema/template consistency.
- [tools/python/score_result.py](</D:/Sandbox/asi_kernel/tools/python/score_result.py>) mostly has a pass-path test. Missing failure tests: validation timeout, failed command, missing expected output, output outside root, no validation commands, and nonzero delegation exits.
- [tools/python/classify_failure.py](</D:/Sandbox/asi_kernel/tools/python/classify_failure.py>) only tests `validation_failed`; missing classes include rejected/unsafe task, timeout, missing Codex CLI, output missing, path policy violation, delegation failed, and unknown failure.
- PowerShell wrapper [tools/codex_cli/run_codex_exec.ps1](</D:/Sandbox/asi_kernel/tools/codex_cli/run_codex_exec.ps1>) has no dedicated test.
- `verification/benchmarks` and `verification/tests` are empty, so there is no benchmark/regression suite for the stated harness loop yet.