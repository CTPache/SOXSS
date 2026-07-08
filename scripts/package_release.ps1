[CmdletBinding()]
param(
    [string]$RepoRoot = "",
    [string]$ReleaseDirName = "release",
    [switch]$IncludeUntracked,
    [switch]$Zip
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
    Write-Host "[package-release] $Message"
}

function Should-SkipPath {
    param(
        [string]$RelativePath,
        [string[]]$ExactSkips,
        [string[]]$PrefixSkips
    )

    if ([string]::IsNullOrWhiteSpace($RelativePath)) {
        return $true
    }

    $normalized = $RelativePath -replace "\\", "/"
    if ($ExactSkips -contains $normalized) {
        return $true
    }

    foreach ($prefix in $PrefixSkips) {
        if ($normalized.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
            return $true
        }
    }

    return $false
}

function Copy-ProjectFile {
    param(
        [string]$RelativePath,
        [string]$SourceRoot,
        [string]$DestinationRoot
    )

    $source = Join-Path $SourceRoot $RelativePath
    if (-not (Test-Path -Path $source -PathType Leaf)) {
        return $false
    }

    $destination = Join-Path $DestinationRoot $RelativePath
    $destinationDir = Split-Path -Parent $destination
    if ($destinationDir -and -not (Test-Path -Path $destinationDir)) {
        New-Item -ItemType Directory -Path $destinationDir -Force | Out-Null
    }

    Copy-Item -Path $source -Destination $destination -Force
    return $true
}

$gitDir = Join-Path $RepoRoot ".git"
if (-not (Test-Path -Path $gitDir -PathType Container)) {
    throw "No git repository found at: $RepoRoot"
}

$releasePath = Join-Path $RepoRoot $ReleaseDirName
if (Test-Path -Path $releasePath) {
    Write-Step "Removing existing release directory: $releasePath"
    Remove-Item -Path $releasePath -Recurse -Force
}
New-Item -ItemType Directory -Path $releasePath | Out-Null

$exactSkips = @(
    ".gitignore",
    ".gitattributes",
    ".gitmodules",
    ".coveragerc"
)

$prefixSkips = @(
    ".git/",
    ".github/",
    ".claude/",
    "$ReleaseDirName/"
)

Write-Step "Collecting tracked files"
$paths = git -C $RepoRoot ls-files

if ($IncludeUntracked) {
    Write-Step "Including non-ignored untracked files"
    $paths += git -C $RepoRoot ls-files --others --exclude-standard
}

$copied = 0
$seen = New-Object System.Collections.Generic.HashSet[string] ([System.StringComparer]::OrdinalIgnoreCase)

foreach ($path in $paths) {
    if (-not $path) {
        continue
    }

    $relative = ($path -replace "\\", "/").Trim()
    if (-not $seen.Add($relative)) {
        continue
    }

    if (Should-SkipPath -RelativePath $relative -ExactSkips $exactSkips -PrefixSkips $prefixSkips) {
        continue
    }

    if (Copy-ProjectFile -RelativePath $relative -SourceRoot $RepoRoot -DestinationRoot $releasePath) {
        $copied++
    }
}

Write-Step "Copied $copied file(s) to $releasePath"

if ($Zip) {
    $zipPath = Join-Path $RepoRoot "$ReleaseDirName.zip"
    if (Test-Path -Path $zipPath) {
        Remove-Item -Path $zipPath -Force
    }

    Write-Step "Creating archive: $zipPath"
    Compress-Archive -Path (Join-Path $releasePath "*") -DestinationPath $zipPath -CompressionLevel Optimal
}

Write-Step "Done"