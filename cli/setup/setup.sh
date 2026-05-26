#!/usr/bin/env bash
# setup.sh — idempotent local setup for a Fabric agent target repo.
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
#   5. Prompts for FABRIC_CLIENT_SECRET and persists to the user's shell
#      profile (NOT .env — secrets stay in the OS env).
#   6. Prompts for FABRIC_SERVER_URL and writes it to .env.
#   7. Prompts for the MCP server URL, writes .mcp.json, and patches
#      .codex/config.toml's [mcp_servers.fabric-server] url (if installed).
#   8. Verifies SPN auth by calling `fab api workspaces`.
#   9. Runs tool/workspace/init.py to populate workspaces.json.
#  10. Prompts to select the active workspace.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
ENV_FILE="${PROJECT_ROOT}/.env"

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
  chmod 600 "$profile"
  echo "  Persisted to ${profile} (chmod 600) — reopen terminals to pick it up."
}

_load_dot_env() {
  local file="$1" line key val
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%%#*}"
    line="${line#"${line%%[![:space:]]*}"}"
    line="${line%"${line##*[![:space:]]}"}"
    [[ -z "$line" || "$line" != *"="* ]] && continue
    key="${line%%=*}"
    val="${line#*=}"
    val="${val%\"}" val="${val#\"}"
    val="${val%\'}" val="${val#\'}"
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

# ── rtk (token optimizer) ─────────────────────────────────────────────────────
echo "-- Check rtk (token optimizer)"
if command -v rtk >/dev/null 2>&1; then
  actions+=("rtk already installed")
else
  RTK_VERSION="v0.40.0"
  case "$(uname -s)-$(uname -m)" in
    Linux-x86_64)             _rtk_asset="rtk-x86_64-unknown-linux-musl.tar.gz" ;;
    Linux-aarch64|Linux-arm64) _rtk_asset="rtk-aarch64-unknown-linux-gnu.tar.gz" ;;
    Darwin-x86_64)            _rtk_asset="rtk-x86_64-apple-darwin.tar.gz" ;;
    Darwin-arm64)             _rtk_asset="rtk-aarch64-apple-darwin.tar.gz" ;;
    *) echo "  Unsupported rtk platform: $(uname -s)-$(uname -m)" >&2; _rtk_asset="" ;;
  esac

  _rtk_ok=false
  if [[ -n "${_rtk_asset}" ]]; then
    _rtk_tmp="$(mktemp -d)"
    trap 'rm -rf "${_rtk_tmp:-}"' EXIT
    _rtk_base="https://github.com/rtk-ai/rtk/releases/download/${RTK_VERSION}"
    if curl -fsSL "${_rtk_base}/${_rtk_asset}" -o "${_rtk_tmp}/${_rtk_asset}" &&
       curl -fsSL "${_rtk_base}/checksums.txt" -o "${_rtk_tmp}/checksums.txt"; then
      _rtk_expected="$(awk -v asset="${_rtk_asset}" '$2 == asset {print $1}' "${_rtk_tmp}/checksums.txt")"
      if [[ -n "${_rtk_expected}" ]]; then
        if command -v sha256sum >/dev/null 2>&1; then
          _rtk_actual="$(sha256sum "${_rtk_tmp}/${_rtk_asset}" | awk '{print $1}')"
        else
          _rtk_actual="$(shasum -a 256 "${_rtk_tmp}/${_rtk_asset}" | awk '{print $1}')"
        fi
        if [[ "${_rtk_actual}" == "${_rtk_expected}" ]]; then
          mkdir -p "${HOME}/.local/bin" "${_rtk_tmp}/extract"
          tar -xzf "${_rtk_tmp}/${_rtk_asset}" -C "${_rtk_tmp}/extract"
          _rtk_bin="$(find "${_rtk_tmp}/extract" -type f -name rtk | head -1)"
          if [[ -n "${_rtk_bin}" ]]; then
            cp "${_rtk_bin}" "${HOME}/.local/bin/rtk"
            chmod 755 "${HOME}/.local/bin/rtk"
            _rtk_ok=true
          fi
        else
          echo "  rtk checksum mismatch — refusing to install." >&2
        fi
      fi
    fi
    rm -rf "${_rtk_tmp}"
    trap - EXIT
  fi
  if ${_rtk_ok}; then
    export PATH="$HOME/.local/bin:$PATH"
    actions+=("rtk installed — ensure ~/.local/bin is in your PATH")
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

# ── Microsoft Fabric CLI ──────────────────────────────────────────────────────
echo ""
echo "-- Check Microsoft Fabric CLI"
if command -v fab >/dev/null 2>&1 && fab --version >/dev/null 2>&1; then
  actions+=("ms-fabric-cli already available")
else
  uv tool install ms-fabric-cli
  actions+=("ms-fabric-cli installed (run 'uv tool update-shell' if 'fab' is not on PATH)")
fi

# ── Load existing .env ────────────────────────────────────────────────────────
[[ -f "$ENV_FILE" ]] && _load_dot_env "$ENV_FILE"

# ── Service-principal credentials ─────────────────────────────────────────────
echo ""
echo "-- Service-principal credentials"

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

# Map FABRIC_* → AZURE_* for child processes that call `fab` (Azure Identity
# reads AZURE_* for service-principal auth). Process-local — not persisted.
export AZURE_TENANT_ID="${FABRIC_TENANT_ID}"
export AZURE_CLIENT_ID="${FABRIC_CLIENT_ID}"
export AZURE_CLIENT_SECRET="${FABRIC_CLIENT_SECRET}"

# ── MCP server URL ────────────────────────────────────────────────────────────
echo ""
echo "-- Fabric MCP server URL"
if [[ -n "${FABRIC_SERVER_URL:-}" ]]; then
  echo "  FABRIC_SERVER_URL already set — keeping ${FABRIC_SERVER_URL}"
else
  read -rp "  FABRIC_SERVER_URL [http://127.0.0.1:8000]: " server_url
  server_url="${server_url:-http://127.0.0.1:8000}"
  write_env_key "FABRIC_SERVER_URL" "$server_url"
  export FABRIC_SERVER_URL="$server_url"
  actions+=("FABRIC_SERVER_URL written to .env (${server_url})")
fi

# ── MCP client config (.mcp.json) ───────────────────────────────────────────────
# Claude/Codex read .mcp.json to reach the fabric-server MCP. Write it with a
# concrete URL here (the installer no longer ships a template). The endpoint
# defaults to <FABRIC_SERVER_URL>/mcp but can be overridden.
echo ""
echo "-- MCP server endpoint (.mcp.json)"
MCP_JSON="${PROJECT_ROOT}/.mcp.json"
default_mcp_url="${FABRIC_SERVER_URL%/}/mcp"
read -rp "  MCP server URL [${default_mcp_url}]: " mcp_url
mcp_url="${mcp_url:-$default_mcp_url}"
cat > "$MCP_JSON" <<EOF
{
  "mcpServers": {
    "fabric-server": {
      "type": "http",
      "url": "${mcp_url}"
    }
  }
}
EOF
actions+=(".mcp.json written (${mcp_url})")

# Codex reads .codex/config.toml (not .mcp.json). Patch its
# [mcp_servers.fabric-server] url to the same endpoint, if that profile is
# installed. The file ships with a default url; we rewrite just that line.
CODEX_CONFIG="${PROJECT_ROOT}/.codex/config.toml"
if [[ -f "$CODEX_CONFIG" ]]; then
  _codex_tmp="$(mktemp)"
  awk -v url="$mcp_url" '
    /^\[mcp_servers\.fabric-server\]/ { print; in_section=1; next }
    /^\[/                             { in_section=0 }
    in_section && /^[[:space:]]*url[[:space:]]*=/ { print "url = \"" url "\""; next }
    { print }
  ' "$CODEX_CONFIG" > "$_codex_tmp" && mv "$_codex_tmp" "$CODEX_CONFIG"
  actions+=(".codex/config.toml MCP url set (${mcp_url})")
fi

# ── Authenticate ──────────────────────────────────────────────────────────────
# Use explicit SPN login. fab does NOT pick up AZURE_* env vars implicitly —
# the login subcommand populates fab's own credential cache.
echo ""
echo "-- Authenticate"
if ! fab auth login \
    -u "$FABRIC_CLIENT_ID" \
    -p "$FABRIC_CLIENT_SECRET" \
    --tenant "$FABRIC_TENANT_ID"; then
  echo "" >&2
  echo "fab auth login flags (run 'fab auth login --help' for the current signature):" >&2
  fab auth login --help >&2 || true
  echo "fab auth login failed. Verify FABRIC_TENANT_ID / FABRIC_CLIENT_ID / FABRIC_CLIENT_SECRET are correct and that the service principal has Contributor on at least one Fabric workspace." >&2
  exit 1
fi
if ! fab api workspaces --output_format json; then
  echo "fab api workspaces failed after login. The SPN may not have access to any workspace yet." >&2
  exit 1
fi
actions+=("SPN auth verified via fab auth login + fab api workspaces")

# ── Workspace registry ────────────────────────────────────────────────────────
echo ""
echo "-- Workspace registry"
WORKSPACE_INIT="${PROJECT_ROOT}/tool/workspace/init.py"
if [[ ! -f "$WORKSPACE_INIT" ]]; then
  echo "tool/workspace/init.py not found. The installer must run before setup.sh (which installs cli/tools/ into <target>/tool/)." >&2
  exit 1
fi
(cd "$PROJECT_ROOT" && python "$WORKSPACE_INIT")
actions+=("workspaces.json refreshed from Fabric API")

# ── Active workspace selection ────────────────────────────────────────────────
# Run pick.py as a sibling script so its stdin stays attached to the parent
# terminal — interactive prompts only work when stdin is a real TTY.
WORKSPACE_PICK="${PROJECT_ROOT}/tool/workspace/pick.py"
if [[ -f "$WORKSPACE_PICK" ]]; then
  if (cd "$PROJECT_ROOT" && python "$WORKSPACE_PICK"); then
    actions+=("active workspace selected and resource IDs written to .env")
  else
    echo "  Workspace selection skipped or failed; set it later with python tool/workspace/switch.py." >&2
    actions+=("active workspace not set (re-run python tool/workspace/switch.py)")
  fi
else
  echo "  tool/workspace/pick.py not found; set the active workspace later with python tool/workspace/switch.py." >&2
  actions+=("active workspace not set (re-run python tool/workspace/switch.py)")
fi

echo ""
echo "Setup complete."
for a in "${actions[@]}"; do echo "- $a"; done
echo ""
echo "Next: start the Fabric MCP server."
echo "  cd <fabric-skills-settings>/server"
echo "  docker compose up --build"
echo "Then open Claude Code (or Codex) in this project."
