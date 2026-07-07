[CmdletBinding()]
param(
    [string]$RepoRoot = "",
    [switch]$FreshStart,
    [switch]$Quiet,
    [switch]$NoTwisterTunnel
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $scriptDir = if ($PSScriptRoot) {
        $PSScriptRoot
    }
    elseif ($MyInvocation.MyCommand.Path) {
        Split-Path -Parent $MyInvocation.MyCommand.Path
    }
    else {
        (Get-Location).Path
    }
    $RepoRoot = (Resolve-Path (Join-Path $scriptDir "..")).Path
}

function Write-Step([string]$Message) {
    Write-Host "[start-all] $Message"
}

function Test-TwisterHealth {
    try {
        $null = Invoke-RestMethod -Uri "http://127.0.0.1:7070/api/users" -Method Get -TimeoutSec 3 -ErrorAction Stop
        return $true
    }
    catch {
        return $false
    }
}

function Resolve-HostPythonExecutable {
    # Prefer the Windows 'py' launcher: it always resolves to a real CPython that
    # produces a standard Scripts\ venv layout. A bare 'python.exe' on PATH may be a
    # bundled MinGW build (e.g. Inkscape's) that creates an unusable Unix-style venv.
    $pyCmd = Get-Command py -ErrorAction SilentlyContinue
    if ($pyCmd) {
        try {
            $resolved = (& $pyCmd.Source -3 -c "import sys; print(sys.executable)" 2>$null | Select-Object -First 1)
            if ($resolved) { $resolved = $resolved.Trim() }
            if ($resolved -and (Test-Path -Path $resolved)) {
                return $resolved
            }
        }
        catch {
            # Fall through to the plain interpreters below.
        }
    }

    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCmd) {
        return $pythonCmd.Source
    }

    $python3Cmd = Get-Command python3 -ErrorAction SilentlyContinue
    if ($python3Cmd) {
        return $python3Cmd.Source
    }

    throw "Python 3 interpreter not found on PATH. Install Python and ensure 'py' or 'python' is available."
}

function Get-VenvPythonExecutable {
    param(
        [string]$VenvRoot
    )

    $candidates = @(
        (Join-Path $VenvRoot "Scripts\python.exe"),
        (Join-Path $VenvRoot "bin\python"),
        (Join-Path $VenvRoot "bin\python3")
    )

    foreach ($candidate in $candidates) {
        if (Test-Path -Path $candidate) {
            return $candidate
        }
    }

    return $null
}

function Initialize-VirtualEnvironment {
    param(
        [string]$VenvPath,
        [string]$HostPython
    )

    if (Test-Path -Path $VenvPath) {
        if (Get-VenvPythonExecutable -VenvRoot $VenvPath) {
            return
        }
        Write-Step "Existing virtual environment at $VenvPath is invalid or incompatible; recreating it"
        Remove-Item -Path $VenvPath -Recurse -Force
    }

    Write-Step "Creating Python virtual environment at $VenvPath using $HostPython"
    & $HostPython -m venv $VenvPath
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create virtual environment using $HostPython."
    }
}

function Test-RequirementsSatisfied {
    param(
        [string]$PythonExe,
        [string]$RequirementsFile
    )

    # Ask pip to resolve the requirements in dry-run/report mode without touching
    # the environment. If every requirement is already satisfied there is nothing
    # left to install and we can skip the (slow, network-bound) install step.
    $output = & $PythonExe -m pip install --dry-run --no-deps -r $RequirementsFile 2>&1
    if ($LASTEXITCODE -ne 0) {
        # Could not determine state (e.g. offline); fall back to attempting install.
        return $false
    }

    # pip prints "Would install <pkg> ..." for anything missing; absence means satisfied.
    if ($output -match 'Would install') {
        return $false
    }

    return $true
}

function Install-Requirements {
    param(
        [string]$PythonExe,
        [string]$RequirementsFile
    )

    if (-not (Test-Path -Path $RequirementsFile)) {
        Write-Step "requirements.txt not found at $RequirementsFile; skipping dependency installation."
        return
    }

    if (Test-RequirementsSatisfied -PythonExe $PythonExe -RequirementsFile $RequirementsFile) {
        Write-Step "All Python dependencies already satisfied."
        return
    }

    Write-Step "Installing dependencies from requirements.txt"
    & $PythonExe -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to upgrade pip inside virtual environment."
    }

    & $PythonExe -m pip install -r $RequirementsFile
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install Python dependencies from requirements.txt."
    }
}

function Initialize-Cloudflared {
    $cmd = Get-Command "cloudflared" -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source) {
        return
    }

    $wingetRoot = Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Packages"
    if (Test-Path -Path $wingetRoot) {
        $existing = Get-ChildItem -Path $wingetRoot -Filter "cloudflared.exe" -Recurse -ErrorAction SilentlyContinue |
            Select-Object -First 1
        if ($existing) {
            return
        }
    }

    $winget = Get-Command "winget" -ErrorAction SilentlyContinue
    if (-not $winget) {
        throw @"
cloudflared executable not found and winget is unavailable to install it.

Install Cloudflare Tunnel manually, then rerun:
  winget install --id Cloudflare.cloudflared -e
"@
    }

    Write-Step "cloudflared not found; installing via winget (Cloudflare.cloudflared)"
    & $winget.Source install --id Cloudflare.cloudflared -e --accept-source-agreements --accept-package-agreements
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install cloudflared via winget (exit code $LASTEXITCODE)."
    }
}

$venvRoot = Join-Path $RepoRoot ".venv"
$pythonExe = Get-VenvPythonExecutable -VenvRoot $venvRoot
if (-not $pythonExe) {
    $hostPython = Resolve-HostPythonExecutable
    Initialize-VirtualEnvironment -VenvPath $venvRoot -HostPython $hostPython
    $pythonExe = Get-VenvPythonExecutable -VenvRoot $venvRoot
    if (-not $pythonExe) {
        throw "Failed to create or locate the virtual environment python executable at: $venvRoot"
    }
}

# Always ensure dependencies are present, even when reusing an existing venv.
Install-Requirements -PythonExe $pythonExe -RequirementsFile (Join-Path $RepoRoot "requirements.txt")

# Make sure the Cloudflare tunnel binary the deploy step needs is available.
Initialize-Cloudflared

$twisterScript = Join-Path $RepoRoot "twister\server.py"
if (-not (Test-Path -Path $twisterScript)) {
    throw "Twister server script not found at: $twisterScript"
}

$deployScript = Join-Path $RepoRoot "scripts\deploy_cloudflare.ps1"
if (-not (Test-Path -Path $deployScript)) {
    throw "Cloudflare deploy script not found at: $deployScript"
}

$twisterLogOut = Join-Path $env:TEMP "soxss-twister.out.log"
$twisterLogErr = Join-Path $env:TEMP "soxss-twister.err.log"
if (Test-Path -Path $twisterLogOut) {
    Remove-Item -Path $twisterLogOut -Force -ErrorAction SilentlyContinue
}
if (Test-Path -Path $twisterLogErr) {
    Remove-Item -Path $twisterLogErr -Force -ErrorAction SilentlyContinue
}

if (Test-TwisterHealth) {
    Write-Step "twister server already running on port 7070, reusing it"
}
else {
    Write-Step "Starting twister server (port 7070)"
    $twisterProc = Start-Process -FilePath $pythonExe -ArgumentList @($twisterScript) -WorkingDirectory $RepoRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput $twisterLogOut -RedirectStandardError $twisterLogErr

    Start-Sleep -Milliseconds 1200
    if ($twisterProc.HasExited) {
        $outTail = if (Test-Path -Path $twisterLogOut) { Get-Content -Path $twisterLogOut -Tail 80 -ErrorAction SilentlyContinue | Out-String } else { "(stdout unavailable)" }
        $errTail = if (Test-Path -Path $twisterLogErr) { Get-Content -Path $twisterLogErr -Tail 80 -ErrorAction SilentlyContinue | Out-String } else { "(stderr unavailable)" }

        if ($errTail -match '10048' -and (Test-TwisterHealth)) {
            Write-Step "Port 7070 was busy but twister is already up, continuing"
        }
        else {
            throw "twister server exited early with code $($twisterProc.ExitCode). Logs:`nSTDOUT:`n$outTail`nSTDERR:`n$errTail"
        }
    }
}

if (Test-TwisterHealth) {
    Write-Step "twister server is up"
}
else {
    Write-Host "[start-all] Warning: twister health check failed, continuing anyway."
}

$deployArgs = @{
    RepoRoot = $RepoRoot
}
if ($FreshStart) { $deployArgs.FreshStart = $true }
if ($Quiet) { $deployArgs.Quiet = $true }
if ($NoTwisterTunnel) { $deployArgs.NoTwisterTunnel = $true }

Write-Step "Starting Cloudflare tunnels and SOXSS"
& $deployScript @deployArgs
