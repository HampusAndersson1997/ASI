#!/usr/bin/env bash
set -euo pipefail

ROOT="${LOCAL_LLM_ROOT:-/mnt/d/Sandbox/local_llm}"
PYTHON_VERSION="${PYTHON_VERSION:-3.12}"
VENV="${VENV:-$ROOT/.venv}"
TORCH_INDEX_URL="${TORCH_INDEX_URL:-https://download.pytorch.org/whl/cu128}"

export PATH="/usr/lib/wsl/lib:$PATH"
cd "$ROOT"
mkdir -p "$ROOT/artifacts" "$ROOT/logs"

bash "$ROOT/scripts/check_wsl_gpu.sh" "$ROOT/artifacts/wsl_gpu_check.json"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required but was not found in Arch WSL." >&2
  exit 10
fi

uv python install "$PYTHON_VERSION"
uv venv --python "$PYTHON_VERSION" "$VENV"

uv pip install --python "$VENV/bin/python" --index-url "$TORCH_INDEX_URL" torch torchvision
uv pip install --python "$VENV/bin/python" -r "$ROOT/requirements/requirements-arch.txt"

"$VENV/bin/python" "$ROOT/scripts/check_torch_cuda.py" --output "$ROOT/artifacts/torch_cuda_check.json"

cat <<EOF
Bootstrap complete.
Venv: $VENV
Torch CUDA check: $ROOT/artifacts/torch_cuda_check.json
EOF
