# Local LLM Measurement Harness V2

Observed at: 2026-05-23

## Fact

- Harness code records run manifests, package versions, CUDA status, command arguments, prompt hashes, model revision metadata, verifier version, decoding settings, and artifact hashes.
- Training code saves `adapter_init.safetensors`, `adapter_final.safetensors`, and `adapter_diff_metrics.json` for future LoRA runs.
- Tiny dry-run artifact: `D:\Sandbox\local_llm\artifacts\runs\20260523_measure_harness_acceptance`.
- Tiny dry-run result: `status=pass`, nonzero adapter deltas recorded, `nan_count=0`, `inf_count=0`.
- V2 held-out prompt file: `D:\Sandbox\local_llm\prompts\heldout_prompts_v2.jsonl`.
- V2 held-out inference run: `D:\Sandbox\local_llm\artifacts\runs\20260523_v2_heldout`.
- V2 held-out trace manifest: `D:\Sandbox\local_llm\artifacts\runs\20260523_v2_heldout_scored_trace_v3\run_manifest.json`.
- V2 held-out prompt SHA256: `70f9f123ae738eddd2623387f68d4657510114461124da49ffc5ec7d720ce1f5`.
- Model revision: `851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`.
- Verifier version: `2026-05-23.risk-boundary-calibration`.
- Decoding settings: `max_new_tokens=512`, `do_sample=false`, `load_in_4bit=true`, `enable_thinking=false`.
- V2 held-out comparison result: `unchanged`.

## Metrics

- Base held-out: accepted `0/3`, valid JSON rate `0.0`.
- Adapter v1 held-out: accepted `0/3`, valid JSON rate `1.0`.
- Base failures: `truncated output=2`, `invalid JSON=1`.
- Adapter failures: `unclassified evidence=3`, with additional weak risk boundary and non-executable abstraction reasons in details.

## Inference

Adapter v1 improves JSON formatting on the v2 held-out prompts, but this is not an accepted model improvement under the comparator because accepted proposal count did not increase.

## Verification

- `wsl.exe -d archlinux -- bash -lc "cd /mnt/d/Sandbox/local_llm && .venv/bin/python -m unittest discover -s tests -v"` passed: 11 tests.
- Comparison emitted exactly one allowed label: `unchanged`.
- No claim of general ASI/ARC capability is supported by this evidence.

## Open Follow-Up

- Add file locking or avoid parallel writes when multiple processes update the same `run_manifest.json`.
- Improve adapter outputs so evidence fields explicitly classify `fact`, `inference`, `hypothesis`, or `unknown`, and risk boundaries include explicit allowed/forbidden/stop terms.
