# pre-commit-check.ps1 - run pre-commit validations in a Fabric project workspace.
# Run from the repository root before committing workspace changes.

$ErrorActionPreference = "Stop"
$ProjectRootInput = if ($env:FABRIC_TARGET_ROOT) { $env:FABRIC_TARGET_ROOT } else { (Get-Location).Path }
$ProjectRoot = Resolve-Path -LiteralPath $ProjectRootInput
$failed = $false

function Write-Step { Write-Host ""; Write-Host "-- $args ----------------------------------------" }
function Write-Ok   { Write-Host "OK $args" }
function Write-Err  { Write-Host "ERROR $args" -ForegroundColor Red }

Write-Step "Deterministic lints"
fabric-vibe lint --target "$ProjectRoot"
if ($LASTEXITCODE -eq 0) { Write-Ok "lints passed" }
else { Write-Err "lints failed"; $failed = $true }

Write-Host ""
Write-Host "----------------------------------------"
if ($failed) { Write-Err "Pre-commit checks failed"; exit 1 }
Write-Ok "All pre-commit checks passed"
Write-Host ""
Write-Host "Note: pipeline staging-path consistency is checked via the"
Write-Host "      pipeline_lineage_check MCP tool; call it from your agent"
Write-Host "      after changing staging-path constants."
