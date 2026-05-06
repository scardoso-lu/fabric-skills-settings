#!/usr/bin/env bash
# setup.sh — Day-one bootstrap for fabric-codex
# Run once when you start working on a new machine or Fabric project.
#
# Usage:
#   ./setup.sh                    Check tools and set up folder structure
#   ./setup.sh --install-tools    Also install missing tools (uv, fab CLI)
#   ./setup.sh --install-skills   Also install recommended external skill packs

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_TOOLS=false
INSTALL_SKILLS=false
RUN_CHECKLIST=false

# Parse flags
for arg in "$@"; do
    case $arg in
        --install-tools)   INSTALL_TOOLS=true ;;
        --install-skills)  INSTALL_SKILLS=true ;;
        --checklist)       RUN_CHECKLIST=true ;;
        --help|-h)
            echo "Usage: setup.sh [--install-tools] [--install-skills] [--checklist]"
            echo ""
            echo "  --install-tools    Install uv, Fabric CLI, and check rtk"
            echo "  --install-skills   Install recommended external skill packs"
            echo "  --checklist        Check installation readiness (run after --install-tools)"
            exit 0
            ;;
    esac
done

log_ok()   { echo "✓ $*"; }
log_warn() { echo "⚠ $*"; }
log_info() { echo "  $*"; }
log_step() { echo ""; echo "── $* ──────────────────────────────────────"; }

# ── Folder Structure ───────────────────────────────────────────────────────

log_step "Folder Structure"

dirs=(
    "src/notebooks"
    "fabric_notebooks"
    "data/sandbox"
    "data/landing"
    "logs"
    "skills/external"
    "memory/runbooks"
    "memory/security"
)

for dir in "${dirs[@]}"; do
    if [[ ! -d "${SCRIPT_DIR}/${dir}" ]]; then
        mkdir -p "${SCRIPT_DIR}/${dir}"
        log_ok "Created: ${dir}/"
    else
        log_info "Exists:  ${dir}/"
    fi
done

# ── Memory Files (local to this clone — never committed) ───────────────────

_init_memory_file() {
    local path="$1" content="$2"
    if [[ ! -f "${SCRIPT_DIR}/${path}" ]]; then
        printf '%s\n' "${content}" > "${SCRIPT_DIR}/${path}"
        log_ok "Created: ${path}"
    else
        log_info "Exists:  ${path}"
    fi
}

_init_memory_file "memory/project.md" \
'# Project State

<!-- Agents: update this file when you complete work, hit a blocker, or change pipeline status -->

## Current Focus

*(not set — update when work begins)*

## Active Pipelines

| Pipeline | Layer | Status | Last Run | Notes |
|---|---|---|---|---|
| *(none yet)* | | | | |

## Known Issues

*(none yet)*

## Completed Work

*(log significant completions here with date)*'

_init_memory_file "memory/platform.md" \
'# Platform Inventory

<!-- Agents: add an entry every time you create or register a Fabric item. Keep this current. -->
<!-- Never write real workspace IDs, lakehouse IDs, or tokens here. -->

## Workspaces

| Name | Type | Purpose | Owner |
|---|---|---|---|
| *(none yet)* | | | |

## Lakehouses

| Name | Workspace | Layer | Created | Notes |
|---|---|---|---|---|
| *(none yet)* | | | | |

## Notebooks

| Name | Workspace | Lakehouse | Schedules | Runbook |
|---|---|---|---|---|
| *(none yet)* | | | | |

## Source Systems

| Name | Type | Env Var Prefix | Cadence | Sensitive Fields |
|---|---|---|---|---|
| *(none yet)* | | | | |

## Source Registration Template

```bash
SRC_<SYSTEM>_TYPE=file
SRC_<SYSTEM>_PATH=./data/sandbox/<filename>.csv
```

Never write real hosts, passwords, tokens, or connection strings to memory.'

_init_memory_file "memory/decisions.md" \
'# Architecture Decisions

<!-- Agents: append when you make a non-obvious design choice future sessions need to know. -->

*(no decisions logged yet)*'

# ── Environment File ───────────────────────────────────────────────────────

log_step "Environment"

if [[ ! -f "${SCRIPT_DIR}/.env" ]]; then
    if [[ -f "${SCRIPT_DIR}/.env.example" ]]; then
        cp "${SCRIPT_DIR}/.env.example" "${SCRIPT_DIR}/.env"
        log_ok "Created .env from .env.example — fill in your values"
    else
        log_warn ".env.example not found — create .env manually"
    fi
else
    log_info ".env already exists"
fi

# ── Tool Checks ────────────────────────────────────────────────────────────

log_step "Tool Checks"

check_tool() {
    local name="$1" cmd="$2" install_hint="$3"
    if command -v "$cmd" &>/dev/null; then
        log_ok "${name}: $(${cmd} --version 2>/dev/null | head -1 || echo 'found')"
    else
        log_warn "${name}: not found — ${install_hint}"
        return 1
    fi
    return 0
}

TOOLS_OK=true

check_tool "Python" "python3" "install from python.org" || TOOLS_OK=false
check_tool "Git" "git" "install from git-scm.com" || TOOLS_OK=false

if check_tool "uv" "uv" "run: curl -LsSf https://astral.sh/uv/install.sh | sh"; then
    :
elif [[ "$INSTALL_TOOLS" == "true" ]]; then
    log_info "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
    log_ok "uv installed"
else
    TOOLS_OK=false
fi

FAB_AVAILABLE=false
if check_tool "Fabric CLI (fab)" "fab" "run: ./setup.sh --install-tools"; then
    FAB_AVAILABLE=true
    # Document the installed version for bin/fab-sandbox minimum-version enforcement
    _fab_ver="$(fab --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || true)"
    if [[ -n "$_fab_ver" ]]; then
        log_info "Tested fab version: ${_fab_ver} (minimum enforced by bin/fab-sandbox: FAB_MIN_VERSION)"
    fi
elif [[ "$INSTALL_TOOLS" == "true" ]]; then
    log_info "Installing Fabric CLI..."
    uv tool install ms-fabric-cli
    log_ok "Fabric CLI installed"
    FAB_AVAILABLE=true
else
    log_warn "Fabric CLI: run './setup.sh --install-tools' to install"
    TOOLS_OK=false
fi

FABRIC_AUTH_OK=false
if [[ "$FAB_AVAILABLE" == "true" ]]; then
    if command -v timeout &>/dev/null; then
        FAB_AUTH_CHECK=(timeout 15s fab api get /v1/me)
    else
        FAB_AUTH_CHECK=(fab api get /v1/me)
    fi

    if "${FAB_AUTH_CHECK[@]}" &>/dev/null; then
        log_ok "Fabric auth: authenticated"
        FABRIC_AUTH_OK=true
    else
        log_warn "Fabric auth: not authenticated — run 'fab auth login' after setup"
    fi
fi

if check_tool "nbmon" "nbmon" "run: uv tool install nbmon"; then
    :
elif [[ "$INSTALL_TOOLS" == "true" ]]; then
    log_info "Installing nbmon..."
    uv tool install nbmon 2>/dev/null || log_warn "nbmon install failed — install manually"
else
    log_warn "nbmon: optional but recommended for Spark job debugging"
fi

if check_tool "rtk" "rtk" "see ~/.claude/RTK.md"; then
    :
else
    log_warn "rtk: optional token optimization tool"
fi

# ── Make bin scripts executable ────────────────────────────────────────────

log_step "Permissions"

for script in "${SCRIPT_DIR}/bin/"*; do
    if [[ -f "$script" && ! -x "$script" ]]; then
        chmod +x "$script"
        log_ok "chmod +x bin/$(basename "$script")"
    fi
done

# ── External Skills ────────────────────────────────────────────────────────

if [[ "$INSTALL_SKILLS" == "true" ]]; then
    log_step "External Skills"

    RECOMMENDED_PACKS=(
        "microsoft/skills-for-fabric"
        "PatrickGallucci/fabric-skills"
    )

    for pack in "${RECOMMENDED_PACKS[@]}"; do
        log_info "Installing ${pack}..."
        "${SCRIPT_DIR}/bin/install-skills.sh" add "$pack" || log_warn "Failed to install ${pack}"
    done
fi

# ── Summary ────────────────────────────────────────────────────────────────

echo ""
echo "════════════════════════════════════════════"

if [[ "$TOOLS_OK" == "true" ]]; then
    log_ok "Setup complete. All required tools found."
else
    log_warn "Setup complete with warnings. Some tools are missing."
    log_info "Run './setup.sh --install-tools' to install them."
fi

# ── Checklist ──────────────────────────────────────────────────────

if [[ "${RUN_CHECKLIST}" == "true" ]]; then
    log_step "Installation Checklist"

    CHECKLIST_OK=true

    # TARGET_REPO_PATH is set and the directory exists
    TARGET_REPO_PATH="${TARGET_REPO_PATH:-}"
    if [[ -z "${TARGET_REPO_PATH}" ]]; then
        log_warn "TARGET_REPO_PATH not set in .env — agents cannot modify the target repo"
        CHECKLIST_OK=false
    elif [[ ! -d "${TARGET_REPO_PATH}" ]]; then
        log_warn "TARGET_REPO_PATH='${TARGET_REPO_PATH}' does not exist — clone the target repo first"
        CHECKLIST_OK=false
    else
        log_ok "TARGET_REPO_PATH: ${TARGET_REPO_PATH}"
    fi

    # .env exists and has no unfilled CHANGE_ME placeholders
    if [[ -f "${SCRIPT_DIR}/.env" ]]; then
        if grep -q "CHANGE_ME\|<your-\|your-workspace\|your-lakehouse" "${SCRIPT_DIR}/.env" 2>/dev/null; then
            log_warn ".env has unfilled placeholder values — open .env and replace them"
            CHECKLIST_OK=false
        else
            log_ok ".env present and no obvious placeholders detected"
        fi
    else
        log_warn ".env not found — run './setup.sh' first"
        CHECKLIST_OK=false
    fi

    # Fabric auth
    if [[ "${FAB_AVAILABLE:-false}" == "true" ]]; then
        if [[ "${FABRIC_AUTH_OK:-false}" == "true" ]]; then
            log_ok "Fabric auth: authenticated"
        else
            log_warn "Fabric auth: not authenticated — run 'fab auth login'"
            CHECKLIST_OK=false
        fi
    else
        log_warn "Fabric CLI not available — install with './setup.sh --install-tools'"
        CHECKLIST_OK=false
    fi

    # Memory files have content beyond seed examples
    PLATFORM_FILE="${SCRIPT_DIR}/memory/platform.md"
    if [[ -f "${PLATFORM_FILE}" ]]; then
        REAL_LINES=$(grep -c "^\[" "${PLATFORM_FILE}" 2>/dev/null || true)
        REAL_LINES=$((REAL_LINES + $(grep -c "^|" "${PLATFORM_FILE}" 2>/dev/null || true)))
        if [[ "${REAL_LINES}" -gt 2 ]]; then
            log_ok "memory/platform.md has registered items"
        else
            log_warn "memory/platform.md appears empty — register at least one source system or sandbox item"
            CHECKLIST_OK=false
        fi
    else
        log_warn "memory/platform.md not found — run './setup.sh' first"
        CHECKLIST_OK=false
    fi

    # Source contracts present
    CONTRACT_COUNT=$(find "${SCRIPT_DIR}/templates" -name "*.yaml" 2>/dev/null | wc -l | tr -d ' ')
    if [[ "${CONTRACT_COUNT}" -gt 0 ]]; then
        log_ok "Source contract templates found: ${CONTRACT_COUNT}"
    else
        log_warn "No source contract YAML files in templates/ — create one from templates/source-contract.yaml"
        CHECKLIST_OK=false
    fi

    # Local notebook sources exist
    NOTEBOOK_COUNT=$(find "${SCRIPT_DIR}/src/notebooks" -name "*.py" 2>/dev/null | wc -l | tr -d ' ')
    if [[ "${NOTEBOOK_COUNT}" -gt 0 ]]; then
        log_ok "Local notebook sources found: ${NOTEBOOK_COUNT} in src/notebooks/"
    else
        log_warn "No .py notebook sources in src/notebooks/ — add at least one before smoke testing"
    fi

    echo ""
    echo "════════════════════════════════════════════"
    if [[ "${CHECKLIST_OK}" == "true" ]]; then
        log_ok "Day-one checklist passed. Ready to smoke test:"
        log_info "  bin/smoke-test-sandbox.sh --notebook <name>"
    else
        log_warn "Day-one checklist has items to resolve (see above)."
    fi
fi

echo ""
log_info "Next steps:"
log_info "  1. Create or open a sandbox Fabric workspace: https://app.fabric.microsoft.com → Workspaces → New workspace"
log_info "  2. Copy the workspace ID from Workspace settings and paste it into FABRIC_WORKSPACE_ID in .env"
log_info "  3. Create three lakehouses in that workspace: bronze_lh, silver_lh, gold_lh"
log_info "  4. Copy each Lakehouse ID from its Settings page into BRONZE/SILVER/GOLD_LAKEHOUSE_ID in .env"
log_info "  5. Run 'fab auth login' if the auth check above is not authenticated"
log_info "  6. Register sources with SRC_<SYSTEM>_TYPE=file and SRC_<SYSTEM>_PATH=./data/sandbox/<file>.csv"
log_info "  7. Open Claude Code / Codex and start with the orchestrator agent"
log_info "  8. Optional: 'python3 bin/validate-source-contract.py --allow-placeholders templates/source-contract.yaml'"
log_info "  9. Optional: 'python3 bin/validate-agent-guidance.py' after guidance changes"
log_info " 10. Optional: 'bin/smoke-test-sandbox.sh --notebook <name>' to run the sandbox smoke test"
log_info "      After the smoke test: 'python3 bin/post-smoke-update.py' to update agent memory"
log_info "      Or for manual steps: read docs/fabric-sandbox-smoke-test.md"
log_info " 11. Optional: read docs/fabric-mcp-readonly-discovery.md for MCP/read-only inventory discovery"
log_info " 12. Optional: './setup.sh --install-skills' for extra skill packs"
log_info "Docs: Microsoft Fabric lakehouse quickstart: https://learn.microsoft.com/en-us/fabric/data-engineering/tutorial-lakehouse-get-started"
echo ""
