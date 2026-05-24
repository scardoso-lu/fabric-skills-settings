#!/usr/bin/env bash
# setup.sh — source-package sanity setup for Fabric Agent Pack maintainers.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_TOOLS=false

for arg in "$@"; do
  case "$arg" in
    --install-tools) INSTALL_TOOLS=true ;;
    --help|-h)
      cat <<'USAGE'
Usage: ./setup.sh [--install-tools]

Checks this source package and optionally installs developer tools. To install
agent profiles into a Fabric project repository, use bin/install-fabric-agent.
USAGE
      exit 0
      ;;
    *) echo "Unknown option: $arg" >&2; exit 1 ;;
  esac
done

log_step() { printf '\n── %s ──────────────────────────────────────\n' "$*"; }
log_ok() { printf '✓ %s\n' "$*"; }
log_warn() { printf '⚠ %s\n' "$*"; }

log_step "Source package directories"
for dir in profiles/codex profiles/claude profiles/shared rules bin memory; do
  if [[ -d "${SCRIPT_DIR}/${dir}" ]]; then
    log_ok "${dir}/"
  else
    log_warn "missing ${dir}/"
  fi
done

log_step "Tool checks"
check_tool() {
  local name="$1" cmd="$2" hint="$3"
  if command -v "$cmd" >/dev/null 2>&1; then
    log_ok "$name: found"
  else
    log_warn "$name: not found — $hint"
    return 1
  fi
}

check_tool "Git" git "install Git" || true
if ! check_tool "uv" uv "optional: install from https://astral.sh/uv" && [[ "$INSTALL_TOOLS" == "true" ]]; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  log_ok "uv installed"
fi

log_step "Executable scripts"
for script in "${SCRIPT_DIR}/bin/"*; do
  if [[ -f "$script" && ! -x "$script" ]]; then
    chmod +x "$script"
    log_ok "chmod +x bin/$(basename "$script")"
  fi
done

log_step "Validation"
uv run "${SCRIPT_DIR}/bin/validate-install-package.py"
uv run "${SCRIPT_DIR}/bin/validate-agent-guidance.py"

cat <<'NEXT'

Next step: install profiles into a target git repository, then run agents there:
  ./bin/install-fabric-agent --profile all --target /path/to/project --dry-run
  ./bin/install-fabric-agent --profile all --target /path/to/project
NEXT
