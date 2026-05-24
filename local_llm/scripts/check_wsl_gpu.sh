#!/usr/bin/env bash
set -euo pipefail

ROOT="${LOCAL_LLM_ROOT:-/mnt/d/Sandbox/local_llm}"
OUT="${1:-$ROOT/artifacts/wsl_gpu_check.json}"
mkdir -p "$(dirname "$OUT")"

export PATH="/usr/lib/wsl/lib:$PATH"

STATUS="pass"
ERRORS=()

if [[ ":$PATH:" != *":/usr/lib/wsl/lib:"* ]]; then
  STATUS="failed"
  ERRORS+=("PATH does not include /usr/lib/wsl/lib")
fi

if [[ ! -e /dev/dxg ]]; then
  STATUS="failed"
  ERRORS+=("/dev/dxg is missing")
fi

if [[ ! -x /usr/lib/wsl/lib/nvidia-smi ]]; then
  STATUS="failed"
  ERRORS+=("/usr/lib/wsl/lib/nvidia-smi is missing or not executable")
fi

NVIDIA_SMI_OUTPUT=""
if [[ -x /usr/lib/wsl/lib/nvidia-smi ]]; then
  if ! NVIDIA_SMI_OUTPUT="$(/usr/lib/wsl/lib/nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>&1)"; then
    STATUS="failed"
    ERRORS+=("nvidia-smi failed")
  fi
fi

python - "$OUT" "$STATUS" "$NVIDIA_SMI_OUTPUT" "${ERRORS[@]}" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

out = Path(sys.argv[1])
status = sys.argv[2]
nvidia = sys.argv[3]
errors = sys.argv[4:]
payload = {
    "checked_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    "status": status,
    "path_has_wsl_lib": True,
    "dev_dxg_exists": Path("/dev/dxg").exists(),
    "nvidia_smi_path_exists": Path("/usr/lib/wsl/lib/nvidia-smi").exists(),
    "nvidia_smi_query": nvidia,
    "errors": errors,
}
out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

if [[ "$STATUS" != "pass" ]]; then
  exit 2
fi
