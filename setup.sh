#!/usr/bin/env bash
# setup.sh — single-shot CLI for the Fabric Agent Pack source clone.
#
#   Maintainer sanity check (no args):
#       ./setup.sh
#
#   Install a profile into a target repo (one command):
#       ./setup.sh --profile claude --target /path/to/project
#       ./setup.sh --profile all    --target /path/to/project --dry-run
#       ./setup.sh --profile claude --target /path/to/project --check
#       ./setup.sh --profile claude --target /path/to/project --force --backup
#
# After `pip install fabric-skills-settings`, the wheel installs the same
# command as `install-fabric-agent --profile claude --target /path/to/project`.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PROFILE=""
TARGET=""
PASSTHROUGH=()
INSTALL_TOOLS=false
SKIP_VALIDATORS=false

show_usage() {
  cat <<'USAGE'
fabric-skills-settings — single-shot setup CLI

Usage:
  ./setup.sh                                              maintainer sanity check (no install)
  ./setup.sh --profile <codex|claude|all> --target <path> install profile into target repo
  ./setup.sh --profile claude --target /path --dry-run    preview without writing
  ./setup.sh --profile claude --target /path --check      verify target state, exit 1 on diff
  ./setup.sh --profile claude --target /path --force      overwrite non-managed files
  ./setup.sh --profile claude --target /path --backup     back up replaced files

Switches:
  --no-bootstrap      skip the post-install target bootstrap (.venv, deps, Fabric auth prompts,
                      workspaces.json). Bootstrap runs by default unless --dry-run or --check is set.
  --skip-validators   skip the pre-install validator pass (validators run by default)
  --install-tools     auto-install uv if missing
  --help, -h          show this message

After `pip install fabric-skills-settings`, the same install runs as:
  install-fabric-agent --profile claude --target /path/to/project
USAGE
}

# Parse args (supports both --flag value and --flag=value forms).
while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile)            PROFILE="$2"; shift 2 ;;
    --profile=*)          PROFILE="${1#--profile=}"; shift ;;
    --target)             TARGET="$2"; shift 2 ;;
    --target=*)           TARGET="${1#--target=}"; shift ;;
    --dry-run)            PASSTHROUGH+=("--dry-run"); shift ;;
    --check)              PASSTHROUGH+=("--check"); shift ;;
    --force)              PASSTHROUGH+=("--force"); shift ;;
    --backup)             PASSTHROUGH+=("--backup"); shift ;;
    --self-test)          PASSTHROUGH+=("--self-test"); shift ;;
    --no-bootstrap)       PASSTHROUGH+=("--no-bootstrap"); shift ;;
    --skip-validators)    SKIP_VALIDATORS=true; shift ;;
    --install-tools)      INSTALL_TOOLS=true; shift ;;
    --help|-h)            show_usage; exit 0 ;;
    *)                    echo "Unknown option: $1" >&2; show_usage; exit 1 ;;
  esac
done

log_step() { printf '\n── %s ──────────────────────────────────────\n' "$*"; }
log_ok()   { printf '✓ %s\n' "$*"; }
log_warn() { printf '⚠ %s\n' "$*"; }
log_fail() { printf '✗ %s\n' "$*" >&2; }

check_tool() {
  local name="$1" cmd="$2" hint="$3"
  if command -v "$cmd" >/dev/null 2>&1; then
    log_ok "$name: found"
  else
    log_warn "$name: not found — $hint"
    return 1
  fi
}

run_validators() {
  log_step "Validators"
  uv run "${SCRIPT_DIR}/packaging/validators/validate-install-package.py"
  uv run "${SCRIPT_DIR}/packaging/validators/validate-agent-guidance.py"
}

# ── uv presence ──────────────────────────────────────────────────────────────
log_step "Tool checks"
check_tool "Git" git "install Git from https://git-scm.com" || true
if ! check_tool "uv" uv "install from https://astral.sh/uv"; then
  if [[ "$INSTALL_TOOLS" == "true" ]]; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    log_ok "uv installed"
  else
    log_fail "uv is required. Re-run with --install-tools or install from https://astral.sh/uv"
    exit 1
  fi
fi

# Make the source-clone installer script executable if needed.
if [[ -f "${SCRIPT_DIR}/packaging/install-fabric-agent" && ! -x "${SCRIPT_DIR}/packaging/install-fabric-agent" ]]; then
  chmod +x "${SCRIPT_DIR}/packaging/install-fabric-agent"
fi

# ── No-args path: maintainer sanity check ────────────────────────────────────
if [[ -z "$TARGET" ]]; then
  show_usage
  log_step "Source package directories"
  for dir in profiles/codex profiles/claude profiles/shared content tool mcp packaging; do
    if [[ -d "${SCRIPT_DIR}/${dir}" ]]; then
      log_ok "${dir}/"
    else
      log_warn "missing ${dir}/"
    fi
  done
  [[ "$SKIP_VALIDATORS" == "true" ]] || run_validators
  echo
  echo "Sanity check complete. To install, re-run with --profile and --target."
  exit 0
fi

# ── Install path: validators (optional) then install-fabric-agent ────────────
if [[ -z "$PROFILE" ]]; then
  log_fail "--target was given without --profile. Specify --profile codex|claude|all."
  show_usage
  exit 2
fi

[[ "$SKIP_VALIDATORS" == "true" ]] || run_validators

log_step "Install profile '$PROFILE' into $TARGET"
uv run python "${SCRIPT_DIR}/packaging/install-fabric-agent" \
  --profile "$PROFILE" --target "$TARGET" "${PASSTHROUGH[@]}"

echo
echo "Done. Open $TARGET in Claude Code or Codex and let the agent call graph_get_entry first."
