$ExpectedRoot = "D:\Sandbox\asi_kernel"
$LogPath = Join-Path $ExpectedRoot "logs\codex_cli_preflight.json"

function Normalize-PathText {
    param([string]$PathText)
    return [System.IO.Path]::GetFullPath($PathText).TrimEnd("\")
}

function Invoke-NativeCheck {
    param(
        [string]$Name,
        [string[]]$Arguments
    )

    $Result = [ordered]@{
        command = "$Name $($Arguments -join ' ')"
        available = $false
        stdout = ""
        stderr = ""
        exit_code = $null
        source = $null
        error = $null
    }

    $Command = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $Command) {
        $Result.error = "$Name not found on PATH"
        return $Result
    }

    $Result.source = $Command.Source

    try {
        $Output = & $Name @Arguments 2>&1
        $Succeeded = $?
        $Text = ($Output | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine
        $Result.stdout = $Text.Trim()
        if ($Succeeded) {
            $Result.exit_code = 0
            $Result.available = $true
        } else {
            $Result.stderr = $Text.Trim()
            if ($null -ne $LASTEXITCODE) {
                $Result.exit_code = $LASTEXITCODE
            } else {
                $Result.exit_code = 1
            }
        }
    } catch {
        $Result.error = $_.Exception.Message
        $Result.stderr = $_.Exception.Message
        if ($null -ne $LASTEXITCODE) {
            $Result.exit_code = $LASTEXITCODE
        } else {
            $Result.exit_code = 1
        }
    }

    return $Result
}

function Invoke-GetCommandCheck {
    param([string]$Name)

    $Result = [ordered]@{
        command = "Get-Command $Name"
        available = $false
        stdout = ""
        stderr = ""
        exit_code = $null
        source = $null
        error = $null
    }

    try {
        $Command = Get-Command $Name -ErrorAction Stop
        $Result.available = $true
        $Result.stdout = $Command.Source
        $Result.source = $Command.Source
        $Result.exit_code = 0
    } catch {
        $Result.stderr = $_.Exception.Message
        $Result.error = "$Name not found on PATH"
        $Result.exit_code = 1
    }

    return $Result
}

$CurrentPath = Normalize-PathText (Get-Location).Path
$RootPath = Normalize-PathText $ExpectedRoot
$CurrentPathOk = ($CurrentPath -ieq $RootPath)

$Checks = [ordered]@{
    node_version = Invoke-NativeCheck -Name "node" -Arguments @("-v")
    npm_version = Invoke-NativeCheck -Name "npm" -Arguments @("-v")
    codex_command = Invoke-GetCommandCheck "codex"
    codex_version = Invoke-NativeCheck -Name "codex" -Arguments @("--version")
}

$CodexReady = $Checks.codex_command.available -and $Checks.codex_version.available
$NodeReady = $Checks.node_version.available -and $Checks.npm_version.available
$Ready = $CurrentPathOk -and $NodeReady -and $CodexReady

$Record = [ordered]@{
    checked_at = [DateTimeOffset]::UtcNow.ToString("o")
    expected_root = $ExpectedRoot
    current_path = $CurrentPath
    current_path_ok = $CurrentPathOk
    ready = $Ready
    checks = $Checks
}

New-Item -ItemType Directory -Force (Split-Path $LogPath) | Out-Null
$Record | ConvertTo-Json -Depth 8 | Set-Content -Encoding UTF8 $LogPath

if (-not $CurrentPathOk) {
    Write-Host "ERROR: run this preflight from $ExpectedRoot"
    Write-Host "Current path: $CurrentPath"
    Write-Host "Results written to $LogPath"
    exit 1
}

Write-Host "Codex CLI preflight results written to $LogPath"
Write-Host "node -v: $($Checks.node_version.stdout)"
Write-Host "npm -v: $($Checks.npm_version.stdout)"

if ($CodexReady) {
    Write-Host "codex: $($Checks.codex_command.source)"
    Write-Host "codex --version: $($Checks.codex_version.stdout)"
} else {
    Write-Host "Codex CLI is missing or not usable."
    Write-Host "Install commands:"
    Write-Host "winget install OpenJS.NodeJS.LTS"
    Write-Host "npm install -g @openai/codex@latest"
    Write-Host "After installing Node/npm, reopen PowerShell so PATH updates are loaded."
}

exit 0
