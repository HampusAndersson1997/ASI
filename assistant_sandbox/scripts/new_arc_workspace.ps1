# Create an ARC-AGI experiment workspace inside the sandbox
param(
    [string]$Name = "arc_experiment"
)

$ErrorActionPreference = "Stop"
$Root = "C:\Users\J\Sandbox\assistant_sandbox"
$SafeName = $Name -replace '[^a-zA-Z0-9_\-]', '_'
$Path = Join-Path $Root ("work\" + $SafeName)

New-Item -ItemType Directory -Path $Path -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $Path "data") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $Path "src") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $Path "runs") -Force | Out-Null

@"
# $SafeName

ARC experiment workspace.

- Put tasks in `data/`.
- Put solver code in `src/`.
- Put run outputs in `runs/`.
"@ | Set-Content -Path (Join-Path $Path "README.md") -Encoding UTF8

Write-Host "Created $Path"


