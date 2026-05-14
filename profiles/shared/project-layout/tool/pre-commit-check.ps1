# pre-commit-check.ps1 — run pre-commit validations in a Fabric project workspace.
# Run from the repository root before committing workspace/ or contracts/ changes.

$ErrorActionPreference = "Stop"
$ScriptDir   = $PSScriptRoot
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..")
$failed      = $false

$python = if ($env:PYTHON_BIN) { $env:PYTHON_BIN } else {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { $cmd.Source } else { $null }
}
if (-not $python) { Write-Error "python is required but was not found on PATH."; exit 127 }

function Write-Step { Write-Host ""; Write-Host "── $args ──────────────────────────────────────" }
function Write-Ok   { Write-Host "v $args" }
function Write-Err  { Write-Host "x $args" -ForegroundColor Red }

Write-Step "Pipeline staging-path consistency"
& $python "$ScriptDir\validate\pipeline-lineage.py"
if ($LASTEXITCODE -eq 0) { Write-Ok "pipeline-lineage passed" }
else { Write-Err "pipeline-lineage failed"; $failed = $true }

$contracts = @(Get-ChildItem -Path (Join-Path $ProjectRoot "contracts") -Filter "*.yaml" -ErrorAction SilentlyContinue) +
             @(Get-ChildItem -Path (Join-Path $ProjectRoot "contracts") -Filter "*.yml"  -ErrorAction SilentlyContinue)
if ($contracts.Count -gt 0) {
    Write-Step "Source contract validation"
    $contractPaths = $contracts | ForEach-Object { $_.FullName }
    & $python "$ScriptDir\validate\source-contract.py" @contractPaths
    if ($LASTEXITCODE -eq 0) { Write-Ok "source-contract passed" }
    else { Write-Err "source-contract failed"; $failed = $true }
}

Write-Host ""
Write-Host "════════════════════════════════════════════"
if ($failed) { Write-Err "Pre-commit checks failed"; exit 1 }
Write-Ok "All pre-commit checks passed"
