[CmdletBinding()]
param(
    [string]$RepoRoot = "",
    [switch]$FreshStart,
    [switch]$Quiet,
    [switch]$NoTestVictimTunnel
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

function Test-TestVictimHealth {
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

$testVictimScript = Join-Path $RepoRoot "testVictima\server.py"
if (-not (Test-Path -Path $testVictimScript)) {
    throw "Test victim server script not found at: $testVictimScript"
}

$deployScript = Join-Path $RepoRoot "scripts\deploy_cloudflare.ps1"
if (-not (Test-Path -Path $deployScript)) {
    throw "Cloudflare deploy script not found at: $deployScript"
}

$testVictimLogOut = Join-Path $env:TEMP "soxss-testVictim.out.log"
$testVictimLogErr = Join-Path $env:TEMP "soxss-testVictim.err.log"
if (Test-Path -Path $testVictimLogOut) {
    Remove-Item -Path $testVictimLogOut -Force -ErrorAction SilentlyContinue
}
if (Test-Path -Path $testVictimLogErr) {
    Remove-Item -Path $testVictimLogErr -Force -ErrorAction SilentlyContinue
}

if (Test-TestVictimHealth) {
    Write-Step "testVictima server already running on port 7070, reusing it"
}
else {
    Write-Step "Starting testVictima server (port 7070)"
    $testVictimProc = Start-Process -FilePath $pythonExe -ArgumentList @($testVictimScript) -WorkingDirectory $RepoRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput $testVictimLogOut -RedirectStandardError $testVictimLogErr

    Start-Sleep -Milliseconds 1200
    if ($testVictimProc.HasExited) {
        $outTail = if (Test-Path -Path $testVictimLogOut) { Get-Content -Path $testVictimLogOut -Tail 80 -ErrorAction SilentlyContinue | Out-String } else { "(stdout unavailable)" }
        $errTail = if (Test-Path -Path $testVictimLogErr) { Get-Content -Path $testVictimLogErr -Tail 80 -ErrorAction SilentlyContinue | Out-String } else { "(stderr unavailable)" }

        if ($errTail -match '10048' -and (Test-TestVictimHealth)) {
            Write-Step "Port 7070 was busy but testVictima is already up, continuing"
        }
        else {
            throw "testVictima server exited early with code $($testVictimProc.ExitCode). Logs:`nSTDOUT:`n$outTail`nSTDERR:`n$errTail"
        }
    }
}

if (Test-TestVictimHealth) {
    Write-Step "testVictima server is up"
}
else {
    Write-Host "[start-all] Warning: testVictima health check failed, continuing anyway."
}

$deployArgs = @{
    RepoRoot = $RepoRoot
}
if ($FreshStart) { $deployArgs.FreshStart = $true }
if ($Quiet) { $deployArgs.Quiet = $true }
if ($NoTestVictimTunnel) { $deployArgs.NoTestVictimTunnel = $true }

Write-Step "Starting Cloudflare tunnels and SOXSS"
& $deployScript @deployArgs
