#!/usr/bin/env bash
# smoke-test-sandbox.sh — human-run sandbox Fabric notebook smoke helper.
# Run from an installed target repository. Never target production.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${PROJECT_ROOT}/.env"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

NOTEBOOK_NAME=""
WORKSPACE_PATH="${FABRIC_WORKSPACE_PATH:-}"

usage() {
  cat <<'USAGE'
Usage: bin/smoke-test-sandbox.sh --notebook <name> [--workspace-path <Workspace.Name>]

Preconditions:
  - Run from the target repository root after profile installation.
  - Notebook source exists at workspace/<name>.py.
  - fab is authenticated and points to a sandbox workspace.
  - FABRIC_WORKSPACE_PATH is set in .env or passed as --workspace-path.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --notebook) NOTEBOOK_NAME="$2"; shift 2 ;;
    --workspace-path) WORKSPACE_PATH="$2"; shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
done

if [[ -z "$NOTEBOOK_NAME" ]]; then
  echo "Missing --notebook" >&2
  usage
  exit 1
fi
if [[ -z "$WORKSPACE_PATH" ]]; then
  echo "Missing workspace path. Set FABRIC_WORKSPACE_PATH in .env or pass --workspace-path." >&2
  exit 1
fi

NOTEBOOK_SRC="${PROJECT_ROOT}/src/notebooks/${NOTEBOOK_NAME}.py"
NOTEBOOK_PKG="${PROJECT_ROOT}/fabric_notebooks/${NOTEBOOK_NAME}.Notebook"
NOTEBOOK_ITEM_PATH="${WORKSPACE_PATH}/${NOTEBOOK_NAME}.Notebook"

if [[ ! -f "$NOTEBOOK_SRC" ]]; then
  echo "Notebook source not found: src/notebooks/${NOTEBOOK_NAME}.py" >&2
  exit 1
fi

echo "── Build notebook packages"
uv run "${PROJECT_ROOT}/bin/build_fabric_notebooks.py"

if [[ ! -d "$NOTEBOOK_PKG" ]]; then
  echo "Built notebook package not found: fabric_notebooks/${NOTEBOOK_NAME}.Notebook" >&2
  exit 1
fi

echo "── Import notebook to sandbox workspace"
"${SCRIPT_DIR}/fab-sandbox" import --workspace-path "$WORKSPACE_PATH" "$NOTEBOOK_PKG"

echo "── Run notebook"
RUN_OUTPUT="$("${SCRIPT_DIR}/fab-sandbox" job run "$NOTEBOOK_ITEM_PATH" 2>&1)"
printf '%s\n' "$RUN_OUTPUT"
RUN_ID="$(printf '%s\n' "$RUN_OUTPUT" | grep -oE '[0-9a-fA-F-]{36}' | tail -1 || true)"

if [[ -z "$RUN_ID" ]]; then
  echo "Could not parse run ID from fab output. Inspect output above." >&2
  exit 1
fi

echo "── Monitor run"
"${SCRIPT_DIR}/nbmon-sandbox" status "$NOTEBOOK_ITEM_PATH" "$RUN_ID"

echo "Smoke helper completed for run: $RUN_ID"
