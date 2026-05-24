# Clean disposable sandbox folders. Keeps logs and outputs.
$ErrorActionPreference = "Stop"
$Root = "C:\Users\J\Sandbox\assistant_sandbox"
$Targets = @("work", "tmp")

foreach ($Name in $Targets) {
    $Path = Join-Path $Root $Name
    if (Test-Path $Path) {
        Get-ChildItem -Path $Path -Force | Remove-Item -Recurse -Force
        Write-Host "Cleaned $Path"
    }
}


