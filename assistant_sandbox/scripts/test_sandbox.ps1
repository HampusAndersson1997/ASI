# Basic sandbox self-test
$ErrorActionPreference = "Stop"
$Root = "C:\Users\J\Sandbox\assistant_sandbox"
$Required = @("inbox", "work", "outputs", "logs", "tmp", "scripts", "config", "tools", "quarantine")

foreach ($Dir in $Required) {
    $Path = Join-Path $Root $Dir
    if (-not (Test-Path $Path)) {
        throw "Missing directory: $Path"
    }
}

$Probe = Join-Path $Root "tmp\probe.txt"
"sandbox write test $(Get-Date -Format o)" | Set-Content -Path $Probe -Encoding UTF8
if (-not (Test-Path $Probe)) { throw "Write test failed" }

Write-Host "Sandbox self-test passed."


