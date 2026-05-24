# Local LLM Measurement Harness Log

Date: 2026-05-23

Goal: make future Qwen LoRA improvement claims traceable from environment, data, prompts, training, weights, inference, verifier, and comparison.

Observed facts:

- `D:\Sandbox\local_llm` already had training, inference, verifier, and benchmark scripts.
- Existing v1 artifacts include measured base/adapter responses and metrics.
- Existing v1 adapter lacks a saved pre-training initialized adapter snapshot, so exact before/after LoRA tensor deltas cannot be reconstructed for that run.

Implemented:

- Added run-scoped manifests and run directories under `local_llm/artifacts/runs/<run_id>`.
- Added initialized/final adapter safetensor snapshots and per-tensor diff metrics for future training runs.
- Added expanded training telemetry: batch loss, learning rate, optimizer-step grad norm, tokens per sample, skipped/truncated counts, GPU memory peak, and wall-clock time.
- Added expanded inference telemetry: raw prompt/response, hashes, parsed JSON, parse failure reason, verifier reasons, token counts, latency, decoding settings, and accepted/rejected status.
- Tightened comparison rules so model improvement requires matching prompt hashes, verifier version, model revision, and decoding settings.
- Added failure taxonomy and debug comparison modes.
- Added standard-library tests and a CPU tiny LoRA dry-run for snapshot/diff verification.

Verification planned:

- Run `python -m unittest discover -s tests` inside `/mnt/d/Sandbox/local_llm`.
- Run the tiny dry-run path and verify `adapter_diff_metrics.json` contains non-zero deltas and no NaN/Inf.

Uncertainty:

- Full Qwen training/eval was not implied as safe to run automatically because it may require GPU time and package/model state. Unit tests and tiny dry-run verify the harness mechanics without claiming new model improvement.
