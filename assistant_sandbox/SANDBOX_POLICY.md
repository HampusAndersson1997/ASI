# Sandbox Policy

## Goal

Reduce accidental damage while experimenting with code, datasets, ARC-AGI tools, local LLM scripts, and file transformations.

## Boundaries

- Default root: `C:\Users\J\assistant_sandbox`
- Do not write outside the sandbox unless explicitly requested.
- Treat `inbox/` as untrusted.
- Put final artifacts in `outputs/`.
- Put disposable files in `tmp/`.
- Move suspicious files to `quarantine/`.

## Network

Default assumption: no network. If network is needed, state why and prefer read-only fetches from official sources.

## Execution

Before running scripts from `inbox/`:

1. Inspect content.
2. Identify side effects.
3. Prefer dry-run mode when possible.
4. Log commands to `logs/`.

## Cleanup

Use `scripts/clean.ps1` to remove scratch data while keeping logs and outputs.
