#!/usr/bin/env bash
set -euo pipefail

ROOT="${LOCAL_LLM_ROOT:-/mnt/d/Sandbox/local_llm}"
VENV="${VENV:-$ROOT/.venv}"
PY="$VENV/bin/python"
MODEL_DIR="${MODEL_DIR:-$ROOT/models/Qwen--Qwen3.5-4B}"
ADAPTER_DIR="${ADAPTER_DIR:-$ROOT/adapters/asi_arc_lora_v1}"
ARTIFACTS="$ROOT/artifacts"
RUN_ID="${RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)_qwen_lora}"
RUN_DIR="${RUN_DIR:-$ARTIFACTS/runs/$RUN_ID}"
PROMPTS="$ROOT/prompts/benchmark_prompts.jsonl"

export PATH="/usr/lib/wsl/lib:$PATH"
export HF_HUB_ENABLE_HF_TRANSFER="${HF_HUB_ENABLE_HF_TRANSFER:-1}"

if [[ ! -x "$PY" ]]; then
  echo "Missing Python environment: $PY" >&2
  echo "Run: bash $ROOT/scripts/bootstrap_arch.sh" >&2
  exit 10
fi

cd "$ROOT"
mkdir -p "$ARTIFACTS" "$ROOT/logs" "$ADAPTER_DIR" "$RUN_DIR"

bash "$ROOT/scripts/check_wsl_gpu.sh" "$RUN_DIR/wsl_gpu_check.json"
"$PY" "$ROOT/scripts/check_torch_cuda.py" --output "$RUN_DIR/torch_cuda_check.json"
"$PY" "$ROOT/scripts/build_sft_dataset.py"
"$PY" "$ROOT/scripts/download_model_manifest.py" --model-id "Qwen/Qwen3.5-4B" --revision main --local-dir "$MODEL_DIR" --output "$ARTIFACTS/model_manifest_qwen3_5_4b.json"

"$PY" "$ROOT/scripts/run_inference.py" --model "$MODEL_DIR" --prompts "$PROMPTS" --output "$RUN_DIR/base_responses.jsonl" --local-files-only --load-in-4bit --run-id "$RUN_ID" --run-dir "$RUN_DIR"
"$PY" "$ROOT/scripts/benchmark_proposals.py" score --responses "$RUN_DIR/base_responses.jsonl" --output "$RUN_DIR/base_metrics.json" --run-id "$RUN_ID" --run-dir "$RUN_DIR"

"$PY" "$ROOT/scripts/train_lora.py" --model "$MODEL_DIR" --dataset "$ROOT/data/asi_arc_sft_v1.jsonl" --output-dir "$ADAPTER_DIR" --metrics "$RUN_DIR/train_lora_metrics.json" --loss-log "$RUN_DIR/train_lora_loss.jsonl" --local-files-only --load-in-4bit --run-id "$RUN_ID" --run-dir "$RUN_DIR"
"$PY" "$ROOT/scripts/verify_adapter.py" --adapter-dir "$ADAPTER_DIR" --model "$MODEL_DIR" --output "$RUN_DIR/adapter_verification.json" --local-files-only --run-id "$RUN_ID" --run-dir "$RUN_DIR"

"$PY" "$ROOT/scripts/run_inference.py" --model "$MODEL_DIR" --adapter "$ADAPTER_DIR" --prompts "$PROMPTS" --output "$RUN_DIR/adapter_responses.jsonl" --local-files-only --load-in-4bit --run-id "$RUN_ID" --run-dir "$RUN_DIR"
"$PY" "$ROOT/scripts/benchmark_proposals.py" score --responses "$RUN_DIR/adapter_responses.jsonl" --output "$RUN_DIR/adapter_metrics.json" --run-id "$RUN_ID" --run-dir "$RUN_DIR"
"$PY" "$ROOT/scripts/benchmark_proposals.py" compare --base "$RUN_DIR/base_metrics.json" --adapter "$RUN_DIR/adapter_metrics.json" --output "$RUN_DIR/benchmark_comparison.json" --mode base-vs-adapter --run-id "$RUN_ID" --run-dir "$RUN_DIR"
