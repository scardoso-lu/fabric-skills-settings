#!/usr/bin/env bash
# smoke-test.sh — build, deploy, run, and monitor a single Fabric notebook.
# Run from the repository root. Never target production.
#
# Requires: python (>=3.10), fab authenticated (fab auth login), FABRIC_WORKSPACE_ID in .env

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
DEPLOY_ONLY=false

usage() {
  cat <<'USAGE'
Usage:
  bin/notebook/smoke-test.sh --notebook <name> [--deploy-only]

Options:
  --notebook     Name of workspace/<name>.py to build, deploy, run, and monitor.
  --deploy-only  Build and deploy but skip the run+monitor step.

Preconditions:
  - Run from the repository root.
  - Notebook source exists at workspace/<name>.py.
  - fab is authenticated (run: fab auth login).
  - FABRIC_WORKSPACE_ID is set in .env.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --notebook) NOTEBOOK_NAME="$2"; shift 2 ;;
    --deploy-only) DEPLOY_ONLY=true; shift ;;
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

NOTEBOOK_SRC="${PROJECT_ROOT}/workspace/${NOTEBOOK_NAME}.py"
if [[ ! -f "$NOTEBOOK_SRC" ]]; then
  echo "Notebook source not found: workspace/${NOTEBOOK_NAME}.py" >&2; exit 1
fi

echo "-- Build notebook packages"
"$PYTHON_BIN" "${PROJECT_ROOT}/bin/notebook/build.py"

NOTEBOOK_PKG="${PROJECT_ROOT}/fabric_notebooks/${NOTEBOOK_NAME}.Notebook"
if [[ ! -d "$NOTEBOOK_PKG" ]]; then
  echo "Built package not found: fabric_notebooks/${NOTEBOOK_NAME}.Notebook" >&2; exit 1
fi

DEPLOY_CMD=deploy
if [[ "$DEPLOY_ONLY" == false ]]; then
  DEPLOY_CMD=run
fi

"$PYTHON_BIN" "${PROJECT_ROOT}/bin/notebook/deploy.py" "$DEPLOY_CMD" "$NOTEBOOK_NAME" "$WORKSPACE_ID"
