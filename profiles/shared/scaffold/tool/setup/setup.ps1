# setup.ps1 - idempotent target repository setup for Fabric agent projects.

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "../..")
$EnvFile     = Join-Path $ProjectRoot ".env"
$VenvDir     = Join-Path $ProjectRoot ".venv"
$VenvPython  = Join-Path $VenvDir "Scripts\python.exe"
$Actions     = [System.Collections.Generic.List[string]]::new()
$SecretWasInEnvironment = $false
$HelperPackages = @(
    "Faker>=26",
    "mimesis>=18",
    "scikit-learn>=1.5",
    "semantic-link>=0.9",
    "pandas>=2",
    "networkx>=3.2",
    "rank_bm25>=0.2.2"
)

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

# ── Mock-data libraries ───────────────────────────────────────────────────────
Write-Host ""
Write-Host "-- Project Python environment (.venv)"
if (-not (Test-Path -LiteralPath $VenvDir)) {
    uv venv $VenvDir
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    uv pip install --python $VenvPython @HelperPackages
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $Actions.Add(".venv created")
    $Actions.Add("Python helper libraries installed in .venv")
} else {
    $Actions.Add(".venv already exists")
    & $VenvPython -c "import networkx, rank_bm25" *> $null
    if ($LASTEXITCODE -ne 0) {
        uv pip install --python $VenvPython "networkx>=3.2" "rank_bm25>=0.2.2"
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        $Actions.Add("Graph helper libraries installed in existing .venv")
    } else {
        $Actions.Add("Graph helper libraries already available")
    }
}

# Knowledge graph artifacts are shipped pre-built by install-fabric-agent.
# Incremental updates flow through the fabric-graph MCP server's CRUD writes
# (tool/graph/writes.py), which atomically rebuilds memory/.graph on every change.
Write-Host ""
Write-Host "-- Knowledge graph"
$GraphJson = Join-Path $ProjectRoot "memory\.graph\graph.json"
if (Test-Path -LiteralPath $GraphJson) {
    $Actions.Add("knowledge graph present at memory/.graph (shipped by installer)")
} else {
    Write-Warning "memory/.graph/graph.json not found. Re-run install-fabric-agent to refresh the shipped graph."
    $Actions.Add("knowledge graph missing -- re-run install-fabric-agent")
}

# ── Load existing .env ────────────────────────────────────────────────────────
if (Test-Path -LiteralPath $EnvFile) { Read-DotEnv -Path $EnvFile }

# ── Credentials ───────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "-- Credentials"

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
    $SecretWasInEnvironment = $true
} else {
    $ss     = Read-Host "  FABRIC_CLIENT_SECRET (input hidden; persisted to OS user environment, not .env)" -AsSecureString
    $secret = [System.Net.NetworkCredential]::new("", $ss).Password
    if (-not $secret) { Write-Error "FABRIC_CLIENT_SECRET is required."; exit 1 }
    [System.Environment]::SetEnvironmentVariable("FABRIC_CLIENT_SECRET", $secret, "User")
    $env:FABRIC_CLIENT_SECRET = $secret
    $SecretWasInEnvironment = $true
    $Actions.Add("FABRIC_CLIENT_SECRET persisted to OS user environment (registry)")
}

# ── Authenticate ───────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "-- Authenticate"
& $FabSandbox api workspaces --output_format json *> $null
if ($LASTEXITCODE -ne 0) {
    if ($SecretWasInEnvironment) {
        Write-Host "  To clear the saved FABRIC_CLIENT_SECRET, run:"
        Write-Host "  [Environment]::SetEnvironmentVariable('FABRIC_CLIENT_SECRET', `$null, 'User'); Remove-Item Env:FABRIC_CLIENT_SECRET -ErrorAction SilentlyContinue"
    }
    Write-Error "Authentication failed. Verify FABRIC_TENANT_ID, FABRIC_CLIENT_ID, and FABRIC_CLIENT_SECRET."
    exit 1
}
$Actions.Add("SPN auth verified")

# Workspace registry is the only source for workspace/resource IDs.
Write-Host ""
Write-Host "-- Workspace registry"
Write-Host "  Discovering Fabric workspaces via API..."
$WorkspaceInit = Join-Path $ProjectRoot "tool\workspace\init.py"
& $VenvPython $WorkspaceInit
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$Actions.Add("workspaces.json refreshed from Fabric API")

# Interactive active-workspace selection.
# Env override:  FABRIC_WORKSPACE_DISPLAYNAME=<name>  -> pick non-interactively
# Single workspace:                                   -> auto-select
# Non-TTY stdin:                                      -> skip; user runs switch.py later
# Multiple workspaces on a TTY:                       -> number-prompt, then call switch.py
$WorkspaceSelector = @'
import json
import os
import subprocess
import sys
from pathlib import Path

REGISTRY = Path("workspaces.json")
try:
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError) as exc:
    print(f"  Could not read workspaces.json: {exc}", file=sys.stderr)
    sys.exit(1)

workspaces = reg.get("workspaces", [])
active = reg.get("active")

if active:
    print(f"  Active workspace already set: {active}")
    sys.exit(0)

if not workspaces:
    print("  No accessible workspaces. Verify service-principal Contributor role on a Fabric workspace.", file=sys.stderr)
    sys.exit(1)

print(f"  Found {len(workspaces)} workspace(s):")
for idx, ws in enumerate(workspaces, 1):
    print(f"    {idx}. {ws.get('displayName', '<unnamed>')}")

override = os.environ.get("FABRIC_WORKSPACE_DISPLAYNAME", "").strip()
if override:
    print(f"\n  FABRIC_WORKSPACE_DISPLAYNAME={override!r}; using that.")
    selection = override
elif len(workspaces) == 1:
    selection = workspaces[0].get("displayName", "")
    print(f"\n  Only one workspace; auto-selecting {selection!r}.")
elif not sys.stdin.isatty():
    print("\n  stdin is not a TTY; skipping interactive prompt.")
    print("  Inside the target, run:  python tool/workspace/switch.py <displayName>")
    sys.exit(0)
else:
    raw = input("\n  Pick the active workspace (number or displayName): ").strip()
    if not raw:
        print("  No selection; skipping.")
        sys.exit(0)
    if raw.isdigit():
        i = int(raw) - 1
        if not (0 <= i < len(workspaces)):
            print(f"  Out of range: {raw}", file=sys.stderr)
            sys.exit(1)
        selection = workspaces[i].get("displayName", "")
    else:
        selection = raw

rc = subprocess.run(
    [sys.executable, "tool/workspace/switch.py", selection]
).returncode
sys.exit(rc)
'@
$WorkspaceSelector | & $VenvPython -
if ($LASTEXITCODE -eq 0) {
    $Actions.Add("active workspace selected and resource IDs written to .env")
} else {
    Write-Warning "Workspace selection skipped or failed; you can set it later with tool/workspace/switch.py."
    $Actions.Add("active workspace not set (re-run tool/workspace/switch.py)")
}

Write-Host ""
Write-Host "Setup complete."
foreach ($a in $Actions) { Write-Host "- $a" }
