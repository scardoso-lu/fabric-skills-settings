#!/usr/bin/env bash
# smoke-test-sandbox.sh — Run the sandbox smoke test sequence end-to-end.
#
# Automates docs/fabric-sandbox-smoke-test.md steps 2-6.
# Step 1 (create local notebook) and step 7 (PII review) remain human-run.
#
# Usage:
#   bin/smoke-test-sandbox.sh --notebook <name> [--workspace <workspace.Workspace>]
#   bin/smoke-test-sandbox.sh --help

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

log_ok()   { echo "✓ $*"; }
log_warn() { echo "⚠ $*"; }
log_info() { echo "  $*"; }
log_step() { echo ""; echo "── $* ──────────────────────────────────────"; }
log_err()  { echo "✗ $*" >&2; }

NOTEBOOK_NAME=""
WORKSPACE_PATH=""

# ── Argument parsing ───────────────────────────────────────────────────────

for arg in "$@"; do
    case $arg in
        --notebook)   shift; NOTEBOOK_NAME="${1:-}" ;;
        --workspace)  shift; WORKSPACE_PATH="${1:-}" ;;
        --help|-h)
            cat <<'USAGE'
Usage:
  bin/smoke-test-sandbox.sh --notebook <name> [--workspace <workspace.Workspace>]

Options:
  --notebook   Name of the notebook (without extension) under src/notebooks/
  --workspace  Fabric workspace path, e.g. "MySandbox.Workspace"
               Falls back to FABRIC_WORKSPACE_PATH in .env

Steps automated:
  2. Build notebooks via build_fabric_notebooks.py
  3. Deploy to sandbox workspace via fab-sandbox
  4. Run the notebook
  5. Capture the run ID
  6. Monitor via nbmon-sandbox

Steps that remain human-run:
  1. Create a local notebook under src/notebooks/ with synthetic data
  7. Review notebook output for PII or credentials

USAGE
            exit 0
            ;;
    esac
done

# ── Guards ─────────────────────────────────────────────────────────────────

if [[ -z "${NOTEBOOK_NAME}" ]]; then
    log_err "--notebook <name> is required"
    echo "Run 'bin/smoke-test-sandbox.sh --help' for usage." >&2
    exit 2
fi

# Safety: refuse to run against production
if [[ "${FABRIC_ENV:-sandbox}" == "production" ]]; then
    log_err "FABRIC_ENV=production — this script targets sandbox only. Aborting."
    exit 1
fi

# Load .env if present (never export real IDs; read only what's needed)
ENV_FILE="${ROOT_DIR}/.env"
if [[ -f "${ENV_FILE}" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "${ENV_FILE}"
    set +a
fi

# Resolve workspace path: flag > .env > error
if [[ -z "${WORKSPACE_PATH}" ]]; then
    WORKSPACE_PATH="${FABRIC_WORKSPACE_PATH:-}"
fi
if [[ -z "${WORKSPACE_PATH}" ]]; then
    log_err "Workspace path not set. Use --workspace or set FABRIC_WORKSPACE_PATH in .env"
    exit 2
fi

NOTEBOOK_ITEM_PATH="${WORKSPACE_PATH}/${NOTEBOOK_NAME}.Notebook"

# Check that a local notebook source file exists
NOTEBOOK_SRC="${ROOT_DIR}/src/notebooks/${NOTEBOOK_NAME}.py"
if [[ ! -f "${NOTEBOOK_SRC}" ]]; then
    log_err "Source file not found: src/notebooks/${NOTEBOOK_NAME}.py"
    log_info "Create a local notebook first (step 1 — human-run):"
    log_info "  src/notebooks/${NOTEBOOK_NAME}.py"
    log_info "Then re-run this script."
    exit 2
fi

echo ""
echo "════════════════════════════════════════════"
echo "  Fabric Sandbox Smoke Test"
echo "  Notebook : ${NOTEBOOK_NAME}"
echo "  Workspace: ${WORKSPACE_PATH}"
echo "  ENV      : ${FABRIC_ENV:-sandbox}"
echo "════════════════════════════════════════════"

# ── Step 2: Build notebooks ────────────────────────────────────────────────

log_step "Step 2 — Build notebooks"
python3 "${SCRIPT_DIR}/build_fabric_notebooks.py"
log_ok "Notebooks built → fabric_notebooks/"

# ── Step 3: Deploy to sandbox workspace ───────────────────────────────────

log_step "Step 3 — Deploy to sandbox workspace"
NOTEBOOK_PKG="${ROOT_DIR}/fabric_notebooks/${NOTEBOOK_NAME}.Notebook"
if [[ ! -d "${NOTEBOOK_PKG}" ]]; then
    log_err "Built notebook package not found: fabric_notebooks/${NOTEBOOK_NAME}.Notebook"
    log_info "Check build_fabric_notebooks.py output above."
    exit 1
fi

"${SCRIPT_DIR}/fab-sandbox" import --workspace-path "${WORKSPACE_PATH}" \
    --item "${NOTEBOOK_PKG}"
log_ok "Deployed: ${NOTEBOOK_NAME}.Notebook → ${WORKSPACE_PATH}"

# ── Step 4 + 5: Run notebook and capture run ID ────────────────────────────

log_step "Step 4+5 — Run notebook and capture run ID"
RUN_OUTPUT="$("${SCRIPT_DIR}/fab-sandbox" job run "${NOTEBOOK_ITEM_PATH}" 2>&1)"
echo "${RUN_OUTPUT}"

RUN_ID="$(python3 - <<'PYEOF'
import sys, json, re

data = sys.stdin.read()
# Try JSON first
try:
    obj = json.loads(data)
    for key in ("runId", "run_id", "id"):
        if key in obj:
            print(obj[key])
            sys.exit(0)
except Exception:
    pass
# Fallback: extract UUID-like token labelled runId
m = re.search(r'(?:runId|run_id)["\s:=]+([a-f0-9\-]{36})', data, re.IGNORECASE)
if m:
    print(m.group(1))
    sys.exit(0)
sys.exit(1)
PYEOF
<<< "${RUN_OUTPUT}" || true)"

if [[ -z "${RUN_ID}" ]]; then
    log_warn "Could not parse run ID from fab output automatically."
    log_info "Paste the run ID shown above, then press Enter:"
    read -r RUN_ID
fi

log_ok "Run ID: ${RUN_ID}"

# ── Step 6: Monitor ────────────────────────────────────────────────────────

log_step "Step 6 — Monitor run via nbmon-sandbox"
"${SCRIPT_DIR}/nbmon-sandbox" status "${NOTEBOOK_ITEM_PATH}" "${RUN_ID}"

# ── Summary ────────────────────────────────────────────────────────────────

echo ""
echo "════════════════════════════════════════════"
log_ok "Smoke test sequence complete."
echo ""
log_info "Step 7 (human-run): Review the notebook output above for PII, credentials,"
log_info "  or real source data before treating this run as a pass."
echo ""
log_info "Record results in memory:"
log_info "  python3 bin/post-smoke-update.py --notebook '${NOTEBOOK_NAME}' --run-id '${RUN_ID}'"
echo ""
