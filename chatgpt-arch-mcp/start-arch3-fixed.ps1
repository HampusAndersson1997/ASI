# Start Arch3 MCP with the working Windows Git/MSYS bash fix.
# Run from PowerShell 7+.

Set-Location 'D:\Sandbox\chatgpt-arch-mcp'

# Make bash resolvable for the Node MCP process.
$env:PATH = 'C:\Program Files\Git\bin;C:\Program Files\Git\usr\bin;C:\Windows\System32;C:\Windows;C:\Windows\System32\WindowsPowerShell\v1.0;' + $env:PATH

# MCP server configuration.
$env:ARCH_MCP_HOST = '127.0.0.1'
$env:ARCH_MCP_PORT = '2091'
$env:ARCH_MCP_ENABLE_RUN = '1'
$env:ARCH_MCP_CWD = 'D:\Sandbox'

Write-Host 'Checking bash resolution...' -ForegroundColor Cyan
Get-Command bash

Write-Host 'Checking Node can spawn bash from D:\Sandbox...' -ForegroundColor Cyan
node -e "require('child_process').spawnSync('bash',['-lc','pwd; echo ok'],{cwd:'D:\\Sandbox',stdio:'inherit'})"

Write-Host 'Starting arch-wsl-shell MCP server...' -ForegroundColor Green
node .\dist\src\index.js
