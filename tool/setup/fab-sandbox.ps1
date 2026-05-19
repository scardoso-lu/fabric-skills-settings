# fab-sandbox.ps1 - Windows companion to fab-sandbox (bash).
# Keeps Fabric CLI config/cache isolated from the user profile.
# Never use this wrapper for production.
#
# Usage: tool\setup\fab-sandbox.ps1 [fab arguments...]
# Example: tool\setup\fab-sandbox.ps1 --version
#          tool\setup\fab-sandbox.ps1 api workspaces --output_format json

$ErrorActionPreference = "Stop"

# ── Sandbox home — user-owned directory, not world-writable /tmp (H-03) ───────
$realUserProfile = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::UserProfile)
if (-not $realUserProfile -and $env:USERPROFILE) {
    $realUserProfile = $env:USERPROFILE
}
if (-not $realUserProfile) {
    Write-Error "Could not resolve the current user's profile directory."; exit 1
}
$realUserProfile = [System.IO.Path]::GetFullPath($realUserProfile)

$FAB_SANDBOX_HOME = if ($env:FAB_SANDBOX_HOME) {
    $env:FAB_SANDBOX_HOME
} else {
    Join-Path $realUserProfile ".local\state\fabric-fab-home"
}

# Validate FAB_SANDBOX_HOME is within the effective user profile to prevent symlink injection.
$realSandboxHome = [System.IO.Path]::GetFullPath($FAB_SANDBOX_HOME)
$sep = [System.IO.Path]::DirectorySeparatorChar
if (-not ($realSandboxHome.Equals($realUserProfile, [System.StringComparison]::OrdinalIgnoreCase) -or
          $realSandboxHome.StartsWith($realUserProfile + $sep, [System.StringComparison]::OrdinalIgnoreCase))) {
    Write-Error "FAB_SANDBOX_HOME must be within the user profile directory. Got: $FAB_SANDBOX_HOME"; exit 1
}

New-Item -ItemType Directory -Force -Path $realSandboxHome | Out-Null

$fab = Join-Path $realUserProfile ".local\bin\fab.exe"
if (-not (Test-Path -LiteralPath $fab -PathType Leaf)) {
    $fab = Join-Path $realUserProfile ".local\bin\fab"
}
if (-not (Test-Path -LiteralPath $fab -PathType Leaf)) {
    Write-Error "fab executable not found in $realUserProfile\.local\bin. Install with: uv tool install ms-fabric-cli"
    exit 127
}

# Load the three Fabric config vars from .env (two levels up from this script's directory).
# FABRIC_CLIENT_SECRET is intentionally excluded — it must come from the OS environment only.
function Read-EnvKey ([string]$Key, [string]$DotEnvPath) {
    $match = Select-String -LiteralPath $DotEnvPath -Pattern "^$([regex]::Escape($Key))\s*=" | Select-Object -Last 1
    if ($match) {
        $v = $match.Line.Split("=", 2)[1].Split("#", 2)[0].Trim().Trim('"').Trim("'")
        if ($v) { Set-Item -Path "Env:$Key" -Value $v }
    }
}
$_repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$_dotEnv   = Join-Path $_repoRoot ".env"
if (Test-Path -LiteralPath $_dotEnv) {
    Read-EnvKey "FABRIC_WORKSPACE_ID" $_dotEnv
    Read-EnvKey "FABRIC_CLIENT_ID"    $_dotEnv
    Read-EnvKey "FABRIC_TENANT_ID"    $_dotEnv
}

$savedUserProfile       = $env:USERPROFILE
$savedHomeDrive         = $env:HOMEDRIVE
$savedHomePath          = $env:HOMEPATH
$savedFabSpnClientId     = $env:FAB_SPN_CLIENT_ID
$savedFabSpnClientSecret = $env:FAB_SPN_CLIENT_SECRET
$savedFabTenantId        = $env:FAB_TENANT_ID
try {
    $env:USERPROFILE = $FAB_SANDBOX_HOME
    $env:HOMEDRIVE   = Split-Path -Qualifier $FAB_SANDBOX_HOME
    $env:HOMEPATH    = $FAB_SANDBOX_HOME.Substring($env:HOMEDRIVE.Length)

    # Map repo credentials to the Fabric CLI SPN env vars.
    # Credentials are passed via environment, never on the command line (C-02).
    if ($env:FABRIC_CLIENT_ID -and $env:FABRIC_CLIENT_SECRET -and $env:FABRIC_TENANT_ID) {
        $env:FAB_SPN_CLIENT_ID     = $env:FABRIC_CLIENT_ID
        $env:FAB_SPN_CLIENT_SECRET = $env:FABRIC_CLIENT_SECRET
        $env:FAB_TENANT_ID         = $env:FABRIC_TENANT_ID
    }

    $savedErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $fab @args
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $savedErrorActionPreference
    }
} finally {
    $env:USERPROFILE         = $savedUserProfile
    $env:HOMEDRIVE           = $savedHomeDrive
    $env:HOMEPATH            = $savedHomePath
    $env:FAB_SPN_CLIENT_ID     = $savedFabSpnClientId
    $env:FAB_SPN_CLIENT_SECRET = $savedFabSpnClientSecret
    $env:FAB_TENANT_ID         = $savedFabTenantId
}
exit $exitCode
