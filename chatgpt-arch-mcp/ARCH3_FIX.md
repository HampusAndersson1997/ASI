# Arch3 MCP fix

## Working diagnosis

The MCP connector was reachable, but `arch_run` failed with:

```text
Error: spawn bash ENOENT
```

The working fix was to run the MCP server from Windows PowerShell with Git/MSYS bash on `PATH`, and to use a Windows working directory instead of `/mnt/d/Sandbox`.

## Working command shape

```powershell
cd D:\Sandbox\chatgpt-arch-mcp

$env:PATH="C:\Program Files\Git\bin;C:\Program Files\Git\usr\bin;C:\Windows\System32;C:\Windows;C:\Windows\System32\WindowsPowerShell\v1.0;$env:PATH"
$env:ARCH_MCP_HOST="127.0.0.1"
$env:ARCH_MCP_PORT="2091"
$env:ARCH_MCP_ENABLE_RUN="1"
$env:ARCH_MCP_CWD="D:\Sandbox"

Get-Command bash
node -e "require('child_process').spawnSync('bash',['-lc','pwd; echo ok'],{cwd:'D:\Sandbox',stdio:'inherit'})"
node .\dist\src\index.js
```

## Start helper

Use:

```powershell
D:\Sandbox\chatgpt-arch-mcp\start-arch3-fixed.ps1
```

Keep that server terminal open. In another PowerShell terminal, start the Cloudflare tunnel:

```powershell
cloudflared tunnel --url http://127.0.0.1:2091 --http-host-header "127.0.0.1:2091"
```

Then set the ChatGPT MCP connector URL to the newest `trycloudflare.com` URL plus `/mcp`.

## Verified behavior

A reversible write/read/delete probe succeeded in `D:\Sandbox` when `arch_run` included:

```text
cwd: D:\Sandbox
PATH: C:\Program Files\Git\bin;C:\Program Files\Git\usr\bin;...
```

Output:

```text
chatgpt write test ok
```

## Caveat

This currently uses Git/MSYS bash, not true WSL Arch bash. True WSL Arch may need the correct distro name from:

```powershell
wsl.exe -l -v
```
