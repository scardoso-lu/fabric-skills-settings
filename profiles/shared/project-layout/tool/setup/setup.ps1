# setup.ps1 - idempotent target repository setup for Fabric agent projects.

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "../..")
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

# ── uv ────────────────────────────────────────────────────────────────────────
Write-Host "-- Check uv"
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Error "uv is required.`nInstall: https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
}
$Actions.Add("uv found")

# ── rtk ───────────────────────────────────────────────────────────────────────
Write-Host "-- Check rtk (token optimizer)"
if (Get-Command rtk -ErrorAction SilentlyContinue) {
    $Actions.Add("rtk already installed")
} else {
    $rtkDir = Join-Path $env:USERPROFILE ".local\bin"
    try {
        $rel   = Invoke-RestMethod -Uri "https://api.github.com/repos/rtk-ai/rtk/releases/tags/v0.40.0" -ErrorAction Stop
        $asset = $rel.assets | Where-Object { $_.name -eq "rtk-x86_64-pc-windows-msvc.zip" } | Select-Object -First 1
        if (-not $asset) { throw "No Windows asset found" }
        $zip   = Join-Path $env:TEMP "rtk-windows.zip"
        Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $zip -ErrorAction Stop
        # Compute and display SHA-256 so the user can verify against the published release (H-02)
        $hash = (Get-FileHash -Path $zip -Algorithm SHA256).Hash
        Write-Host "  rtk SHA-256: $hash"
        Write-Host "  Verify at: https://github.com/rtk-ai/rtk/releases"
        # Verify against the pinned release checksum before extracting (H-02).
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
        Write-Host "  Hash verified against rtk v0.40.0 checksums.txt."
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

# ── Fabric CLI ────────────────────────────────────────────────────────────────
Write-Host "-- Check Microsoft Fabric CLI"
$FabSandbox = Join-Path $ScriptDir "fab-sandbox.ps1"
$fabOk = $false
try { & $FabSandbox --version *> $null; $fabOk = $LASTEXITCODE -eq 0 } catch {}
if ($fabOk) {
    $Actions.Add("ms-fabric-cli already available")
} else {
    uv tool install ms-fabric-cli
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $Actions.Add("ms-fabric-cli installed")
}

# ── Load existing .env ────────────────────────────────────────────────────────
if (Test-Path -LiteralPath $EnvFile) { Read-DotEnv -Path $EnvFile }

# ── Credentials ───────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "-- Credentials"

if ($env:FABRIC_WORKSPACE_ID) {
    Write-Host "  FABRIC_WORKSPACE_ID already set -skipping"
} else {
    $wsId = Read-Host "  FABRIC_WORKSPACE_ID (Fabric workspace GUID)"
    if (-not $wsId) { Write-Error "FABRIC_WORKSPACE_ID is required."; exit 1 }
    Write-EnvKey -Key "FABRIC_WORKSPACE_ID" -Value $wsId
    $env:FABRIC_WORKSPACE_ID = $wsId
    $Actions.Add("FABRIC_WORKSPACE_ID written to .env")
}

if ($env:FABRIC_TENANT_ID) {
    Write-Host "  FABRIC_TENANT_ID already set -skipping"
} else {
    $tenantId = Read-Host "  FABRIC_TENANT_ID (Azure tenant GUID)"
    if (-not $tenantId) { Write-Error "FABRIC_TENANT_ID is required."; exit 1 }
    Write-EnvKey -Key "FABRIC_TENANT_ID" -Value $tenantId
    $env:FABRIC_TENANT_ID = $tenantId
    $Actions.Add("FABRIC_TENANT_ID written to .env")
}

if ($env:FABRIC_CLIENT_ID) {
    Write-Host "  FABRIC_CLIENT_ID already set -skipping"
} else {
    $clientId = Read-Host "  FABRIC_CLIENT_ID (service principal app/client GUID)"
    if (-not $clientId) { Write-Error "FABRIC_CLIENT_ID is required."; exit 1 }
    Write-EnvKey -Key "FABRIC_CLIENT_ID" -Value $clientId
    $env:FABRIC_CLIENT_ID = $clientId
    $Actions.Add("FABRIC_CLIENT_ID written to .env")
}

if ($env:FABRIC_CLIENT_SECRET) {
    Write-Host "  FABRIC_CLIENT_SECRET already in OS environment -skipping"
} else {
    $ss     = Read-Host "  FABRIC_CLIENT_SECRET (input hidden; persisted to OS user environment, not .env)" -AsSecureString
    $secret = [System.Net.NetworkCredential]::new("", $ss).Password
    if (-not $secret) { Write-Error "FABRIC_CLIENT_SECRET is required."; exit 1 }
    [System.Environment]::SetEnvironmentVariable("FABRIC_CLIENT_SECRET", $secret, "User")
    $env:FABRIC_CLIENT_SECRET = $secret
    $Actions.Add("FABRIC_CLIENT_SECRET persisted to OS user environment (registry)")
}

# ── Authenticate ───────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "-- Authenticate"
& $FabSandbox api workspaces --output_format json *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Error "Authentication failed. Verify FABRIC_TENANT_ID, FABRIC_CLIENT_ID, and FABRIC_CLIENT_SECRET."
    exit 1
}
$Actions.Add("SPN auth verified")

Write-Host ""
Write-Host "Setup complete."
foreach ($a in $Actions) { Write-Host "- $a" }
