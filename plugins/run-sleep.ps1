# SkillOpt-Sleep shared runner for Windows PowerShell
# Resolves the repo root, picks Python >= 3.10, and runs the engine CLI.
#
# Usage: .\run-sleep.ps1 [status|run|dry-run|adopt|...] [args...]

$ErrorActionPreference = "Stop"

$ScriptDir = $PSScriptRoot

$RepoRoot = $null
if (Test-Path (Join-Path $ScriptDir "..\skillopt_sleep")) {
    $RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")
} elseif ($env:CLAUDE_PLUGIN_ROOT -and (Test-Path (Join-Path $env:CLAUDE_PLUGIN_ROOT "..\..\skillopt_sleep"))) {
    $RepoRoot = Resolve-Path (Join-Path $env:CLAUDE_PLUGIN_ROOT "..\..")
} elseif ($env:SKILLOPT_SLEEP_REPO -and (Test-Path (Join-Path $env:SKILLOPT_SLEEP_REPO "skillopt_sleep"))) {
    $RepoRoot = Resolve-Path $env:SKILLOPT_SLEEP_REPO
} else {
    # search upward from current location
    $d = Get-Item .
    while ($d -and $d.FullName -ne $d.Root.FullName) {
        if (Test-Path (Join-Path $d.FullName "skillopt_sleep")) {
            $RepoRoot = $d.FullName
            break
        }
        $d = Split-Path -Parent $d.FullName -ErrorAction SilentlyContinue | Get-Item -ErrorAction SilentlyContinue
    }
}

if (-not $RepoRoot) {
    Write-Error "[sleep] ERROR: could not locate the skillopt_sleep package. Set SKILLOPT_SLEEP_REPO to the repo root."
    exit 1
}

$Py = ""
if ($env:SKILLOPT_SLEEP_PYTHON) {
    $Py = $env:SKILLOPT_SLEEP_PYTHON
} else {
    foreach ($cand in @("python3", "python", "py")) {
        $cmd = Get-Command $cand -ErrorAction SilentlyContinue
        if ($cmd) {
            $ver = & $cand -c "import sys; print('%d%d' % sys.version_info[:2])" 2>$null
            if ($ver -and [int]$ver -ge 310) {
                $Py = $cand
                break
            }
        }
    }
}

if (-not $Py) {
    Write-Error "[sleep] ERROR: need Python >= 3.10 (found none)."
    exit 1
}

$argsList = @($args)
if ($argsList.Count -eq 0) {
    $argsList = @("status")
}

Set-Location $RepoRoot
# Run using the call operator
& $Py -m skillopt_sleep $argsList
