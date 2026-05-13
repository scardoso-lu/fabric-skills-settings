# setup.ps1 - idempotent target repository setup for Fabric agent projects.

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "../..")
$EnvFile = Join-Path $ProjectRoot ".env"
$EnvExample = Join-Path $ProjectRoot ".env.example"
$Actions = New-Object System.Collections.Generic.List[string]

function Read-DotEnv {
    param([string]$Path)

    foreach ($line in Get-Content -LiteralPath $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) {
            continue
        }
        $parts = $trimmed.Split("=", 2)
        $key = $parts[0].Trim()
        $value = $parts[1].Split("#", 2)[0].Trim().Trim('"').Trim("'")
        if ($key) {
            Set-Item -Path "Env:$key" -Value $value
        }
    }
}

Write-Host "-- Check uv"
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Error @"
uv is required but was not found on PATH.

Install uv, then rerun:
  https://docs.astral.sh/uv/getting-started/installation/
"@
    exit 1
}
$Actions.Add("uv found")

Write-Host "-- Check Microsoft Fabric CLI"
$FabSandbox = Join-Path $ScriptDir "fab-sandbox"
$fabReady = $false
try {
    & $FabSandbox --version *> $null
    if ($LASTEXITCODE -eq 0) {
        $fabReady = $true
    }
} catch {
    $fabReady = $false
}

if ($fabReady) {
    $Actions.Add("ms-fabric-cli already available")
} else {
    & uv tool install ms-fabric-cli
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
    $Actions.Add("ms-fabric-cli installed")
}

Write-Host "-- Check .env"
if (-not (Test-Path -LiteralPath $EnvFile)) {
    if (-not (Test-Path -LiteralPath $EnvExample)) {
        Write-Error "Missing .env and .env.example at project root."
        exit 1
    }
    Copy-Item -LiteralPath $EnvExample -Destination $EnvFile
    Write-Host @"
Created .env from .env.example.

Fill in FABRIC_WORKSPACE_ID in .env, then rerun:
  .\bin\setup\setup.ps1
"@
    exit 0
}
$Actions.Add(".env found")

Read-DotEnv -Path $EnvFile

if (-not $env:FABRIC_WORKSPACE_ID) {
    Write-Error @"
FABRIC_WORKSPACE_ID is missing in .env.

Edit .env and set:
  FABRIC_WORKSPACE_ID=<your-workspace-id>

Then rerun:
  .\bin\setup\setup.ps1
"@
    exit 1
}
$Actions.Add("FABRIC_WORKSPACE_ID set")

Write-Host "-- Authenticate Fabric CLI"
& $FabSandbox auth login
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
$Actions.Add("Fabric CLI auth login completed")

Write-Host ""
Write-Host "Setup complete."
foreach ($action in $Actions) {
    Write-Host "- $action"
}
