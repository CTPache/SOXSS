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

$pythonExe = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -Path $pythonExe)) {
    throw "Python virtual environment not found at: $pythonExe"
}

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
