#Requires -Version 5.1
<#
.SYNOPSIS
    Launcher for the AWS Environment Assessment Tool (Windows).

.DESCRIPTION
    Ensures Python 3.10+ is available, then hands off to setup_wizard.py.
    Any arguments passed to this script are forwarded to the wizard.

    DISCLAIMER: Community sample script provided without support guarantees.
    Not an official product. Use at your own risk.

.EXAMPLE
    .\Start-Assessment.ps1
    .\Start-Assessment.ps1 --verbose
    .\Start-Assessment.ps1 --all-regions --output MyAssessment.xlsx

.NOTES
    Run with:  powershell -ExecutionPolicy Bypass -File .\Start-Assessment.ps1
#>

[CmdletBinding()]
param([Parameter(ValueFromRemainingArguments=$true)][string[]]$PassThrough)

$ErrorActionPreference = "Stop"
$scriptDir = $PSScriptRoot

# ── Colour helpers ────────────────────────────────────────────────────────────
function Write-Header  { param($msg) Write-Host "`n  $msg" -ForegroundColor Cyan }
function Write-Good    { param($msg) Write-Host "  ✓ $msg" -ForegroundColor Green }
function Write-Warn    { param($msg) Write-Host "  ⚠ $msg" -ForegroundColor Yellow }
function Write-Fail    { param($msg) Write-Host "  ✗ $msg" -ForegroundColor Red }
function Write-Info    { param($msg) Write-Host "    $msg" -ForegroundColor Gray }

# ── Banner ────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  ┌─────────────────────────────────────────────────┐" -ForegroundColor DarkCyan
Write-Host "  │       AWS Environment Assessment Tool           │" -ForegroundColor DarkCyan
Write-Host "  │            Windows Launcher                     │" -ForegroundColor DarkCyan
Write-Host "  └─────────────────────────────────────────────────┘" -ForegroundColor DarkCyan
Write-Host ""

# ── Step 1: Find Python 3.10+ ─────────────────────────────────────────────────
Write-Header "Checking for Python 3.10+..."

function Get-PythonVersion {
    param($cmd)
    try {
        $v = & $cmd --version 2>&1
        if ($v -match "Python (\d+)\.(\d+)") {
            return [int]$Matches[1], [int]$Matches[2]
        }
    } catch {}
    return $null
}

$pythonCmd = $null
foreach ($candidate in @("python", "python3", "py")) {
    $result = Get-PythonVersion $candidate
    if ($result -and ($result[0] -gt 3 -or ($result[0] -eq 3 -and $result[1] -ge 10))) {
        $pythonCmd = $candidate
        Write-Good "Found Python $($result[0]).$($result[1]) via '$candidate'"
        break
    }
}

if (-not $pythonCmd) {
    Write-Warn "Python 3.10+ not found. Attempting to install via winget..."

    # Try winget
    $wingetAvailable = $null -ne (Get-Command winget -ErrorAction SilentlyContinue)
    if ($wingetAvailable) {
        try {
            Write-Info "Running: winget install --id Python.Python.3.12 -e --silent"
            winget install --id Python.Python.3.12 -e --silent --accept-source-agreements --accept-package-agreements
            # Refresh PATH in current session
            $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" +
                        [System.Environment]::GetEnvironmentVariable("PATH", "User")
            # Re-check
            foreach ($candidate in @("python", "python3", "py")) {
                $result = Get-PythonVersion $candidate
                if ($result -and ($result[0] -gt 3 -or ($result[0] -eq 3 -and $result[1] -ge 10))) {
                    $pythonCmd = $candidate
                    Write-Good "Python $($result[0]).$($result[1]) installed and ready"
                    break
                }
            }
        } catch {
            Write-Warn "winget install failed: $_"
        }
    }

    if (-not $pythonCmd) {
        # Try Microsoft Store
        $storeAvailable = $null -ne (Get-Command ms-windows-store: -ErrorAction SilentlyContinue)
        if ($storeAvailable) {
            Write-Info "Opening Microsoft Store Python page..."
            Start-Process "ms-windows-store://pdp/?productid=9PJPW5LDXLZ5"
        } else {
            Write-Info "Please install Python 3.10+ from: https://www.python.org/downloads/windows/"
            Start-Process "https://www.python.org/downloads/windows/"
        }
        Write-Fail "Python 3.10+ is required. Please install it and re-run this script."
        Read-Host "`n  Press Enter to exit"
        exit 1
    }
}

# ── Step 2: Verify wizard exists ──────────────────────────────────────────────
$wizardPath = Join-Path $scriptDir "setup_wizard.py"
if (-not (Test-Path $wizardPath)) {
    Write-Fail "setup_wizard.py not found in: $scriptDir"
    Read-Host "`n  Press Enter to exit"
    exit 1
}

# ── Step 3: Prefer project venv if it already exists ─────────────────────────
$venvPython = Join-Path $scriptDir ".venv\Scripts\python.exe"
if (Test-Path $venvPython) {
    Write-Good "Using project virtual environment (.venv\)"
    $pythonCmd = $venvPython
    $env:_AWS_WIZARD_VENV = "1"
}

# ── Step 4: Launch wizard ─────────────────────────────────────────────────────
Write-Good "Launching setup wizard...`n"

$argList = @("`"$wizardPath`"") + ($PassThrough | ForEach-Object { "`"$_`"" })

& $pythonCmd @argList
exit $LASTEXITCODE
