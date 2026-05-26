# smoke-test.ps1 — trigger and monitor a Fabric notebook job without deploying.
# The notebook must already be deployed in the workspace.
# Run from the repository root. Never targets production.
#
# Requires: python (>=3.10), fab authenticated (fab auth login),
#           FABRIC_WORKSPACE_ID in .env

param(
    [string]$Notebook = "",
    [string]$WorkspaceId = "",
    [switch]$Help
)

$ErrorActionPreference = "Stop"

$ProjectRootInput = if ($env:FABRIC_TARGET_ROOT) { $env:FABRIC_TARGET_ROOT } else { (Get-Location).Path }
$ProjectRoot = Resolve-Path -LiteralPath $ProjectRootInput
$EnvFile     = Join-Path $ProjectRoot ".env"

if ($Help -or (-not $Notebook)) {
    @'
Usage:
  fabric-cli notebook smoke-test -Notebook <name>

Options:
  -Notebook     Stem name of the notebook (e.g. bronze_electricity_day_ahead_prices).
                The notebook must already be deployed in the Fabric workspace.
  -WorkspaceId  Override FABRIC_WORKSPACE_ID from .env (optional).

Preconditions:
  - Run from the repository root.
  - The notebook is already deployed (run: fabric-cli notebook deploy deploy <name> <workspace_id>).
  - fab is authenticated (run: fab auth login).
  - FABRIC_WORKSPACE_ID is set in .env.
'@
    if (-not $Notebook) { exit 1 }
    exit 0
}

# Load .env
if (Test-Path -LiteralPath $EnvFile) {
    foreach ($line in Get-Content -LiteralPath $EnvFile) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) { continue }
        $parts = $trimmed.Split("=", 2)
        $key   = $parts[0].Trim()
        $value = $parts[1].Split("#", 2)[0].Trim().Trim('"').Trim("'")
        if ($key -and -not (Test-Path "Env:$key")) {
            Set-Item -Path "Env:$key" -Value $value
        }
    }
}

if (-not $WorkspaceId) { $WorkspaceId = $env:FABRIC_WORKSPACE_ID }
if (-not $WorkspaceId) {
    Write-Error "Missing workspace id. Set FABRIC_WORKSPACE_ID in .env."
    exit 1
}

fabric-cli notebook deploy exec $Notebook $WorkspaceId
exit $LASTEXITCODE
