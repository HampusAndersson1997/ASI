# D:\Sandbox Private GitHub Publish Manifest

Date: 2026-05-24

Target: `HampusAndersson1997/SymbiosAI` private GitHub repository.

## Included

- Root MCP and editor MCP configs that were inspected and contain only local command paths.
- `asi_kernel` source, tests, dashboards, benchmark tooling, safety policy, memory tooling, and non-secret evidence artifacts selected by git ignore rules.
- `arc_dataset_library` inventory, normalization scripts, normalized summaries, and verifier/baseline reports.
- `local_llm` source, prompts, configs, small data files, and measured metric artifacts.
- `chatgpt-arch-mcp` source, package metadata, TypeScript config, and start scripts.
- `assistant_sandbox` policy, manifest, scripts, and stable scaffold files.
- `tools/tunnel-client` binary/zip artifacts and `hatch_pet_runs` generated pet artifacts.

## Excluded

- Secrets and credential files, including `asi_kernel/.env`.
- Python virtual environments, `node_modules`, build outputs, bytecode caches, and transient logs.
- `wsl/archlinux/ext4.vhdx`.
- Raw ARC dataset payloads under `arc_dataset_library/datasets/`.
- Local LLM model weights, LoRA adapters, and full training run directories under `local_llm/models/`, `local_llm/adapters/`, and `local_llm/artifacts/runs/`.

## Verification Boundary

This manifest records a source/evidence snapshot, not a claim of AGI or ASI. Harness progress percentages should only be updated from verified dashboards, tests, logs, benchmark scores, or saved artifacts.
