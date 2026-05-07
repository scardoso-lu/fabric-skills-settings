#!/usr/bin/env bash
# pre-commit-check.sh — run local validators before committing profile/installer changes.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log_step() { echo ""; echo "── $* ──────────────────────────────────────"; }
log_ok() { echo "✓ $*"; }
log_err() { echo "✗ $*" >&2; }

FAILED=false

log_step "Install package validation"
if python3 "${SCRIPT_DIR}/validate-install-package.py"; then
  log_ok "validate-install-package.py passed"
else
  log_err "validate-install-package.py failed"
  FAILED=true
fi

log_step "Agent guidance validation"
if python3 "${SCRIPT_DIR}/validate-agent-guidance.py"; then
  log_ok "validate-agent-guidance.py passed"
else
  log_err "validate-agent-guidance.py failed"
  FAILED=true
fi

echo ""
echo "════════════════════════════════════════════"
if [[ "$FAILED" == "true" ]]; then
  log_err "Pre-commit checks failed"
  exit 1
fi
log_ok "All pre-commit checks passed"
