#Requires -Version 5.1
# setup.ps1 — source-package sanity setup for Fabric Agent Pack maintainers (Windows).

param(
    [switch]$InstallTools,
    [switch]$Help
)

$ErrorActionPreference = 'Stop'
$ScriptDir = $PSScriptRoot

if ($Help) {
    @'
Usage: .\setup.ps1 [-InstallTools]

Checks this source package and optionally installs developer tools. To install
agent profiles into a Fabric project repository, use bin/install-fabric-agent.
'@
    exit 0
}

function Write-Step  { Write-Host "`n-- $args ------------------------------------------" }
function Write-Ok    { Write-Host "v $args" }
function Write-Warn  { Write-Host "! $args" }

# ── Source package directories ───────────────────────────────────────────────
Write-Step "Source package directories"
foreach ($dir in @('profiles/codex','profiles/claude','profiles/shared','rules','bin','memory')) {
    if (Test-Path (Join-Path $ScriptDir $dir) -PathType Container) {
        Write-Ok "$dir/"
    } else {
        Write-Warn "missing $dir/"
    }
}

# ── Tool checks ───────────────────────────────────────────────────────────────
Write-Step "Tool checks"
function Test-Tool {
    param([string]$Name, [string]$Cmd, [string]$Hint)
    if (Get-Command $Cmd -ErrorAction SilentlyContinue) {
        Write-Ok "${Name}: found"
        return $true
    } else {
        Write-Warn "${Name}: not found -- $Hint"
        return $false
    }
}

Test-Tool -Name 'Git' -Cmd 'git' -Hint 'install Git from https://git-scm.com' | Out-Null

$uvFound = Test-Tool -Name 'uv' -Cmd 'uv' -Hint 'optional: install from https://astral.sh/uv'
if (-not $uvFound -and $InstallTools) {
    Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
    Write-Ok "uv installed"
}

# ── Validation ────────────────────────────────────────────────────────────────
Write-Step "Validation"
uv run (Join-Path $ScriptDir 'bin/validate-install-package.py')
uv run (Join-Path $ScriptDir 'bin/validate-agent-guidance.py')

@'

Next step: install profiles into a target git repository, then run agents there:
  python bin/install-fabric-agent --profile all --target C:\path\to\project --dry-run
  python bin/install-fabric-agent --profile all --target C:\path\to\project
'@
