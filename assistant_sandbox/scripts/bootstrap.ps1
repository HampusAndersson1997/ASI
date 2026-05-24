# Assistant sandbox bootstrap for Windows 11
$ErrorActionPreference = "Stop"

$SandboxRoot = "C:\Users\J\Sandbox\assistant_sandbox"
$Dirs = @(
    "inbox",
    "work",
    "outputs",
    "logs",
    "tmp",
    "scripts",
    "config",
    "tools",
    "quarantine"
)

foreach ($Dir in $Dirs) {
    $Path = Join-Path $SandboxRoot $Dir
    if (-not (Test-Path $Path)) {
        New-Item -ItemType Directory -Path $Path | Out-Null
    }
}

$Log = Join-Path $SandboxRoot "logs\bootstrap.log"
"$(Get-Date -Format o) bootstrap completed at $SandboxRoot" | Tee-Object -FilePath $Log -Append

Write-Host "Sandbox ready at $SandboxRoot"
Write-Host "Next: .\scripts\enter_sandbox.ps1"


