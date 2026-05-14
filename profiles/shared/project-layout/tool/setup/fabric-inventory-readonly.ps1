# fabric-inventory-readonly.ps1 — Human-run read-only Fabric inventory helper.
# It never writes to .env, memory, or Fabric resources.
#
# Usage: bin\fabric-inventory-readonly.ps1 [--workspace-id <id>] [--items]

param(
    [string]$WorkspaceId = $env:FABRIC_WORKSPACE_ID,
    [switch]$Items,
    [switch]$Help
)

$ErrorActionPreference = "Stop"

if ($Help) {
    @'
Usage: bin\fabric-inventory-readonly.ps1 [--workspace-id <id>] [--items]

Read-only helper that prints Fabric workspace or item inventory using the Fabric CLI.
It never writes .env, memory, or Fabric resources. Humans copy approved sandbox IDs
manually after review.

Options:
  --workspace-id <id>  Workspace ID to inspect when using --items.
  --items              List items in the specified workspace.
  --help               Show this help.
'@
    exit 0
}

$UserProfile = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::UserProfile)
if (-not $UserProfile -and $env:USERPROFILE) { $UserProfile = $env:USERPROFILE }
$FabBin = Join-Path $UserProfile ".local\bin\fab.exe"
if (-not (Test-Path -LiteralPath $FabBin -PathType Leaf)) {
    $FabBin = Join-Path $UserProfile ".local\bin\fab"
}
if (-not (Test-Path -LiteralPath $FabBin -PathType Leaf)) {
    Write-Error "Fabric CLI (fab) is not installed at the expected user-local path. Run '.\setup.ps1 -InstallTools' first."
    exit 127
}

if ($Items) {
    if (-not $WorkspaceId) {
        Write-Error "--workspace-id is required for --items when FABRIC_WORKSPACE_ID is not set."
        exit 2
    }
    Write-Host "# Fabric items for workspace (read-only): $WorkspaceId"
    & $FabBin api get "/v1/workspaces/$WorkspaceId/items"
} else {
    Write-Host "# Fabric workspaces (read-only)"
    & $FabBin api get "/v1/workspaces"
}
