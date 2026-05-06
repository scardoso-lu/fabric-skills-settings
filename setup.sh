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

# Parse flags
for arg in "$@"; do
    case $arg in
        --install-tools)   INSTALL_TOOLS=true ;;
        --install-skills)  INSTALL_SKILLS=true ;;
        --help|-h)
            echo "Usage: setup.sh [--install-tools] [--install-skills]"
            echo ""
            echo "  --install-tools    Install uv, Fabric CLI, and check rtk"
            echo "  --install-skills   Install recommended external skill packs"
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
    ".codex-fabric/memory/adr"
    ".codex-fabric/memory/platform-inventory"
    ".codex-fabric/memory/runbooks"
    ".codex-fabric/memory/security"
)

for dir in "${dirs[@]}"; do
    if [[ ! -d "${SCRIPT_DIR}/${dir}" ]]; then
        mkdir -p "${SCRIPT_DIR}/${dir}"
        log_ok "Created: ${dir}/"
    else
        log_info "Exists:  ${dir}/"
    fi
done

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

if check_tool "Fabric CLI (fab)" "fab" "run: ./setup.sh --install-tools"; then
    :
elif [[ "$INSTALL_TOOLS" == "true" ]]; then
    log_info "Installing Fabric CLI..."
    uv tool install ms-fabric-cli
    log_ok "Fabric CLI installed"
else
    log_warn "Fabric CLI: run './setup.sh --install-tools' to install"
    TOOLS_OK=false
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

echo ""
log_info "Next steps:"
log_info "  1. Fill in .env with your environment values"
log_info "  2. Run 'fab auth login' to authenticate with Fabric"
log_info "  3. Open Claude Code / Codex and start with the orchestrator agent"
log_info "  4. Optional: './setup.sh --install-skills' for extra skill packs"
echo ""
