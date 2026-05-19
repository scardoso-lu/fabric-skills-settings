#!/usr/bin/env bash
# setup.sh - idempotent target repository setup for Fabric agent projects.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
ENV_FILE="${PROJECT_ROOT}/.env"
VENV_DIR="${PROJECT_ROOT}/.venv"
VENV_PY="${VENV_DIR}/bin/python"

actions=()

write_env_key() {
  local key="$1" value="$2"
  touch "$ENV_FILE"
  if grep -qE "^${key}\s*=" "$ENV_FILE"; then
    sed -i.bak "s|^${key}\s*=.*|${key}=${value}|" "$ENV_FILE" && rm -f "${ENV_FILE}.bak"
  else
    printf '%s=%s\n' "$key" "$value" >> "$ENV_FILE"
  fi
}

persist_secret() {
  local key="$1" value="$2"
  case "${SHELL:-}" in
    */zsh)  profile="$HOME/.zprofile" ;;
    */bash) profile="$HOME/.bash_profile" ;;
    *)      profile="$HOME/.profile" ;;
  esac
  if grep -q "^export ${key}=" "$profile" 2>/dev/null; then
    sed -i.bak "s|^export ${key}=.*|export ${key}=${value}|" "$profile" && rm -f "${profile}.bak"
  else
    printf '\nexport %s=%s\n' "$key" "$value" >> "$profile"
  fi
  # Restrict profile permissions — shell profiles should not be world-readable (H-04)
  chmod 600 "$profile"
  echo "  Persisted to ${profile} (chmod 600) — reopen terminals to pick it up."
}

# Safe .env parser — reads KEY=VALUE pairs without executing the file (H-01)
# Contrast with 'source .env' which executes arbitrary shell code.
_load_dot_env() {
  local file="$1" line key val
  while IFS= read -r line || [[ -n "$line" ]]; do
    # Strip inline comments, then trim leading/trailing whitespace
    line="${line%%#*}"
    line="${line#"${line%%[![:space:]]*}"}"
    line="${line%"${line##*[![:space:]]}"}"
    [[ -z "$line" || "$line" != *"="* ]] && continue
    key="${line%%=*}"
    val="${line#*=}"
    # Strip surrounding quotes
    val="${val%\"}" val="${val#\"}"
    val="${val%\'}" val="${val#\'}"
    # Only export names that are valid shell identifiers
    [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
    export "$key"="$val"
  done < "$file"
}

# ── uv ────────────────────────────────────────────────────────────────────────
echo "-- Check uv"
if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. Install: https://docs.astral.sh/uv/getting-started/installation/" >&2
  exit 1
fi
actions+=("uv found")

# ── rtk ───────────────────────────────────────────────────────────────────────
echo "-- Check rtk (token optimizer)"
if command -v rtk >/dev/null 2>&1; then
  actions+=("rtk already installed")
else
  RTK_VERSION="v0.40.0"
  case "$(uname -s)-$(uname -m)" in
    Linux-x86_64) _rtk_asset="rtk-x86_64-unknown-linux-musl.tar.gz" ;;
    Linux-aarch64|Linux-arm64) _rtk_asset="rtk-aarch64-unknown-linux-gnu.tar.gz" ;;
    Darwin-x86_64) _rtk_asset="rtk-x86_64-apple-darwin.tar.gz" ;;
    Darwin-arm64) _rtk_asset="rtk-aarch64-apple-darwin.tar.gz" ;;
    *) echo "  Unsupported rtk platform: $(uname -s)-$(uname -m)" >&2; _rtk_asset="" ;;
  esac

  _rtk_ok=false
  if [[ -n "${_rtk_asset}" ]]; then
    _rtk_tmp="$(mktemp -d)"
    trap 'rm -rf "${_rtk_tmp:-}"' EXIT
    _rtk_base="https://github.com/rtk-ai/rtk/releases/download/${RTK_VERSION}"
    _rtk_archive="${_rtk_tmp}/${_rtk_asset}"
    _rtk_checksums="${_rtk_tmp}/checksums.txt"
    if curl -fsSL "${_rtk_base}/${_rtk_asset}" -o "${_rtk_archive}" &&
       curl -fsSL "${_rtk_base}/checksums.txt" -o "${_rtk_checksums}"; then
      _rtk_expected="$(awk -v asset="${_rtk_asset}" '$2 == asset {print $1}' "${_rtk_checksums}")"
      if [[ -z "${_rtk_expected}" ]]; then
        echo "  Missing checksum for ${_rtk_asset} in ${_rtk_base}/checksums.txt." >&2
      else
        if command -v sha256sum >/dev/null 2>&1; then
          _rtk_actual="$(sha256sum "${_rtk_archive}" | awk '{print $1}')"
        else
          _rtk_actual="$(shasum -a 256 "${_rtk_archive}" | awk '{print $1}')"
        fi
        if [[ "${_rtk_actual}" != "${_rtk_expected}" ]]; then
          echo "  rtk checksum mismatch for ${_rtk_asset}." >&2
          echo "  expected: ${_rtk_expected}" >&2
          echo "  actual:   ${_rtk_actual}" >&2
        else
          mkdir -p "${HOME}/.local/bin" "${_rtk_tmp}/extract"
          tar -xzf "${_rtk_archive}" -C "${_rtk_tmp}/extract"
          _rtk_bin="$(find "${_rtk_tmp}/extract" -type f -name rtk | head -1)"
          if [[ -z "${_rtk_bin}" ]]; then
            echo "  rtk binary not found in ${_rtk_asset}." >&2
          else
            cp "${_rtk_bin}" "${HOME}/.local/bin/rtk"
            chmod 755 "${HOME}/.local/bin/rtk"
            _rtk_ok=true
          fi
        fi
      fi
    fi
    rm -rf "${_rtk_tmp}"
    trap - EXIT
  fi
  if ${_rtk_ok}; then
    export PATH="$HOME/.local/bin:$PATH"
    if command -v rtk >/dev/null 2>&1; then
      actions+=("rtk installed — ensure ~/.local/bin is in your PATH")
    else
      echo "  rtk installed but not on PATH. Add: export PATH=\"\$HOME/.local/bin:\$PATH\"" >&2
      actions+=("rtk installed (restart shell or update PATH)")
    fi
  else
    echo "  rtk install failed — install manually: https://github.com/rtk-ai/rtk" >&2
    actions+=("rtk not installed (optional)")
  fi
fi
if command -v rtk >/dev/null 2>&1; then
  rtk init -g
  rtk init -g --codex
  actions+=("rtk init -g completed")
fi

# ── Fabric CLI ────────────────────────────────────────────────────────────────
echo "-- Check Microsoft Fabric CLI"
if "${SCRIPT_DIR}/fab-sandbox" --version >/dev/null 2>&1; then
  actions+=("ms-fabric-cli already available")
else
  uv tool install ms-fabric-cli
  actions+=("ms-fabric-cli installed")
fi

# ── Project Python environment ────────────────────────────────────────────────
echo ""
echo "-- Project Python environment (.venv)"
if [[ ! -d "${VENV_DIR}" ]]; then
  uv venv "${VENV_DIR}"
  uv pip install --python "${VENV_PY}" "Faker>=26" "mimesis>=18" "scikit-learn>=1.5" "semantic-link>=0.9" "pandas>=2"
  actions+=(".venv created")
  actions+=("Python helper libraries installed in .venv")
else
  actions+=(".venv already exists")
  actions+=("Python helper libraries: skipped because .venv already exists")
fi

# ── Load existing .env ────────────────────────────────────────────────────────
if [[ -f "$ENV_FILE" ]]; then
  _load_dot_env "$ENV_FILE"
fi

# ── Credentials ───────────────────────────────────────────────────────────────
echo ""
echo "-- Credentials"

if [[ -n "${FABRIC_TENANT_ID:-}" ]]; then
  echo "  FABRIC_TENANT_ID already set — skipping"
else
  read -rp "  FABRIC_TENANT_ID (Azure tenant GUID): " tenant_id
  [[ -z "$tenant_id" ]] && { echo "FABRIC_TENANT_ID is required." >&2; exit 1; }
  write_env_key "FABRIC_TENANT_ID" "$tenant_id"
  export FABRIC_TENANT_ID="$tenant_id"
  actions+=("FABRIC_TENANT_ID written to .env")
fi

if [[ -n "${FABRIC_CLIENT_ID:-}" ]]; then
  echo "  FABRIC_CLIENT_ID already set — skipping"
else
  read -rp "  FABRIC_CLIENT_ID (service principal app/client GUID): " client_id
  [[ -z "$client_id" ]] && { echo "FABRIC_CLIENT_ID is required." >&2; exit 1; }
  write_env_key "FABRIC_CLIENT_ID" "$client_id"
  export FABRIC_CLIENT_ID="$client_id"
  actions+=("FABRIC_CLIENT_ID written to .env")
fi

if [[ -n "${FABRIC_CLIENT_SECRET:-}" ]]; then
  echo "  FABRIC_CLIENT_SECRET already in OS environment — skipping"
else
  read -rsp "  FABRIC_CLIENT_SECRET (input hidden; persisted to shell profile, not .env): " client_secret
  echo
  [[ -z "$client_secret" ]] && { echo "FABRIC_CLIENT_SECRET is required." >&2; exit 1; }
  export FABRIC_CLIENT_SECRET="$client_secret"
  persist_secret "FABRIC_CLIENT_SECRET" "$client_secret"
  actions+=("FABRIC_CLIENT_SECRET persisted to shell profile (chmod 600)")
fi

# ── Authenticate ───────────────────────────────────────────────────────────────
echo ""
echo "-- Authenticate"
if ! "${SCRIPT_DIR}/fab-sandbox" api workspaces --output_format json >/dev/null 2>&1; then
  echo "Authentication failed. Verify FABRIC_TENANT_ID, FABRIC_CLIENT_ID, and FABRIC_CLIENT_SECRET." >&2
  exit 1
fi
actions+=("SPN auth verified")

# Workspace registry is the only source for workspace/resource IDs.
echo ""
echo "-- Workspace registry"
"${VENV_PY}" "${PROJECT_ROOT}/tool/workspace/init.py"
actions+=("workspaces.json refreshed from Fabric API")

if "${VENV_PY}" - <<'PY'
import json
from pathlib import Path

registry = json.loads(Path("workspaces.json").read_text(encoding="utf-8"))
active = registry.get("active")
if active:
    print(f"  Active workspace: {active}")
else:
    print("  No active workspace set. Run: python tool/workspace/switch.py list")
    print("  Then run: python tool/workspace/switch.py <displayName>")
PY
then
  actions+=("workspace registry checked")
else
  echo "Could not read workspaces.json after refresh." >&2
fi

echo ""
echo "Setup complete."
for a in "${actions[@]}"; do echo "- $a"; done
