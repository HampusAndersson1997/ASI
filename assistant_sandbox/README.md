# Assistant Sandbox Environment

A small, local, auditable sandbox scaffold for safe experiments.

Default Windows target path:

```powershell
C:\Users\J\assistant_sandbox
```

## Layout

| Path | Purpose |
|---|---|
| `inbox/` | Put user-provided files here before processing. |
| `work/` | Temporary working files. |
| `outputs/` | Final results safe to inspect or copy out. |
| `logs/` | Command logs and transcripts. |
| `tmp/` | Scratch space, disposable. |
| `scripts/` | PowerShell helper scripts. |
| `config/` | Local config, allowlists, sandbox policy. |
| `tools/` | Optional local tools. |
| `quarantine/` | Suspicious or untrusted files. |

## Start on Windows 11

Unzip this folder to `C:\Users\J\assistant_sandbox`, then run:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
cd C:\Users\J\assistant_sandbox
.\scripts\bootstrap.ps1
.\scripts\enter_sandbox.ps1
```

## Core rule

Everything starts untrusted. Work happens inside this folder. Outputs are copied out only after inspection.
