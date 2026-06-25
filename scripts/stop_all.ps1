[CmdletBinding()]
param(
    [switch]$IncludeNode,
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Step([string]$Message) {
    Write-Host "[stop-all] $Message"
}

function Stop-ByName {
    param(
        [string[]]$Names
    )

    foreach ($name in $Names) {
        $procs = Get-Process -Name $name -ErrorAction SilentlyContinue
        if (-not $procs) {
            continue
        }

        foreach ($proc in $procs) {
            if ($DryRun) {
                Write-Host "Would stop process: $($proc.ProcessName) (PID=$($proc.Id))"
            }
            else {
                Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
                Write-Host "Stopped process: $($proc.ProcessName) (PID=$($proc.Id))"
            }
        }
    }
}

function Stop-ByCommandLinePattern {
    param(
        [string[]]$Patterns
    )

    $targets = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {
            $cmd = $_.CommandLine
            if (-not $cmd) {
                return $false
            }
            foreach ($pattern in $Patterns) {
                if ($cmd -match $pattern) {
                    return $true
                }
            }
            return $false
        }

    foreach ($proc in $targets) {
        if ($DryRun) {
            Write-Host "Would stop by command line: PID=$($proc.ProcessId) NAME=$($proc.Name)"
            continue
        }

        try {
            Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
            Write-Host "Stopped by command line: PID=$($proc.ProcessId) NAME=$($proc.Name)"
        }
        catch {
            # Ignore races where process has just exited.
        }
    }
}

Write-Step "Stopping tunnel processes (cloudflared/ngrok)"
Stop-ByName -Names @("cloudflared", "ngrok")

Write-Step "Stopping Python processes for SOXSS and twister"
Stop-ByCommandLinePattern -Patterns @(
    "Socxss\.py",
    "twister[\\/]server\.py",
    "server[\\/]server\.py"
)

if ($IncludeNode) {
    Write-Step "Stopping node/npx processes"
    Stop-ByName -Names @("node", "npx")
}

Write-Step "Done"
