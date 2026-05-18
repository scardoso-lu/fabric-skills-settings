#!/usr/bin/env bash
# smoke-test.sh — trigger and monitor a Fabric notebook job without deploying.
# The notebook must already be deployed in the workspace.
# Run from the repository root. Never targets production.
#
# Requires: python (>=3.10), fab authenticated (tool/setup/fab-sandbox auth login), FABRIC_WORKSPACE_ID in .env

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
ENV_FILE="${PROJECT_ROOT}/.env"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python)"
  else
    echo "python3 or python is required." >&2
    exit 127
  fi
fi

NOTEBOOK_NAME=""
WORKSPACE_ID="${FABRIC_WORKSPACE_ID:-}"

usage() {
  cat <<'USAGE'
Usage:
  tool/notebook/smoke-test.sh --notebook <name>

Options:
  --notebook     Stem name of the notebook (e.g. bronze_electricity_day_ahead_prices).
                 The notebook must already be deployed in the Fabric workspace.

Preconditions:
  - Run from the repository root.
  - The notebook is already deployed (run: python tool/notebook/deploy.py deploy <name> <workspace_id>).
  - fab is authenticated (run: tool/setup/fab-sandbox auth login).
  - FABRIC_WORKSPACE_ID is set in .env.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --notebook) NOTEBOOK_NAME="$2"; shift 2 ;;
    --workspace-id) WORKSPACE_ID="$2"; shift 2 ;;  # kept for backwards compat; prefer .env
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
done

if [[ -z "$NOTEBOOK_NAME" ]]; then
  echo "Missing --notebook" >&2; usage; exit 1
fi
if [[ -z "$WORKSPACE_ID" ]]; then
  echo "Missing workspace id. Set FABRIC_WORKSPACE_ID in .env." >&2; exit 1
fi

"$PYTHON_BIN" "${PROJECT_ROOT}/tool/notebook/deploy.py" exec "$NOTEBOOK_NAME" "$WORKSPACE_ID"
