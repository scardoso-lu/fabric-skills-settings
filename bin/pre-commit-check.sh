#!/usr/bin/env bash
# pre-commit-check.sh — run all local validators before committing guidance changes.
#
# Install as a git hook:
#   cp bin/pre-commit-check.sh .git/hooks/pre-commit
#   chmod +x .git/hooks/pre-commit
#
# Or run manually after editing CLAUDE.md, AGENTS.md, .claude/agents/, or skills/:
#   ./bin/pre-commit-check.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

log_step() { echo ""; echo "── $* ──────────────────────────────────────"; }
log_ok()   { echo "✓ $*"; }
log_err()  { echo "✗ $*" >&2; }

FAILED=false

# ── Agent guidance drift check ─────────────────────────────────────────────
log_step "Agent guidance drift check"
if python3 "${SCRIPT_DIR}/validate-agent-guidance.py"; then
    log_ok "validate-agent-guidance.py passed"
else
    log_err "validate-agent-guidance.py failed — fix drift before committing"
    FAILED=true
fi

# ── Source contract validation (templates only) ────────────────────────────
log_step "Source contract template validation"
TEMPLATE_CONTRACT="${ROOT_DIR}/templates/source-contract.yaml"
if [[ -f "$TEMPLATE_CONTRACT" ]]; then
    if python3 "${SCRIPT_DIR}/validate-source-contract.py" \
        --allow-placeholders "$TEMPLATE_CONTRACT" 2>/dev/null; then
        log_ok "source-contract template is valid"
    else
        log_err "templates/source-contract.yaml failed validation"
        FAILED=true
    fi
else
    echo "  templates/source-contract.yaml not found — skipping"
fi

# ── Thresholds config presence ─────────────────────────────────────────────
log_step "Thresholds config"
THRESHOLDS="${ROOT_DIR}/config/thresholds.yaml"
if [[ -f "$THRESHOLDS" ]]; then
    log_ok "config/thresholds.yaml present"
else
    log_err "config/thresholds.yaml missing — agents cannot load DQ thresholds"
    FAILED=true
fi

echo ""
echo "════════════════════════════════════════════"
if [[ "$FAILED" == "true" ]]; then
    echo "✗ Pre-commit checks failed. Fix the issues above before committing."
    exit 1
else
    echo "✓ All pre-commit checks passed."
fi
