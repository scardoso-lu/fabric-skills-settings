#!/usr/bin/env bash
# pre-commit-check.sh — run pre-commit validations in a Fabric project workspace.
# Run from the repository root before committing workspace changes.

set -euo pipefail

PROJECT_ROOT="$(cd "${FABRIC_TARGET_ROOT:-$PWD}" && pwd)"

log_step() { echo ""; echo "── $* ──────────────────────────────────────"; }
log_ok()   { echo "✓ $*"; }
log_err()  { echo "✗ $*" >&2; }

FAILED=false

log_step "Deterministic lints (tool/lint/)"
if (cd "$PROJECT_ROOT" && fabric-cli lint --target "$PROJECT_ROOT"); then
  log_ok "lints passed"
else
  log_err "lints failed"
  FAILED=true
fi

echo ""
echo "════════════════════════════════════════════"
if [[ "$FAILED" == "true" ]]; then
  log_err "Pre-commit checks failed"
  exit 1
fi
log_ok "All pre-commit checks passed"
echo ""
echo "Note: pipeline staging-path consistency is checked via the"
echo "      pipeline_lineage_check MCP tool — call it from your agent"
echo "      after changing staging-path constants."
