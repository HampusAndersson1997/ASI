param(
    [Parameter(Mandatory = $true)]
    [string]$Task,

    [switch]$DryRun
)

$ExpectedRoot = "D:\Sandbox\asi_kernel"
$CurrentPath = [System.IO.Path]::GetFullPath((Get-Location).Path).TrimEnd("\")
$RootPath = [System.IO.Path]::GetFullPath($ExpectedRoot).TrimEnd("\")

if ($CurrentPath -ine $RootPath) {
    Write-Error "Refusing to run outside $ExpectedRoot. Current path: $CurrentPath"
    exit 1
}

$ScriptPath = Join-Path $ExpectedRoot "tools\codex_cli\run_codex_exec.py"
$VenvPython = Join-Path $ExpectedRoot ".venv\Scripts\python.exe"

if (Test-Path $VenvPython) {
    $Python = $VenvPython
} else {
    $Python = "python"
}

$Args = @($ScriptPath, "--task", $Task)
if ($DryRun) {
    $Args += "--dry-run"
}

& $Python @Args
exit $LASTEXITCODE
