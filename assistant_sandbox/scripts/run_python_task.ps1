param(
    [Parameter(Mandatory=$true)]
    [string]$ScriptPath,

    [string[]]$Args
)

$ErrorActionPreference = "Stop"
$Root = "C:\Users\J\Sandbox\assistant_sandbox"
$Resolved = Resolve-Path $ScriptPath

if (-not ($Resolved.Path.StartsWith($Root))) {
    throw "Refusing to run outside sandbox: $($Resolved.Path)"
}

$Log = Join-Path $Root ("logs\python_{0}.log" -f (Get-Date -Format "yyyyMMdd_HHmmss"))
"Running: python $($Resolved.Path) $Args" | Tee-Object -FilePath $Log -Append
python $Resolved.Path @Args 2>&1 | Tee-Object -FilePath $Log -Append


