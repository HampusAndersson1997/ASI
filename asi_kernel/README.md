# ASI Kernel

This is a measured AGI/ASI-harness project, not actual AGI or ASI.

Prime Directive:

Goal -> Memory -> Plan -> Execute -> Verify -> Compress -> Improve

Law:

No claim without evidence.
No action without logging.
No improvement without measurement.
No hallucinated success.

## Codex CLI Preflight

Run this from PowerShell in the repo root:

```powershell
Set-Location D:\Sandbox\asi_kernel; powershell -ExecutionPolicy Bypass -File tools\codex_cli\check_codex_cli.ps1
```

The preflight checks `node -v`, `npm -v`, `Get-Command codex`, and `codex --version`. It writes results to `logs\codex_cli_preflight.json`.

## Install Codex CLI

If the preflight reports that Codex CLI is missing, install Node.js LTS and Codex CLI explicitly:

```powershell
winget install OpenJS.NodeJS.LTS
npm install -g @openai/codex@latest
```

After installing Node/npm, reopen PowerShell so PATH updates are loaded.

## Sign In

Run:

```powershell
codex
```

Complete the interactive sign-in flow before using `codex exec`.

## Safe One-Line Repo Inspection

```powershell
Set-Location D:\Sandbox\asi_kernel; New-Item -ItemType Directory -Force .\logs\codex_cli_outputs | Out-Null; codex --ask-for-approval on-request exec --cd D:\Sandbox\asi_kernel --sandbox workspace-write --output-last-message .\logs\codex_cli_outputs\last_message.md "Inspect this repo. Do not edit files. Write a concise summary of the file tree and missing tests."
```

Codex CLI 0.133.0 accepts `--ask-for-approval` as a top-level `codex` option, before `exec`.

## Wrapper

The bounded wrapper validates task JSON before invoking Codex CLI. It rejects unsafe paths, high-risk tasks, and forbidden flags. It writes JSONL audit records to `logs\codex_cli_runs.jsonl`.

Dry-run a task without invoking Codex CLI:

```powershell
Set-Location D:\Sandbox\asi_kernel; python tools\codex_cli\run_codex_exec.py --task tools\codex_cli\codex_task_template.json --dry-run
```

Run a validated task:

```powershell
Set-Location D:\Sandbox\asi_kernel; python tools\codex_cli\run_codex_exec.py --task tools\codex_cli\codex_task_template.json
```

PowerShell wrapper:

```powershell
Set-Location D:\Sandbox\asi_kernel; powershell -ExecutionPolicy Bypass -File tools\codex_cli\run_codex_exec.ps1 -Task tools\codex_cli\codex_task_template.json -DryRun
```

## Evaluator And Memory

Non-dry wrapper runs execute the configured validation commands after Codex CLI returns. Passing validations append `memory\agent_runs.jsonl`; failed validations or failed delegation append `memory\failures.jsonl`.

## Progress Dashboard

Generate the local harness progress dashboard from existing tests, logs, Codex CLI audit records, the tool registry, skills, and verification artifacts:

```powershell
Set-Location D:\Sandbox\asi_kernel; python dashboards\progress_report.py
```

This writes `dashboards\progress_report.md`. The generator does not read `.env`, does not use the network, does not run `codex exec`, and does not call Supabase.

## Stage 6c Patch Proposal Loop

Generate a safe, review-only patch proposal without applying it:

```powershell
Set-Location D:\Sandbox\asi_kernel; .\.venv\Scripts\python.exe research\patch_proposal_loop.py --suite smoke --cycles 1
```

This writes a proposal JSON, a unified diff patch artifact, and an audit JSONL entry under `logs\research`. The loop requires human approval and records `auto_applied=false`.

## Tests

```powershell
Set-Location D:\Sandbox\asi_kernel; python -m pytest tests\test_codex_cli_wrapper.py tests\test_codex_phase2.py -q
```

Unit test command:

```powershell
D:\Sandbox\asi_kernel\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider -q
```

Unit tests must not read `.env`, call Supabase, use network, or run real `codex exec` delegation. If integration tests are added later, they must be explicitly marked and skipped by default.

## Recover From PowerShell `>>`

If PowerShell shows `>>`, press Ctrl+C. That means an unfinished multiline command is active.
