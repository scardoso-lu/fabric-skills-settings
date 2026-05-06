#!/usr/bin/env bash
# install-skills.sh — Extension manager for fabric-codex skills
# Usage:
#   ./bin/install-skills.sh add <owner/repo>       Install a skill pack from GitHub
#   ./bin/install-skills.sh remove <pack-name>     Remove an installed skill pack
#   ./bin/install-skills.sh list                   List installed skill packs
#   ./bin/install-skills.sh update                 Update all installed skill packs
#   ./bin/install-skills.sh update <pack-name>     Update a specific skill pack

set -euo pipefail

SKILLS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/skills/external"
REGISTRY_FILE="${SKILLS_DIR}/.registry.json"

# Ensure external skills directory exists
mkdir -p "$SKILLS_DIR"

# Initialize registry if it doesn't exist
if [[ ! -f "$REGISTRY_FILE" ]]; then
    echo '{"packs": []}' > "$REGISTRY_FILE"
fi

# ── Helpers ────────────────────────────────────────────────────────────────

log_ok()   { echo "✓ $*"; }
log_info() { echo "  $*"; }
log_err()  { echo "✗ $*" >&2; }

registry_add() {
    local repo="$1" pack_name="$2"
    # Simple JSON update using python (portable, no jq dependency)
    python3 - <<EOF
import json, sys
with open('$REGISTRY_FILE') as f:
    reg = json.load(f)
packs = [p for p in reg['packs'] if p['name'] != '$pack_name']
packs.append({'name': '$pack_name', 'repo': '$repo'})
reg['packs'] = packs
with open('$REGISTRY_FILE', 'w') as f:
    json.dump(reg, f, indent=2)
EOF
}

registry_remove() {
    local pack_name="$1"
    python3 - <<EOF
import json
with open('$REGISTRY_FILE') as f:
    reg = json.load(f)
reg['packs'] = [p for p in reg['packs'] if p['name'] != '$pack_name']
with open('$REGISTRY_FILE', 'w') as f:
    json.dump(reg, f, indent=2)
EOF
}

registry_list() {
    python3 - <<EOF
import json
with open('$REGISTRY_FILE') as f:
    reg = json.load(f)
if not reg['packs']:
    print("No external skill packs installed.")
else:
    print(f"{'Pack':<30} {'Repo'}")
    print("-" * 60)
    for p in reg['packs']:
        print(f"{p['name']:<30} {p['repo']}")
EOF
}

registry_get_repo() {
    local pack_name="$1"
    python3 -c "
import json
with open('$REGISTRY_FILE') as f:
    reg = json.load(f)
match = [p for p in reg['packs'] if p['name'] == '$pack_name']
print(match[0]['repo'] if match else '')
"
}

# ── Commands ───────────────────────────────────────────────────────────────

cmd_add() {
    local repo="${1:-}"
    if [[ -z "$repo" ]]; then
        log_err "Usage: install-skills.sh add <owner/repo>"
        exit 1
    fi

    local pack_name="${repo//\//-}"
    local target_dir="${SKILLS_DIR}/${pack_name}"

    if [[ -d "$target_dir" ]]; then
        log_info "Pack '$pack_name' already installed. Use 'update' to refresh."
        exit 0
    fi

    log_info "Installing skill pack from github.com/${repo} ..."
    if ! git clone --depth=1 "https://github.com/${repo}.git" "$target_dir"; then
        log_err "Clone failed. Check the repo URL and your internet connection."
        exit 1
    fi

    # Remove git history to keep it lean
    rm -rf "${target_dir}/.git"

    registry_add "$repo" "$pack_name"
    log_ok "Installed: ${pack_name} → skills/external/${pack_name}/"
    log_info "Skills are immediately available to agents."
}

cmd_remove() {
    local pack_name="${1:-}"
    if [[ -z "$pack_name" ]]; then
        log_err "Usage: install-skills.sh remove <pack-name>"
        log_info "Run 'install-skills.sh list' to see installed packs."
        exit 1
    fi

    local target_dir="${SKILLS_DIR}/${pack_name}"
    if [[ ! -d "$target_dir" ]]; then
        log_err "Pack '$pack_name' is not installed."
        exit 1
    fi

    rm -rf "$target_dir"
    registry_remove "$pack_name"
    log_ok "Removed: ${pack_name}"
}

cmd_list() {
    echo ""
    echo "Core skills (bundled):"
    for skill_dir in "$(dirname "$SKILLS_DIR")/core"/*/; do
        [[ -d "$skill_dir" ]] && log_info "$(basename "$skill_dir")"
    done

    echo ""
    echo "External skill packs:"
    registry_list
}

cmd_update() {
    local pack_name="${1:-}"

    if [[ -n "$pack_name" ]]; then
        # Update single pack
        local repo
        repo=$(registry_get_repo "$pack_name")
        if [[ -z "$repo" ]]; then
            log_err "Pack '$pack_name' not found in registry."
            exit 1
        fi
        local target_dir="${SKILLS_DIR}/${pack_name}"
        rm -rf "$target_dir"
        git clone --depth=1 "https://github.com/${repo}.git" "$target_dir"
        rm -rf "${target_dir}/.git"
        log_ok "Updated: ${pack_name}"
    else
        # Update all packs
        export REGISTRY_FILE SKILLS_DIR
        python3 - <<'PYEOF'
import json, subprocess, os, shutil

registry_file = os.environ.get('REGISTRY_FILE', '')
skills_dir = os.environ.get('SKILLS_DIR', '')

with open(registry_file) as f:
    reg = json.load(f)

for pack in reg['packs']:
    name = pack['name']
    repo = pack['repo']
    target = os.path.join(skills_dir, name)
    shutil.rmtree(target, ignore_errors=True)
    print(f"  Updating {name}...")
    subprocess.run(['git', 'clone', '--depth=1', f'https://github.com/{repo}.git', target], check=True)
    shutil.rmtree(os.path.join(target, '.git'), ignore_errors=True)
    print(f"✓ Updated: {name}")
PYEOF
    fi
}

# ── Entry point ─────────────────────────────────────────────────────────────

command="${1:-list}"
shift || true

case "$command" in
    add)     cmd_add "$@" ;;
    remove)  cmd_remove "$@" ;;
    list)    cmd_list ;;
    update)  cmd_update "$@" ;;
    *)
        echo "Usage: install-skills.sh <add|remove|list|update> [args]"
        exit 1
        ;;
esac
