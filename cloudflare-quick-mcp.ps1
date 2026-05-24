$ErrorActionPreference = "Continue"

$LogDir  = "D:\Sandbox\asi_kernel\logs"
$LogFile = Join-Path $LogDir "cloudflare-quick-mcp.log"
$UrlFile = Join-Path $LogDir "cloudflare-quick-mcp.url.txt"

New-Item -ItemType Directory -Force $LogDir | Out-Null
Remove-Item $UrlFile -ErrorAction SilentlyContinue

"$(Get-Date -Format o) starting cloudflared quick tunnel -> http://127.0.0.1:2091" |
  Add-Content $LogFile

& "C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel --url http://127.0.0.1:2091 --no-autoupdate 2>&1 |
  ForEach-Object {
    $line = $_.ToString()
    $line | Add-Content $LogFile

    if ($line -match "https://[-a-z0-9]+\.trycloudflare\.com") {
      $Matches[0] | Set-Content $UrlFile
    }
  }
