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

echo "-- Check rtk (token optimizer)"
if command -v rtk >/dev/null 2>&1; then
  actions+=("rtk already installed")
else
  if curl -fsSL https://raw.githubusercontent.com/rtk-ai/rtk/refs/heads/master/install.sh | sh; then
    # install.sh puts binary in ~/.local/bin; add to PATH for this session
    export PATH="$HOME/.local/bin:$PATH"
    if command -v rtk >/dev/null 2>&1; then
      actions+=("rtk installed — ensure ~/.local/bin is in your PATH (add to ~/.bashrc or ~/.zshrc)")
    else
      echo "   rtk installed to ~/.local/bin but not found on PATH." >&2
      echo '   Add to your shell profile: export PATH="$HOME/.local/bin:$PATH"' >&2
      actions+=("rtk installed (restart shell or add ~/.local/bin to PATH)")
    fi
  else
    echo "   rtk install failed — install manually: https://github.com/rtk-ai/rtk" >&2
    actions+=("rtk not installed (optional, install manually)")
  fi
fi

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
    cat >&2 <<'EOF'
Missing .env and .env.example at project root.

This script is for installed target repositories only.
If you are in the fabric-skills-settings source package, run the source setup instead:
  bash setup.sh
EOF
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
