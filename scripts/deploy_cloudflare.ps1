[CmdletBinding()]
param(
    [string]$RepoRoot = "",
    [string]$CloudflaredExe = "cloudflared",
    [int]$HttpPort = 8000,
    [int]$WsPort = 8765,
    [int]$TwisterPort = 7070,
    [switch]$NoTwisterTunnel,
    [switch]$NoRun,
    [switch]$FreshStart,
    [switch]$Quiet
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
    Write-Host "[deploy-cloudflare] $Message"
}

function Update-ConfigValue {
    param(
        [string]$FilePath,
        [string]$Name,
        [string]$ValueLiteral
    )

    $pattern = "(?m)^\s*$([regex]::Escape($Name))\s*=\s*.*$"
    $replacement = "$Name = $ValueLiteral"
    $updated = [regex]::Replace((Get-Content -Raw -Path $FilePath), $pattern, $replacement)
    Set-Content -Path $FilePath -Value $updated -Encoding UTF8
}

function Resolve-CloudflaredExecutable {
    param([string]$InputPath)

    if ($InputPath -and (Test-Path -Path $InputPath)) {
        return (Resolve-Path -Path $InputPath).Path
    }

    $cmd = Get-Command $InputPath -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source) {
        return $cmd.Source
    }

    $wingetCandidates = @()
    $wingetRoot = Join-Path $env:LOCALAPPDATA "Microsoft\WinGet\Packages"
    if (Test-Path -Path $wingetRoot) {
        $wingetCandidates = Get-ChildItem -Path $wingetRoot -Filter "cloudflared.exe" -Recurse -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty FullName
    }

    $candidates = @(
        (Join-Path $env:ProgramFiles "cloudflared\cloudflared.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "cloudflared\cloudflared.exe")
    ) + @($wingetCandidates)

    $candidates = $candidates | Where-Object { $_ -and (Test-Path -Path $_) }
    if (@($candidates).Count -gt 0) {
        return @($candidates)[0]
    }

    throw @"
cloudflared executable not found.

Install Cloudflare Tunnel first:
  winget install --id Cloudflare.cloudflared -e

Then rerun this script, or pass the explicit binary path:
  .\scripts\deploy_cloudflare.ps1 -CloudflaredExe "C:\path\to\cloudflared.exe"
"@
}

function Parse-PublicUrl {
    param([string]$Url)

    $uri = [Uri]$Url
    [PSCustomObject]@{
        Scheme = $uri.Scheme
        Host = $uri.Host
    }
}

function Start-QuickTunnel {
    param(
        [string]$Name,
        [string]$CloudflaredPath,
        [string]$LocalUrl,
        [string]$LogPath,
        [string]$WorkDir
    )

    if (Test-Path -Path $LogPath) {
        Remove-Item -Path $LogPath -Force -ErrorAction SilentlyContinue
    }

    $args = @(
        "tunnel",
        "--no-autoupdate",
        "--url", $LocalUrl,
        "--logfile", $LogPath,
        "--loglevel", "info"
    )

    $proc = Start-Process -FilePath $CloudflaredPath -ArgumentList $args -WorkingDirectory $WorkDir -WindowStyle Hidden -PassThru
    return $proc
}

function Wait-TunnelPublicUrl {
    param(
        [string]$Name,
        [System.Diagnostics.Process]$Process,
        [string]$LogPath,
        [int]$Retries = 60,
        [int]$DelayMs = 500
    )

    $pattern = 'https://[a-z0-9-]+\.trycloudflare\.com'

    for ($i = 0; $i -lt $Retries; $i++) {
        if ($Process.HasExited) {
            $tail = if (Test-Path -Path $LogPath) { Get-Content -Path $LogPath -Tail 80 -ErrorAction SilentlyContinue | Out-String } else { "(log unavailable)" }
            throw "Cloudflared process '$Name' exited early with code $($Process.ExitCode). Log:`n$tail"
        }

        if (Test-Path -Path $LogPath) {
            $content = Get-Content -Path $LogPath -Raw -ErrorAction SilentlyContinue
            if ($content) {
                $match = [regex]::Match($content, $pattern)
                if ($match.Success) {
                    return $match.Value
                }
            }
        }

        Start-Sleep -Milliseconds $DelayMs
    }

    $tail = if (Test-Path -Path $LogPath) { Get-Content -Path $LogPath -Tail 120 -ErrorAction SilentlyContinue | Out-String } else { "(log unavailable)" }
    throw "Could not resolve public URL for tunnel '$Name'. Log tail:`n$tail"
}

$configPath = Join-Path $RepoRoot "config.py"
if (-not (Test-Path -Path $configPath)) {
    throw "config.py was not found at: $configPath"
}

Write-Step "Repository root: $RepoRoot"
Write-Step "Resolving cloudflared executable"
$CloudflaredExe = Resolve-CloudflaredExecutable -InputPath $CloudflaredExe
Write-Step "Using cloudflared binary: $CloudflaredExe"

$httpLocal = "http://127.0.0.1:$HttpPort"
$wsLocal = "http://127.0.0.1:$WsPort"
$twisterLocal = "http://127.0.0.1:$TwisterPort"

$httpLog = Join-Path $env:TEMP "soxss-cloudflare-http.log"
$wsLog = Join-Path $env:TEMP "soxss-cloudflare-ws.log"
$twisterLog = Join-Path $env:TEMP "soxss-cloudflare-twister.log"

Write-Step "Starting Cloudflare quick tunnels"
$httpProc = Start-QuickTunnel -Name "http" -CloudflaredPath $CloudflaredExe -LocalUrl $httpLocal -LogPath $httpLog -WorkDir $RepoRoot
$wsProc = Start-QuickTunnel -Name "ws" -CloudflaredPath $CloudflaredExe -LocalUrl $wsLocal -LogPath $wsLog -WorkDir $RepoRoot
$twisterProc = $null
if (-not $NoTwisterTunnel) {
    $twisterProc = Start-QuickTunnel -Name "twister" -CloudflaredPath $CloudflaredExe -LocalUrl $twisterLocal -LogPath $twisterLog -WorkDir $RepoRoot
}

$httpPublic = Wait-TunnelPublicUrl -Name "http" -Process $httpProc -LogPath $httpLog
$wsPublic = Wait-TunnelPublicUrl -Name "ws" -Process $wsProc -LogPath $wsLog
$twisterPublic = $null
if (-not $NoTwisterTunnel) {
    $twisterPublic = Wait-TunnelPublicUrl -Name "twister" -Process $twisterProc -LogPath $twisterLog
}

$httpParsed = Parse-PublicUrl -Url $httpPublic
$wsParsed = Parse-PublicUrl -Url $wsPublic

Write-Step "Resolved HTTP tunnel: $httpPublic"
Write-Step "Resolved WS tunnel:   $wsPublic"
if (-not $NoTwisterTunnel) {
    Write-Step "Resolved Twister tunnel: $twisterPublic"
}

Update-ConfigValue -FilePath $configPath -Name "PUBLIC_HTTP_HOST" -ValueLiteral ('"{0}"' -f $httpParsed.Host)
Update-ConfigValue -FilePath $configPath -Name "PUBLIC_WS_HOST" -ValueLiteral ('"{0}"' -f $wsParsed.Host)
Update-ConfigValue -FilePath $configPath -Name "PUBLIC_HTTP_SCHEME" -ValueLiteral '"https"'
Update-ConfigValue -FilePath $configPath -Name "PUBLIC_WS_SCHEME" -ValueLiteral '"wss"'
Update-ConfigValue -FilePath $configPath -Name "PUBLIC_HTTP_PORT" -ValueLiteral "None"
Update-ConfigValue -FilePath $configPath -Name "PUBLIC_WS_PORT" -ValueLiteral "None"

Write-Step "Config updated successfully"
Write-Host ""
Write-Host "=== SOXSS PUBLIC ENDPOINTS (CLOUDFLARE) ==="
Write-Host "Payload URL:    $httpPublic/webSocket.js"
Write-Host "Script base:    $httpPublic/"
Write-Host "WS endpoint:    $($wsPublic -replace '^https://', 'wss://')"
if (-not $NoTwisterTunnel) {
    Write-Host "Twister URL: $twisterPublic/"
}
Write-Host "==========================================="
Write-Host ""

if ($NoRun) {
    Write-Step "NoRun enabled. Deployment script finished without starting SOXSS."
    exit 0
}

$pythonExe = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -Path $pythonExe)) {
    throw "Python virtual environment not found at: $pythonExe"
}

$soxssArgs = @("Socxss.py")
$soxssArgs += @("--PUBLIC_HTTP_HOST", $httpParsed.Host)
$soxssArgs += @("--PUBLIC_WS_HOST", $wsParsed.Host)
$soxssArgs += @("--PUBLIC_HTTP_SCHEME", "https")
$soxssArgs += @("--PUBLIC_WS_SCHEME", "wss")
$soxssArgs += @("--PUBLIC_HTTP_PORT", "None")
$soxssArgs += @("--PUBLIC_WS_PORT", "None")
if ($FreshStart) { $soxssArgs += "-f" }
if ($Quiet) { $soxssArgs += "-q" }

Write-Step "Starting SOXSS with: $pythonExe $($soxssArgs -join ' ')"
Push-Location $RepoRoot
try {
    & $pythonExe @soxssArgs
}
finally {
    Pop-Location
}
