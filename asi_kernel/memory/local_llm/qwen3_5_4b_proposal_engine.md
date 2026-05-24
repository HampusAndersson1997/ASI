# Local LLM Proposal Engine Memory

Date: 2026-05-23

Purpose:

```text
Track evidence-backed state for the Qwen/Qwen3.5-4B ASI/ARC LoRA proposal engine.
```

Records:

```text
LLM001 fact | D:\Sandbox\local_llm is the local runtime root for this proposal engine | user proposal + directory creation | Get-ChildItem/New-Item/apply_patch | 2026-05-23 | local filesystem | until path changes
LLM002 fact | Arch WSL distribution archlinux is installed, running, and WSL2 | wsl.exe --list --verbose output | command output | 2026-05-23 | local Windows WSL state | until WSL config changes
LLM003 fact | /dev/dxg exists inside Arch WSL | wsl.exe -d archlinux -- /bin/ls -l /dev/dxg | command output | 2026-05-23 | Arch WSL GPU device visibility | until WSL/GPU driver changes
LLM004 fact | /usr/lib/wsl/lib/nvidia-smi exists and runs inside Arch WSL | wsl.exe -d archlinux -- /usr/lib/wsl/lib/nvidia-smi | command output | 2026-05-23 | Arch WSL NVIDIA utility visibility | until WSL/GPU driver changes
LLM005 fact | Hugging Face lists Qwen/Qwen3.5-4B with apache-2.0 license and image-text-to-text pipeline tag | https://huggingface.co/Qwen/Qwen3.5-4B search/page observation | web search observation | 2026-05-23 | upstream model metadata | recheck before download/training
LLM006 unknown | PyTorch CUDA availability inside the isolated Arch Python environment | missing installed environment evidence | run scripts/bootstrap_arch.sh then read artifacts/torch_cuda_check.json | local training runtime | no premise use until checked
LLM007 unknown | LoRA adapter improves ASI/ARC proposal generation | no training or benchmark result exists | run scripts/run_cycle.sh then read artifacts/benchmark_comparison.json | adapter quality | no premise use until measured
LLM008 fact | Seed ASI/ARC SFT dataset was generated with 6 records and SHA256 844750784a40f1f45c504fb23190090c415d9338deae40d2e21b0b1a557f5324 | D:\Sandbox\local_llm\data\asi_arc_sft_v1_manifest.json | dataset builder output readback | 2026-05-23 | local SFT seed dataset | until dataset file changes
LLM009 fact | Benchmark verifier self-test accepted 1 of 1 fixture responses and comparator returned unchanged for identical metrics | D:\Sandbox\local_llm\artifacts\verifier_selftest_metrics.json and verifier_selftest_comparison.json | command output | 2026-05-23 | local benchmark verifier | until verifier code changes
LLM010 fact | Pre-bootstrap Arch Python torch check failed because torch is not installed | D:\Sandbox\local_llm\artifacts\torch_cuda_check_prebootstrap.json | command output | 2026-05-23 | pre-bootstrap Arch system Python | until bootstrap installs isolated environment
LLM011 fact | Isolated Arch Python environment reports torch.cuda.is_available true on NVIDIA GeForce RTX 5060 Ti | D:\Sandbox\local_llm\artifacts\torch_cuda_check.json | command output | 2026-05-23 | local_llm Arch venv | until environment or GPU driver changes
LLM012 fact | Qwen/Qwen3.5-4B was downloaded locally and hash-recorded at resolved revision 851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a | D:\Sandbox\local_llm\artifacts\model_manifest_qwen3_5_4b.json | command output | 2026-05-23 | local model snapshot | until model files change
LLM013 fact | LoRA training completed without NaN/Inf loss and saved adapter to D:\Sandbox\local_llm\adapters\asi_arc_lora_v1 | D:\Sandbox\local_llm\artifacts\train_lora_metrics.json | command output | 2026-05-23 | local adapter training | until adapter retrained
LLM014 fact | Adapter safetensors passed non-zero, no-NaN, SHA256, and load checks | D:\Sandbox\local_llm\artifacts\adapter_verification.json | command output | 2026-05-23 | local adapter verification | until adapter changes
LLM015 fact | Calibrated benchmark comparison reports improved: base accepted 0/5, adapter accepted 2/5, valid JSON rate 0.0 to 0.8 | D:\Sandbox\local_llm\artifacts\benchmark_comparison.json | command output | 2026-05-23 | tiny local proposal benchmark | until prompts/verifier/model/adapter change
```

Decision:

```text
Use LoRA/QLoRA adapter weights first. Do not claim base-model weight modification or ASI improvement.
```

Next verification:

```text
Add held-out prompts and ARC-specific executable-verifier tasks. Current improvement is narrow and should not be generalized.
```
