# Evidence Ledger

## Claim

## Evidence

## Uncertainty

## Test

## Result

## Next Action

## 2026-05-23 Local LLM Proposal Engine

## Claim

`D:\Sandbox\local_llm` contains a scaffold for a Qwen/Qwen3.5-4B ASI/ARC proposal engine with LoRA/QLoRA training and benchmark comparison.

## Evidence

- Files created under `D:\Sandbox\local_llm`.
- Log: `D:\Sandbox\asi_kernel\logs\2026-05-23_local_llm_proposal_engine.md`.
- Memory note: `D:\Sandbox\asi_kernel\memory\local_llm\qwen3_5_4b_proposal_engine.md`.

## Uncertainty

- CUDA PyTorch inside the isolated Arch environment is not yet verified.
- Model files are not yet downloaded.
- Adapter training and benchmark comparison have not yet run.

## Test

```text
wsl.exe -d archlinux -- /usr/bin/env bash /mnt/d/Sandbox/local_llm/scripts/bootstrap_arch.sh
wsl.exe -d archlinux -- /usr/bin/env bash /mnt/d/Sandbox/local_llm/scripts/run_cycle.sh
```

## Result

```text
improved on tiny local benchmark
```

## Next Action

Expand benchmark coverage and add a held-out prompt set before making broader claims.

Observed partial verification:

- Script compile check passed.
- Seed dataset built with `record_count=6` and SHA256 `844750784a40f1f45c504fb23190090c415d9338deae40d2e21b0b1a557f5324`.
- WSL GPU check passed with `/dev/dxg`, `/usr/lib/wsl/lib/nvidia-smi`, and RTX 5060 Ti visible.
- Pre-bootstrap torch check failed because `torch` is not installed in Arch system Python 3.14.5.
- Benchmark verifier self-test passed; comparator self-test returned `unchanged` for identical metric files.
- Bootstrap passed: PyTorch `2.11.0+cu128`, CUDA available, RTX 5060 Ti visible.
- Model manifest passed: `Qwen/Qwen3.5-4B`, resolved revision `851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`, license `apache-2.0`, 14 files hash-recorded.
- LoRA training passed: 3 epochs, 6 optimizer steps, no NaN/Inf loss.
- Adapter verification passed: SHA256 `06b84dffff600bbd7d9b4dff4f36641b5c0522bdde37b52ab5d9f40b264ca01d`, non-zero elements `21233664`, load pass.
- Final benchmark comparison passed: result `improved`, base accepted `0/5`, adapter accepted `2/5`, base valid JSON rate `0.0`, adapter valid JSON rate `0.8`.
