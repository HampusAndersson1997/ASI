# Strict JSON Verifier V2 Measurement

Date: 2026-05-23

## Verdict

final_comparison_result: regressed

Fact: verifier version is `2026-05-23.strict-json-v2`.
Fact: strict parser tests and verifier regression tests passed: `python -m unittest tests.test_measurement_harness` ran 24 tests OK.
Fact: v2.1 training completed and wrote adapter artifacts, but held-out strict evaluation regressed versus adapter v2.
Inference: the targeted v2.1 examples did not recover exact-JSON termination; they increased trailing transcript failure on the three held-out prompts.

## Instrument Change

Fact: `extract_single_json_object_with_reason(text)` now accepts only optional whitespace around one top-level JSON object.
Fact: non-exact JSON is rejected with `not_exactly_one_json_object` and categorized as `invalid JSON`.
Fact: truncated JSON still maps to `truncated output` through `unterminated_json_object`.
Fact: metrics now include `exact_json_count`, `exact_json_rate`, and `extra_text_after_json_count`.

## Calibration Results

All saved outputs were re-scored as verifier calibration under `D:\Sandbox\local_llm\artifacts\runs\20260523_strict_json_v2`.

| response set | accepted | valid_json_rate | exact_json_rate | extra_text_after_json_count | primary note |
|---|---:|---:|---:|---:|---|
| base | 0/3 | 0.000 | 0.000 | 0 | all truncated |
| adapter v1 | 0/3 | 1.000 | 1.000 | 0 | exact JSON but semantic verifier failures |
| adapter v2 | 1/3 | 0.333 | 0.333 | 2 | old v1-valid trailing outputs now invalid JSON |

Fact: `heldout_v2_001` adapter v2 remains accepted.
Fact: `heldout_v2_002` and `heldout_v2_003` adapter v2 are now `invalid JSON` with `not_exactly_one_json_object`.
Inference: previous `valid_json_rate=1.0` for adapter v2 was a measurement artifact from accepting the first parseable object.

## V2.1 Run

Fact: v2.1 dataset: `D:\Sandbox\local_llm\data\asi_arc_sft_v2_1.jsonl`.
Fact: v2.1 dataset contains 23 records: 18 v2 records plus 5 targeted strict-JSON records.
Fact: held-out prompt text was not copied exactly into v2.1 training data.
Fact: v2.1 adapter: `D:\Sandbox\local_llm\adapters\asi_arc_lora_v2_1_strict_json`.
Fact: adapter tensor verification passed: nonzero tensors, no NaN, no Inf.

| comparison | result | accepted delta | valid/exact JSON delta | reason |
|---|---|---:|---:|---|
| base vs v2.1 | unchanged | 0 -> 0 | 0.000 -> 0.000 | no required metric improvement |
| v2 vs v2.1 | regressed | 1 -> 0 | 0.333 -> 0.000 | valid_json_rate_decreased |

Fact: v2.1 held-out metrics: accepted `0/3`, exact JSON `0/3`, `extra_text_after_json_count=3`.
Fact: final v2-vs-v2.1 comparison result is `regressed`.
Inference: v2.1 learned to produce relevant first objects but still emitted trailing `user/assistant/<think>` transcript continuations.

## Artifacts

- Run root: `D:\Sandbox\local_llm\artifacts\runs\20260523_strict_json_v2`
- Strict base metrics: `metrics\base_metrics.json`
- Strict adapter v1 metrics: `metrics\adapter_v1_metrics.json`
- Strict adapter v2 metrics: `metrics\adapter_v2_metrics.json`
- Adapter v2.1 metrics: `metrics\adapter_v2_1_metrics.json`
- Base vs v2.1 comparison: `comparisons\base_vs_v2_1.json`
- V2 vs v2.1 comparison: `comparisons\v2_vs_v2_1.json`
- Verifier calibration comparisons: `comparisons\*_verifier_calibration.json`
- Run manifest: `run_manifest.json`

## Process Notes

Fact: concurrent updates to the same `run_manifest.json` caused JSON corruption twice during parallel comparison commands.
Fact: the manifest was repaired and validated with `python -m json.tool`.
Inference: future benchmark scripts should avoid parallel writes to one manifest or make `update_run_manifest` atomic.

## Next Invariant

Hypothesis: adding an inference-time stop condition for transcript markers or constraining decoding to stop after the first balanced object will recover exact JSON more reliably than SFT alone.
Test: run the same held-out prompts with a generation stop rule that truncates at the first complete top-level JSON object only if no non-whitespace follows in the raw output, then record it as a separate decoder-instrument experiment, not model improvement.
