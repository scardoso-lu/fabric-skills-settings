#!/usr/bin/env bash
# setup.sh - idempotent target repository setup for Fabric agent projects.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
ENV_FILE="${PROJECT_ROOT}/.env"
ENV_EXAMPLE="${PROJECT_ROOT}/.env.example"

actions=()

echo "-- Check uv"
if ! command -v uv >/dev/null 2>&1; then
  cat >&2 <<'EOF'
uv is required but was not found on PATH.

Install uv, then rerun:
  https://docs.astral.sh/uv/getting-started/installation/
EOF
  exit 1
fi
actions+=("uv found")

echo "-- Check Microsoft Fabric CLI"
if "${SCRIPT_DIR}/fab-sandbox" --version >/dev/null 2>&1; then
  actions+=("ms-fabric-cli already available")
else
  uv tool install ms-fabric-cli
  actions+=("ms-fabric-cli installed")
fi

echo "-- Check .env"
if [[ ! -f "$ENV_FILE" ]]; then
  if [[ ! -f "$ENV_EXAMPLE" ]]; then
    echo "Missing .env and .env.example at project root." >&2
    exit 1
  fi
  cp "$ENV_EXAMPLE" "$ENV_FILE"
  cat <<'EOF'
Created .env from .env.example.

Fill in FABRIC_WORKSPACE_ID in .env, then rerun:
  bin/setup/setup.sh
EOF
  exit 0
fi
actions+=(".env found")

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

if [[ -z "${FABRIC_WORKSPACE_ID:-}" ]]; then
  cat >&2 <<'EOF'
FABRIC_WORKSPACE_ID is missing in .env.

Edit .env and set:
  FABRIC_WORKSPACE_ID=<your-workspace-id>

Then rerun:
  bin/setup/setup.sh
EOF
  exit 1
fi
actions+=("FABRIC_WORKSPACE_ID set")

echo "-- Authenticate Fabric CLI"
"${SCRIPT_DIR}/fab-sandbox" auth login
actions+=("Fabric CLI auth login completed")

echo
echo "Setup complete."
for action in "${actions[@]}"; do
  echo "- ${action}"
done
