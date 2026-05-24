# Local ASI/ARC Proposal Engine

Status: scaffolded, trained, and measured. The original v1 `artifacts/benchmark_comparison.json` records `improved` for the first small benchmark, but v1 did not save initialized adapter weights before training. Exact init-to-final LoRA tensor deltas are therefore unavailable for that run.

## Target

- Runtime root: `D:\Sandbox\local_llm`
- WSL runtime root: `/mnt/d/Sandbox/local_llm`
- Model: `Qwen/Qwen3.5-4B`
- Adapter: `D:\Sandbox\local_llm\adapters\asi_arc_lora_v1`
- ASI kernel logs/artifacts: `D:\Sandbox\asi_kernel\logs`, `D:\Sandbox\asi_kernel\artifacts`

Observed source metadata on 2026-05-23:

- Hugging Face model URL: <https://huggingface.co/Qwen/Qwen3.5-4B>
- Observed license: `apache-2.0`
- Observed pipeline tag: `image-text-to-text`
- Observed implementation note: model card examples use latest `transformers` from GitHub main.

These are source observations, not proof that the model is downloaded locally.

## Arch WSL Bootstrap

From PowerShell:

```powershell
wsl.exe -d archlinux -- /usr/bin/env bash /mnt/d/Sandbox/local_llm/scripts/bootstrap_arch.sh
```

What it does:

1. Adds `/usr/lib/wsl/lib` to `PATH`.
2. Verifies `/dev/dxg` and `/usr/lib/wsl/lib/nvidia-smi`.
3. Uses `uv` to install Python 3.12 into `/mnt/d/Sandbox/local_llm/.venv`.
4. Installs CUDA PyTorch from `https://download.pytorch.org/whl/cu128`.
5. Installs `transformers`, `accelerate`, `peft`, `trl`, `datasets`, `bitsandbytes`, `safetensors`, and support packages.
6. Writes `artifacts/torch_cuda_check.json`.

Package installs and model downloads require network access and user approval in Codex.

## Full Measured Cycle

Inside Arch WSL after bootstrap:

```bash
cd /mnt/d/Sandbox/local_llm
bash scripts/run_cycle.sh
```

The cycle writes run-scoped measurement artifacts under:

```text
artifacts/runs/<run_id>/
```

Key run artifacts:

- `run_manifest.json`
- `wsl_gpu_check.json`
- `torch_cuda_check.json`
- `data/asi_arc_sft_v1.jsonl`
- `data/asi_arc_sft_v1_manifest.json`
- `artifacts/model_manifest_qwen3_5_4b.json`
- `base_responses.jsonl`
- `base_metrics.json`
- `train_lora_metrics.json`
- `train_lora_loss.jsonl`
- `adapter_init.safetensors`
- `adapter_final.safetensors`
- `adapter_diff_metrics.json`
- `adapters/asi_arc_lora_v1/adapter_model.safetensors`
- `adapter_verification.json`
- `adapter_responses.jsonl`
- `adapter_metrics.json`
- `benchmark_comparison.json`

`run_manifest.json` records run id, timestamps, model revision metadata, adapter path, dataset hash, prompt hash, verifier version, seed, package versions, CUDA status, decoding settings, and command arguments.

## Improvement Rule

The adapter is `improved` only when:

- adapter accepted proposal count is at least base accepted count + 1
- adapter valid JSON rate is not lower than base valid JSON rate
- prompt set, verifier version, model revision, and decoding settings match and are recorded

All other outcomes are recorded as `unchanged`, `regressed`, `failed`, or `inconclusive`.

Current measured result:

```text
result: improved
base accepted proposals: 0 / 5
adapter accepted proposals: 2 / 5
base valid JSON rate: 0.0
adapter valid JSON rate: 0.8
verifier_version: 2026-05-23.risk-boundary-calibration
```

Caveat:

```text
This proves improvement on the tiny local benchmark only. It does not prove general ASI/ARC capability.
```

Debug comparison modes:

- `base-vs-adapter`
- `adapter-train-vs-heldout`
- `adapter-vs-adapter`
- `verifier-vs-verifier`
- `checkpoint-series`

Verifier changes are measurement instrument changes. Re-score old outputs when needed, but label the verifier version and do not count verifier-only score movement as model improvement.

## V2 Held-Out Eval

Held-out prompts live at:

```text
prompts/heldout_prompts_v2.jsonl
```

Measured run:

```text
artifacts/runs/20260523_v2_heldout
```

Trace-only re-score/compare manifest:

```text
artifacts/runs/20260523_v2_heldout_scored_trace_v3/run_manifest.json
```

Result:

```text
result: unchanged
base accepted proposals: 0 / 3
adapter accepted proposals: 0 / 3
base valid JSON rate: 0.0
adapter valid JSON rate: 1.0
prompt_file_sha256: 70f9f123ae738eddd2623387f68d4657510114461124da49ffc5ec7d720ce1f5
model_revision: 851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a
verifier_version: 2026-05-23.risk-boundary-calibration
decoding: max_new_tokens=512, do_sample=false, load_in_4bit=true, enable_thinking=false
```

Interpretation: adapter v1 improved held-out JSON validity, but did not improve verifier-accepted proposal count, so the allowed final comparison label is `unchanged`, not `improved`.

## Tiny Harness Dry Run

Verify snapshot and diff machinery without loading the full model:

```bash
/mnt/d/Sandbox/local_llm/.venv/bin/python scripts/train_lora.py \
  --dry-run-tiny \
  --run-id tiny_harness_check \
  --run-dir artifacts/runs/tiny_harness_check \
  --output-dir artifacts/runs/tiny_harness_check/tiny_adapter \
  --metrics artifacts/runs/tiny_harness_check/train_lora_metrics.json \
  --loss-log artifacts/runs/tiny_harness_check/train_lora_loss.jsonl
```

Expected artifacts:

- `adapter_init.safetensors`
- `adapter_final.safetensors`
- `adapter_diff_metrics.json`
- `run_manifest.json`

## Narrow Manual Commands

Build the local seed dataset:

```bash
/mnt/d/Sandbox/local_llm/.venv/bin/python scripts/build_sft_dataset.py
```

Download and hash model files:

```bash
/mnt/d/Sandbox/local_llm/.venv/bin/python scripts/download_model_manifest.py \
  --model-id Qwen/Qwen3.5-4B \
  --revision main \
  --local-dir /mnt/d/Sandbox/local_llm/models/Qwen--Qwen3.5-4B
```

Run base inference and score it:

```bash
/mnt/d/Sandbox/local_llm/.venv/bin/python scripts/run_inference.py \
  --model /mnt/d/Sandbox/local_llm/models/Qwen--Qwen3.5-4B \
  --prompts prompts/benchmark_prompts.jsonl \
  --output artifacts/base_responses.jsonl \
  --local-files-only \
  --load-in-4bit

/mnt/d/Sandbox/local_llm/.venv/bin/python scripts/benchmark_proposals.py score \
  --responses artifacts/base_responses.jsonl \
  --output artifacts/base_metrics.json
```

Train and verify adapter:

```bash
/mnt/d/Sandbox/local_llm/.venv/bin/python scripts/train_lora.py \
  --model /mnt/d/Sandbox/local_llm/models/Qwen--Qwen3.5-4B \
  --dataset data/asi_arc_sft_v1.jsonl \
  --output-dir adapters/asi_arc_lora_v1 \
  --local-files-only \
  --load-in-4bit \
  --run-id manual_train_check \
  --run-dir artifacts/runs/manual_train_check

/mnt/d/Sandbox/local_llm/.venv/bin/python scripts/verify_adapter.py \
  --adapter-dir adapters/asi_arc_lora_v1 \
  --model /mnt/d/Sandbox/local_llm/models/Qwen--Qwen3.5-4B \
  --local-files-only \
  --run-id manual_train_check \
  --run-dir artifacts/runs/manual_train_check
```
