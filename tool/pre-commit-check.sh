#!/usr/bin/env bash
# pre-commit-check.sh — run pre-commit validations in a Fabric project workspace.
# Run from the repository root before committing workspace changes.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if command -v python3 >/dev/null 2>&1; then PYTHON_BIN="$(command -v python3)"
  elif command -v python >/dev/null 2>&1; then PYTHON_BIN="$(command -v python)"
  else echo "python3 or python is required." >&2; exit 127; fi
fi

log_step() { echo ""; echo "── $* ──────────────────────────────────────"; }
log_ok()   { echo "✓ $*"; }
log_err()  { echo "✗ $*" >&2; }

FAILED=false

log_step "Pipeline staging-path consistency"
if "$PYTHON_BIN" "${SCRIPT_DIR}/validate/pipeline-lineage.py"; then
  log_ok "pipeline-lineage passed"
else
  log_err "pipeline-lineage failed"
  FAILED=true
fi

log_step "Deterministic lints (tool/lint/)"
if "$PYTHON_BIN" -m tool.lint --target "$PROJECT_ROOT"; then
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
