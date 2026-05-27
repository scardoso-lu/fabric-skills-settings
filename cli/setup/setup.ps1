# setup.ps1 - idempotent local setup for a Fabric agent target repo.
#
# Scope: configure the user's laptop so Claude/Codex can talk to the Fabric
# MCP server AND drive the local Fabric CLI (fab) for notebook / pipeline /
# lakehouse / workspace work. The MCP server itself lives in Docker — start
# it separately with `docker compose up --build` from the source repo's
# `server/` directory.
#
# This script:
#   1. Verifies uv is installed.
#   2. Installs rtk (token optimizer) from an upstream release with checksum verify.
#   3. Installs ms-fabric-cli via `uv tool install` so `fab` is on PATH.
#   4. Prompts for FABRIC_TENANT_ID / CLIENT_ID and writes them to .env.
#   5. Prompts for FABRIC_CLIENT_SECRET and persists to the user's OS env
#      (NOT .env - secrets stay in the OS env).
#   6. Prompts for MCP_SERVER_URL.
#   7. Writes .mcp.json and patches .codex/config.toml's [mcp_servers.fabric-server]
#      url (if installed).
#   8. Runs fabric-vibe auth refresh, which generates an RSA private key (stored
#      in .env as FABRIC_MCP_API_PRIVATE_KEY), writes the signed MCP token into
#      the client headers, and prints the public key to share with the MCP
#      server admin (added to the server's FABRIC_MCP_API_PUBLIC_KEY list).
#   9. Verifies SPN auth by calling `fab api workspaces`.
#  10. Runs fabric-vibe workspace init to populate workspaces.json.
#  11. Prompts to select the active workspace.

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$ProjectRootInput = if ($env:FABRIC_TARGET_ROOT) { $env:FABRIC_TARGET_ROOT } else { (Get-Location).Path }
$ProjectRoot = Resolve-Path -LiteralPath $ProjectRootInput
$EnvFile     = Join-Path $ProjectRoot ".env"
$Actions     = [System.Collections.Generic.List[string]]::new()

function Read-DotEnv ([string]$Path) {
    foreach ($line in Get-Content -LiteralPath $Path) {
        $t = $line.Trim()
        if (-not $t -or $t.StartsWith("#") -or -not $t.Contains("=")) { continue }
        $p = $t.Split("=", 2)
        $k = $p[0].Trim()
        $v = $p[1].Split("#", 2)[0].Trim().Trim('"').Trim("'")
        if ($k) { Set-Item -Path "Env:$k" -Value $v }
    }
}

function Write-EnvKey ([string]$Key, [string]$Value) {
    $lines = if (Test-Path -LiteralPath $EnvFile) { [System.IO.File]::ReadAllLines($EnvFile) } else { @() }
    $out   = [System.Collections.Generic.List[string]]::new()
    $found = $false
    foreach ($l in $lines) {
        if ($l -match "^${Key}\s*=") { $out.Add("${Key}=${Value}"); $found = $true }
        else { $out.Add($l) }
    }
    if (-not $found) { $out.Add("${Key}=${Value}") }
    [System.IO.File]::WriteAllLines($EnvFile, $out, [System.Text.UTF8Encoding]::new($false))
}

# -- uv -----------------------------------------------------------------------
Write-Host "-- Check uv"
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Error "uv is required.`nInstall: https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
}
$Actions.Add("uv found")

# -- rtk (token optimizer) ----------------------------------------------------
Write-Host "-- Check rtk (token optimizer)"
if (Get-Command rtk -ErrorAction SilentlyContinue) {
    $Actions.Add("rtk already installed")
} else {
    $rtkDir = Join-Path $env:USERPROFILE ".local\bin"
    try {
        $rel   = Invoke-RestMethod -Uri "https://api.github.com/repos/rtk-ai/rtk/releases/tags/v0.40.0" -ErrorAction Stop
        $asset = $rel.assets | Where-Object { $_.name -eq "rtk-x86_64-pc-windows-msvc.zip" } | Select-Object -First 1
        if (-not $asset) { throw "No Windows asset found" }
        $zip = Join-Path $env:TEMP "rtk-windows.zip"
        Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $zip -ErrorAction Stop
        $hash = (Get-FileHash -Path $zip -Algorithm SHA256).Hash
        $sha256Asset = $rel.assets | Where-Object { $_.name -eq "checksums.txt" } | Select-Object -First 1
        if (-not $sha256Asset) { throw "Missing checksums.txt for rtk v0.40.0" }
        $sha256File = Join-Path $env:TEMP "rtk-checksums.txt"
        Invoke-WebRequest -Uri $sha256Asset.browser_download_url -OutFile $sha256File -ErrorAction Stop
        $expectedLine = Get-Content $sha256File | Where-Object { $_ -like "*windows*msvc*.zip*" } | Select-Object -First 1
        Remove-Item $sha256File -ErrorAction SilentlyContinue
        if (-not $expectedLine) { throw "Missing checksum for $($asset.name)" }
        $expected = $expectedLine.Split()[0].ToUpperInvariant()
        if ($hash.ToUpperInvariant() -ne $expected) {
            Remove-Item $zip -ErrorAction SilentlyContinue
            throw "SHA-256 mismatch for rtk binary: expected $expected, got $hash"
        }
        New-Item -ItemType Directory -Force -Path $rtkDir | Out-Null
        Expand-Archive -Path $zip -DestinationPath $rtkDir -Force
        Remove-Item $zip
        $env:PATH = "$rtkDir;$env:PATH"
        $up = [Environment]::GetEnvironmentVariable("PATH", "User")
        if ($up -notlike "*$rtkDir*") { [Environment]::SetEnvironmentVariable("PATH", "$rtkDir;$up", "User") }
        $Actions.Add("rtk installed to $rtkDir")
    } catch {
        Write-Warning "rtk install failed: $_ (install manually: https://github.com/rtk-ai/rtk)"
        $Actions.Add("rtk not installed (optional)")
    }
}
if (Get-Command rtk -ErrorAction SilentlyContinue) {
    rtk init -g
    rtk init -g --codex
    $Actions.Add("rtk init -g completed")
}

# -- Microsoft Fabric CLI ----------------------------------------------------
Write-Host ""
Write-Host "-- Check Microsoft Fabric CLI"
$fabOk = $false
if (Get-Command fab -ErrorAction SilentlyContinue) {
    try { fab --version *> $null; $fabOk = $LASTEXITCODE -eq 0 } catch {}
}
if ($fabOk) {
    $Actions.Add("ms-fabric-cli already available")
} else {
    uv tool install ms-fabric-cli
    if ($LASTEXITCODE -ne 0) { Write-Error "ms-fabric-cli install failed"; exit $LASTEXITCODE }
    $Actions.Add("ms-fabric-cli installed (run 'uv tool update-shell' if 'fab' is not on PATH)")
}

# -- Load existing .env ------------------------------------------------------
if (Test-Path -LiteralPath $EnvFile) { Read-DotEnv -Path $EnvFile }

# -- Service-principal credentials -------------------------------------------
Write-Host ""
Write-Host "-- Service-principal credentials"

if ($env:FABRIC_TENANT_ID) {
    Write-Host "  FABRIC_TENANT_ID already set - skipping"
} else {
    $tenantId = Read-Host "  FABRIC_TENANT_ID (Azure tenant GUID)"
    if (-not $tenantId) { Write-Error "FABRIC_TENANT_ID is required."; exit 1 }
    Write-EnvKey -Key "FABRIC_TENANT_ID" -Value $tenantId
    $env:FABRIC_TENANT_ID = $tenantId
    $Actions.Add("FABRIC_TENANT_ID written to .env")
}

if ($env:FABRIC_CLIENT_ID) {
    Write-Host "  FABRIC_CLIENT_ID already set - skipping"
} else {
    $clientId = Read-Host "  FABRIC_CLIENT_ID (service principal app/client GUID)"
    if (-not $clientId) { Write-Error "FABRIC_CLIENT_ID is required."; exit 1 }
    Write-EnvKey -Key "FABRIC_CLIENT_ID" -Value $clientId
    $env:FABRIC_CLIENT_ID = $clientId
    $Actions.Add("FABRIC_CLIENT_ID written to .env")
}

if ($env:FABRIC_CLIENT_SECRET) {
    Write-Host "  FABRIC_CLIENT_SECRET already in OS environment - skipping"
} else {
    $ss     = Read-Host "  FABRIC_CLIENT_SECRET (input hidden; persisted to OS user environment, not .env)" -AsSecureString
    $secret = [System.Net.NetworkCredential]::new("", $ss).Password
    if (-not $secret) { Write-Error "FABRIC_CLIENT_SECRET is required."; exit 1 }
    [System.Environment]::SetEnvironmentVariable("FABRIC_CLIENT_SECRET", $secret, "User")
    $env:FABRIC_CLIENT_SECRET = $secret
    $Actions.Add("FABRIC_CLIENT_SECRET persisted to OS user environment (registry)")
}

# Map FABRIC_* → AZURE_* for child processes that call `fab` (Azure Identity
# reads AZURE_* for service-principal auth). The mapping is process-local and
# lasts only for this script's children — no Azure env vars are persisted.
$env:AZURE_TENANT_ID     = $env:FABRIC_TENANT_ID
$env:AZURE_CLIENT_ID     = $env:FABRIC_CLIENT_ID
$env:AZURE_CLIENT_SECRET = $env:FABRIC_CLIENT_SECRET

# -- MCP server URL ----------------------------------------------------------
Write-Host ""
Write-Host "-- MCP server URL"
if ($env:MCP_SERVER_URL) {
    Write-Host "  MCP_SERVER_URL already set - keeping $($env:MCP_SERVER_URL)"
    $mcpServerUrl = $env:MCP_SERVER_URL
} else {
    $mcpServerUrl = Read-Host "  MCP_SERVER_URL [http://127.0.0.1:8000]"
    if (-not $mcpServerUrl) { $mcpServerUrl = "http://127.0.0.1:8000" }
}

# -- MCP identity email ------------------------------------------------------
# fabric-vibe auth refresh signs this email with the generated private key.
Write-Host ""
Write-Host "-- MCP identity email"
if ($env:FABRIC_MCP_USER_EMAIL) {
    Write-Host "  FABRIC_MCP_USER_EMAIL already set - keeping $($env:FABRIC_MCP_USER_EMAIL)"
} else {
    $userEmail = Read-Host "  Your email (identity for MCP auth)"
    if (-not $userEmail) { Write-Error "An email is required for MCP auth."; exit 1 }
    $env:FABRIC_MCP_USER_EMAIL = $userEmail
}

# -- MCP client config (.mcp.json) -------------------------------------------
# Write url only; fabric-vibe auth refresh generates the RSA key pair under
# ~/.fabric-vibecoding and writes the signed token into MCP client headers below.
$McpJson = Join-Path $ProjectRoot ".mcp.json"
$mcpUrl  = "$($mcpServerUrl.TrimEnd('/'))/mcp"
$mcpDoc  = [ordered]@{ mcpServers = [ordered]@{ "fabric-server" = [ordered]@{ type = "http"; url = $mcpUrl } } }
$mcpDoc | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $McpJson -Encoding utf8
$Actions.Add(".mcp.json written ($mcpUrl)")

# Keep Codex's MCP config url aligned (auth header is written by fabric-vibe auth refresh).
$CodexConfig = Join-Path $ProjectRoot ".codex/config.toml"
if (Test-Path -LiteralPath $CodexConfig) {
    $lines    = [System.IO.File]::ReadAllLines($CodexConfig)
    $out      = [System.Collections.Generic.List[string]]::new()
    $inFabric = $false
    foreach ($line in $lines) {
        if ($line -match '^\[mcp_servers\.fabric-server\]') { $inFabric = $true;  $out.Add($line); continue }
        if ($line -match '^\[')                             { $inFabric = $false }
        if ($inFabric -and $line -match '^\s*url\s*=')     { $out.Add("url = `"$mcpUrl`""); continue }
        $out.Add($line)
    }
    [System.IO.File]::WriteAllLines($CodexConfig, $out, [System.Text.UTF8Encoding]::new($false))
    $Actions.Add(".codex/config.toml MCP url set ($mcpUrl)")
}

# -- MCP client token --------------------------------------------------------
Write-Host ""
Write-Host "-- MCP client token"
fabric-vibe auth refresh
if ($LASTEXITCODE -ne 0) { Write-Warning "MCP token refresh failed; run 'fabric-vibe auth refresh' manually." }
else { $Actions.Add("MCP token written to MCP client headers") }

# -- Authenticate ------------------------------------------------------------
# Use explicit SPN login. fab does NOT pick up AZURE_* env vars implicitly —
# the login subcommand populates fab's own credential cache.
Write-Host ""
Write-Host "-- Authenticate"
$loginOut = fab auth login `
    -u "$env:FABRIC_CLIENT_ID" `
    -p "$env:FABRIC_CLIENT_SECRET" `
    --tenant "$env:FABRIC_TENANT_ID" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host $loginOut
    Write-Host ""
    Write-Host "fab auth login flags (run 'fab auth login --help' for the current signature):"
    fab auth login --help 2>&1 | Write-Host
    Write-Error "fab auth login failed. Verify FABRIC_TENANT_ID / FABRIC_CLIENT_ID / FABRIC_CLIENT_SECRET are correct and that the service principal has Contributor on at least one Fabric workspace."
    exit 1
}
$probe = fab api workspaces --output_format json 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host $probe
    Write-Error "fab api workspaces failed after login. The SPN may not have access to any workspace yet."
    exit 1
}
$Actions.Add("SPN auth verified via fab auth login + fab api workspaces")

# -- Workspace registry ------------------------------------------------------
Write-Host ""
Write-Host "-- Workspace registry"
fabric-vibe workspace init
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$Actions.Add("workspaces.json refreshed from Fabric API")

# -- Active workspace selection ----------------------------------------------
# Run pick.py as a sibling script so its stdin stays attached to the parent
# terminal — interactive prompts only work when stdin is a real TTY.
fabric-vibe workspace pick
if ($LASTEXITCODE -eq 0) {
    $Actions.Add("active workspace selected and resource IDs written to .env")
} else {
    Write-Warning "Workspace selection skipped or failed; set it later with fabric-vibe workspace switch."
    $Actions.Add("active workspace not set (re-run fabric-vibe workspace switch)")
}

Write-Host ""
Write-Host "Setup complete."
foreach ($a in $Actions) { Write-Host "- $a" }
Write-Host ""
Write-Host "Next: Open Claude Code (or Codex) in this project."
