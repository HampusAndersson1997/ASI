# 2026-05-23 Local LLM Proposal Engine Log

Goal:

```text
Create a local, verification-gated ASI/ARC proposal engine scaffold for Qwen/Qwen3.5-4B LoRA/QLoRA work.
```

Success metric:

```text
Do not claim improvement until base vs adapter benchmark comparison records improved under the rule:
+1 accepted proposal and no lower valid JSON rate.
```

Facts observed:

- `D:\Sandbox\asi_kernel\loop\current_state.md` lists local LLM proposal engine and benchmark-driven improvement as current focus.
- Arch WSL distribution `archlinux` is installed, running, and WSL2.
- `/dev/dxg` exists inside Arch WSL.
- `/usr/lib/wsl/lib/nvidia-smi` exists and runs inside Arch WSL.
- `nvidia-smi` reported `NVIDIA GeForce RTX 5060 Ti` with `16311 MiB` memory visible to WSL on 2026-05-23.
- Arch WSL currently reports Python `3.14.5`.
- Arch WSL has `uv 0.11.16`.
- Hugging Face search/page observation on 2026-05-23 found `Qwen/Qwen3.5-4B`, license `apache-2.0`, and pipeline tag `image-text-to-text`.

Actions:

- Created `D:\Sandbox\local_llm`.
- Added config, fixed benchmark prompts, dependency requirements, WSL bootstrap script, model manifest script, SFT dataset builder, inference script, LoRA training script, adapter verification script, benchmark scorer/comparator, and run-cycle script.
- Added this log and a local memory note.
- Compiled Python scripts with `D:\Sandbox\asi_kernel\.venv\Scripts\python.exe -m compileall D:\Sandbox\local_llm\scripts`.
- Generated `D:\Sandbox\local_llm\data\asi_arc_sft_v1.jsonl`.
- Generated `D:\Sandbox\local_llm\data\asi_arc_sft_v1_manifest.json`.
- Ran WSL GPU artifact check and wrote `D:\Sandbox\local_llm\artifacts\wsl_gpu_check.json`.
- Ran pre-bootstrap torch check and wrote `D:\Sandbox\local_llm\artifacts\torch_cuda_check_prebootstrap.json`.
- Ran benchmark verifier self-test and comparator self-test.
- Bootstrapped isolated Arch Python environment at `/mnt/d/Sandbox/local_llm/.venv`.
- Installed Python `3.12.13`, PyTorch `2.11.0+cu128`, `transformers`, `accelerate`, `peft`, `trl`, `datasets`, `bitsandbytes`, and `safetensors`.
- Downloaded `Qwen/Qwen3.5-4B` to `/mnt/d/Sandbox/local_llm/models/Qwen--Qwen3.5-4B`.
- Ran baseline inference on five fixed prompts.
- Trained LoRA/QLoRA adapter at `/mnt/d/Sandbox/local_llm/adapters/asi_arc_lora_v1`.
- Verified adapter safetensors and loadability.
- Ran adapter inference on the same five fixed prompts.
- Recorded first comparator result `unchanged`, then calibrated a verifier false negative for risk-boundary wording and reran scoring on the same saved base/adapter outputs.
- Copied key result artifacts into `D:\Sandbox\asi_kernel\artifacts\local_llm`.

Unverified:

- General ASI/ARC capability improvement is not proven. The measured improvement applies only to this tiny local benchmark.
- Full ARC task-solving improvement is not tested.

Verification results:

- `compileall`: pass.
- Seed SFT dataset manifest: pass, `record_count=6`, `dataset_sha256=844750784a40f1f45c504fb23190090c415d9338deae40d2e21b0b1a557f5324`.
- WSL GPU check: pass, `/dev/dxg=true`, `nvidia_smi_query=NVIDIA GeForce RTX 5060 Ti, 16311 MiB, 595.71`.
- Pre-bootstrap torch check: failed as expected, `torch_import_failed`.
- Verifier self-test: pass, `accepted_proposal_count=1`, `valid_json_rate=1.0`.
- Comparator self-test: pass, result `unchanged` for identical base/adapter metrics.
- Bootstrap torch CUDA check: pass, `cuda_available=true`, device `NVIDIA GeForce RTX 5060 Ti`, PyTorch `2.11.0+cu128`.
- Model manifest: pass, resolved revision `851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`, file count `14`, license `apache-2.0`, pipeline tag `image-text-to-text`.
- Baseline metrics before adapter: pass, valid JSON rate `0.0`, accepted proposals `0/5`.
- LoRA training: pass, 3 epochs, 6 optimizer steps, final loss `2.2158048152923584`, no NaN/Inf loss.
- Adapter verification: pass, `adapter_model.safetensors` SHA256 `06b84dffff600bbd7d9b4dff4f36641b5c0522bdde37b52ab5d9f40b264ca01d`, non-zero elements `21233664`, no NaN, base+adapter load pass.
- First benchmark comparison: `unchanged` because accepted count stayed `0`.
- Verifier calibration: pass, calibration fixture accepted. Calibration added boundary terms such as `risk`, `mitigation`, and `do not` because the earlier verifier rejected clear risk-boundary language.
- Final benchmark comparison after calibrated verifier: `improved`, base accepted `0/5`, adapter accepted `2/5`, base valid JSON rate `0.0`, adapter valid JSON rate `0.8`.

Verification pending:

```text
Expand benchmark coverage beyond five proposal prompts before making any broader claim.
```

Rollback:

```text
Delete D:\Sandbox\local_llm
Delete D:\Sandbox\asi_kernel\logs\2026-05-23_local_llm_proposal_engine.md
Delete D:\Sandbox\asi_kernel\memory\local_llm\qwen3_5_4b_proposal_engine.md
```
