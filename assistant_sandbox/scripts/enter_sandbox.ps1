# Enter assistant sandbox
$ErrorActionPreference = "Stop"

$env:ASSISTANT_SANDBOX = "C:\Users\J\Sandbox\assistant_sandbox"
Set-Location $env:ASSISTANT_SANDBOX

$Transcript = Join-Path $env:ASSISTANT_SANDBOX ("logs\session_{0}.log" -f (Get-Date -Format "yyyyMMdd_HHmmss"))
Start-Transcript -Path $Transcript -Append | Out-Null

function prompt {
    "sandbox:$($executionContext.SessionState.Path.CurrentLocation)> "
}

Write-Host "Entered sandbox: $env:ASSISTANT_SANDBOX"
Write-Host "Transcript: $Transcript"
Write-Host "Use Stop-Transcript when done."


