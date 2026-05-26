# pre-commit-check.ps1 — run pre-commit validations in a Fabric project workspace.
# Run from the repository root before committing workspace changes.

$ErrorActionPreference = "Stop"
$ScriptDir   = $PSScriptRoot
# Installed at the target as tool/precommit/, so the project root is two levels up.
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..\..")
$failed      = $false

$python = if ($env:PYTHON_BIN) { $env:PYTHON_BIN } else {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { $cmd.Source } else { $null }
}
if (-not $python) { Write-Error "python is required but was not found on PATH."; exit 127 }

function Write-Step { Write-Host ""; Write-Host "── $args ──────────────────────────────────────" }
function Write-Ok   { Write-Host "v $args" }
function Write-Err  { Write-Host "x $args" -ForegroundColor Red }

Write-Step "Deterministic lints (tool/lint/)"
& $python -m tool.lint --target "$ProjectRoot"
if ($LASTEXITCODE -eq 0) { Write-Ok "lints passed" }
else { Write-Err "lints failed"; $failed = $true }

Write-Host ""
Write-Host "════════════════════════════════════════════"
if ($failed) { Write-Err "Pre-commit checks failed"; exit 1 }
Write-Ok "All pre-commit checks passed"
Write-Host ""
Write-Host "Note: pipeline staging-path consistency is checked via the"
Write-Host "      pipeline_lineage_check MCP tool — call it from your agent"
Write-Host "      after changing staging-path constants."
