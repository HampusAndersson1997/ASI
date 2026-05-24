# Safe Codex CLI Commands

These commands are intentionally one-line PowerShell commands for Windows 11. Do not use dangerous Codex flags such as `--yolo`, `--dangerously-bypass-approvals-and-sandbox`, or `--sandbox danger-full-access` outside a disposable VM.

## PowerShell Install/Check

```powershell
Set-Location D:\Sandbox\asi_kernel; node -v; npm -v; npm install -g @openai/codex@latest; Get-Command codex; codex --version
```

After installing Node/npm, reopen PowerShell so PATH updates are loaded.

## First Sign-In

```powershell
codex
```

## Safe Repo Inspection

```powershell
Set-Location D:\Sandbox\asi_kernel; New-Item -ItemType Directory -Force .\logs\codex_cli_outputs | Out-Null; codex --ask-for-approval on-request exec --cd D:\Sandbox\asi_kernel --sandbox workspace-write --output-last-message .\logs\codex_cli_outputs\last_message.md "Inspect this repo. Do not edit files. Write a concise summary of the file tree and missing tests."
```

Codex CLI 0.133.0 accepts `--ask-for-approval` as a top-level `codex` option, before `exec`.

## Emergency Escape

If PowerShell shows `>>`, press Ctrl+C. That means an unfinished multiline command is active.
