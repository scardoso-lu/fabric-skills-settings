# fab-sandbox.ps1 — Windows companion to fab-sandbox (bash).
# Keeps Fabric CLI config/cache isolated from the user profile.
# Never use this wrapper for production.
#
# Usage: bin\setup\fab-sandbox.ps1 [fab arguments...]
# Example: bin\setup\fab-sandbox.ps1 --version
#          bin\setup\fab-sandbox.ps1 api workspaces --output_format json

$ErrorActionPreference = "Stop"

$FAB_SANDBOX_HOME = if ($env:FAB_SANDBOX_HOME) {
    $env:FAB_SANDBOX_HOME
} else {
    Join-Path ([System.IO.Path]::GetTempPath()) "fabric-fab-home"
}
New-Item -ItemType Directory -Force -Path $FAB_SANDBOX_HOME | Out-Null

if ($env:FAB_BIN) {
    $fab = $env:FAB_BIN
} else {
    $fabCmd = Get-Command fab -ErrorAction SilentlyContinue
    if ($fabCmd) {
        $fab = $fabCmd.Source
    } else {
        Write-Error "fab executable not found. Install with: uv tool install ms-fabric-cli"
        exit 127
    }
}

$savedUserProfile = $env:USERPROFILE
$savedHomeDrive   = $env:HOMEDRIVE
$savedHomePath    = $env:HOMEPATH
try {
    $env:USERPROFILE = $FAB_SANDBOX_HOME
    $env:HOMEDRIVE   = Split-Path -Qualifier $FAB_SANDBOX_HOME
    $env:HOMEPATH    = $FAB_SANDBOX_HOME.Substring($env:HOMEDRIVE.Length)
    & $fab @args
    $exitCode = $LASTEXITCODE
} finally {
    $env:USERPROFILE = $savedUserProfile
    $env:HOMEDRIVE   = $savedHomeDrive
    $env:HOMEPATH    = $savedHomePath
}
exit $exitCode
