#Requires -Version 5.1
# setup.ps1 — single-shot CLI for the Fabric Agent Pack source clone (Windows).
#
#   Maintainer sanity check (no args):
#       .\setup.ps1
#
#   Install a profile into a target repo (one command):
#       .\setup.ps1 -Profile claude -Target C:\path\to\project
#       .\setup.ps1 -Profile all    -Target C:\path\to\project -DryRun
#       .\setup.ps1 -Profile claude -Target C:\path\to\project -Check
#       .\setup.ps1 -Profile claude -Target C:\path\to\project -Force -Backup
#
# After `pip install fabric-skills-settings`, the wheel installs the same
# command as `install-fabric-agent --profile claude --target C:\path\to\project`.

param(
    [ValidateSet('codex','claude','all')]
    [string]$Profile,
    [string]$Target,
    [switch]$DryRun,
    [switch]$Check,
    [switch]$Force,
    [switch]$Backup,
    [switch]$SelfTest,
    [switch]$NoBootstrap,
    [switch]$SkipValidators,
    [switch]$InstallTools,
    [switch]$Help
)

$ErrorActionPreference = 'Stop'
$ScriptDir = $PSScriptRoot

function Show-Usage {
    @'
fabric-skills-settings — single-shot setup CLI

Usage:
  .\setup.ps1                                            maintainer sanity check (no install)
  .\setup.ps1 -Profile <codex|claude|all> -Target <path> install profile into target repo
  .\setup.ps1 -Profile claude -Target C:\path -DryRun    preview without writing
  .\setup.ps1 -Profile claude -Target C:\path -Check     verify target state, exit 1 on diff
  .\setup.ps1 -Profile claude -Target C:\path -Force     overwrite non-managed files
  .\setup.ps1 -Profile claude -Target C:\path -Backup    back up replaced files

Switches:
  -NoBootstrap      skip the post-install target bootstrap (.venv, deps, Fabric auth prompts,
                    workspaces.json). Bootstrap runs by default unless -DryRun or -Check is set.
  -SkipValidators   skip the pre-install validator pass (validators run by default)
  -InstallTools     auto-install uv if missing
  -Help             show this message

After `pip install fabric-skills-settings`, the same install runs as:
  install-fabric-agent --profile claude --target C:\path\to\project
'@
}

function Write-Step  { Write-Host "`n-- $args ------------------------------------------" }
function Write-Ok    { Write-Host "v $args" }
function Write-Warn  { Write-Host "! $args" }
function Write-Fail  { Write-Host "x $args" -ForegroundColor Red }

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

function Invoke-Validators {
    Write-Step "Validators"
    uv run (Join-Path $ScriptDir 'packaging/validators/validate-install-package.py')
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "validate-install-package failed (exit $LASTEXITCODE)"
        exit $LASTEXITCODE
    }
    uv run (Join-Path $ScriptDir 'packaging/validators/validate-agent-guidance.py')
    if ($LASTEXITCODE -ne 0) {
        Write-Fail "validate-agent-guidance failed (exit $LASTEXITCODE)"
        exit $LASTEXITCODE
    }
}

if ($Help) {
    Show-Usage
    exit 0
}

# ── uv presence ───────────────────────────────────────────────────────────────
Write-Step "Tool checks"
Test-Tool -Name 'Git' -Cmd 'git' -Hint 'install Git from https://git-scm.com' | Out-Null
$uvFound = Test-Tool -Name 'uv' -Cmd 'uv' -Hint 'install from https://astral.sh/uv'
if (-not $uvFound) {
    if ($InstallTools) {
        Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
        Write-Ok "uv installed"
    } else {
        Write-Fail "uv is required. Re-run with -InstallTools or install from https://astral.sh/uv"
        exit 1
    }
}

# ── No-args path: maintainer sanity check ────────────────────────────────────
if (-not $Target) {
    Show-Usage
    Write-Step "Source package directories"
    foreach ($dir in @('profiles/codex','profiles/claude','profiles/shared','content','tool','mcp','packaging')) {
        if (Test-Path (Join-Path $ScriptDir $dir) -PathType Container) {
            Write-Ok "$dir/"
        } else {
            Write-Warn "missing $dir/"
        }
    }
    if (-not $SkipValidators) { Invoke-Validators }
    Write-Host "`nSanity check complete. To install, re-run with -Profile and -Target."
    exit 0
}

# ── Install path: validators (optional) then install-fabric-agent ────────────
if (-not $Profile) {
    Write-Fail "-Target was given without -Profile. Specify -Profile codex|claude|all."
    Show-Usage
    exit 2
}

if (-not $SkipValidators) {
    Invoke-Validators
}

Write-Step "Install profile '$Profile' into $Target"
$installerArgs = @('--profile', $Profile, '--target', $Target)
if ($DryRun)   { $installerArgs += '--dry-run' }
if ($Check)    { $installerArgs += '--check' }
if ($Force)    { $installerArgs += '--force' }
if ($Backup)      { $installerArgs += '--backup' }
if ($SelfTest)    { $installerArgs += '--self-test' }
if ($NoBootstrap) { $installerArgs += '--no-bootstrap' }

$installer = Join-Path $ScriptDir 'packaging/install-fabric-agent'
uv run python $installer @installerArgs
$installerExit = $LASTEXITCODE

if ($installerExit -ne 0) {
    Write-Fail "install-fabric-agent exited with $installerExit"
    exit $installerExit
}

Write-Host "`nDone. Open $Target in Claude Code or Codex and let the agent call graph_get_entry first."
