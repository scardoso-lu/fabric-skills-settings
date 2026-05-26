#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Validate vendor-native Fabric agent profile package layout."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROFILES = ROOT / "cli" / "profiles"
SETUP = ROOT / "cli" / "setup"
CLI_TOOLS = ROOT / "cli" / "tools"
SERVER = ROOT / "server"
TOOLS = SERVER / "tools"
GRAPH_CONTENT = SERVER / "content"
RULES = GRAPH_CONTENT / "rules"
SKILLS = {
    "rtk",
    "fabric-ingest",
    "fabric-transform",
    "fabric-model",
    "fabric-validate",
    "fabric-notebook-loop",
    "fabric-ops",
    "fabric-pipeline",
    "semantic-model",
    "mock-data",
    "prd",
    "grill-me",
    "git-commit",
    "caveman",
}
AGENTS = {"orchestrator", "developer", "tester", "operator"}
# Source-of-truth layout: cli/ holds installable assets for target users, server/
# holds the MCP server + graph runtime + content + builders. The graph is
# server-side now; target users no longer receive a local copy.
FORBIDDEN = [
    "wrapper repo",
    "configuration wrapper",
    "ignore target repo instructions",
    "this repo is the authoritative harness",
    "everything goes to $TARGET_REPO_PATH",
]


def error(message: str, errors: list[str]) -> None:
    errors.append(message)


def require(path: Path, errors: list[str]) -> None:
    if not path.exists():
        error(f"Missing required path: {path.relative_to(ROOT)}", errors)


def skill_names(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {p.parent.name for p in path.glob("*/SKILL.md")}


def agent_names(path: Path, suffix: str) -> set[str]:
    if not path.exists():
        return set()
    return {p.stem for p in path.glob(f"*{suffix}")}


def validate_required(errors: list[str]) -> None:
    require(PROFILES / "codex" / "AGENTS.md", errors)
    require(PROFILES / "codex" / "config.toml", errors)
    require(PROFILES / "claude" / "CLAUDE.md", errors)
    require(PROFILES / "claude" / "settings.local.json", errors)
    if (PROFILES / "claude" / "settings.json").exists():
        error("profiles/claude/settings.json must not exist; Claude local installs use settings.local.json", errors)
    require(PROFILES / "shared" / ".env.example", errors)
    require(PROFILES / "shared" / ".gitignore.fragment", errors)
    require(PROFILES / "shared" / "scaffold" / ".mcp.json", errors)
    require(RULES / "data-engineering.md", errors)
    require(RULES / "fabric-platform.md", errors)
    require(RULES / "security.md", errors)
    require(GRAPH_CONTENT / "entry.md", errors)
    # server/ — MCP server + graph runtime + graph content + graph builders.
    require(SERVER / "__init__.py", errors)
    require(SERVER / "app.py", errors)
    require(SERVER / "script_runner.py", errors)
    require(SERVER / "audit.py", errors)
    require(SERVER / "Dockerfile", errors)
    require(SERVER / "graph" / "store.py", errors)
    require(SERVER / "graph" / "search.py", errors)
    require(SERVER / "graph" / "writes.py", errors)
    require(SERVER / "builders" / "build-graph.py", errors)
    # server/tools/ — MCP-exposed helpers that don't need ms-fabric-cli.
    require(TOOLS / "semantic_model" / "tools.py", errors)
    require(TOOLS / "semantic_model" / "inspect.py", errors)
    require(TOOLS / "validate" / "tools.py", errors)
    require(TOOLS / "validate" / "pipeline-lineage.py", errors)
    require(TOOLS / "data" / "tools.py", errors)
    require(TOOLS / "data" / "mock-data-generator.py", errors)
    require(TOOLS / "graph" / "tools.py", errors)
    # cli/tools/ — target-side helpers, shipped to target as tool/ and
    # invoked locally via Bash (NOT MCP). Fabric-CLI-dependent helpers plus
    # the deterministic lint scaffold + pre-commit aggregator.
    require(CLI_TOOLS / "notebook" / "build.py", errors)
    require(CLI_TOOLS / "notebook" / "deploy.py", errors)
    require(CLI_TOOLS / "notebook" / "smoke-test.ps1", errors)
    require(CLI_TOOLS / "notebook" / "smoke-test.sh", errors)
    require(CLI_TOOLS / "pipeline" / "manage.py", errors)
    require(CLI_TOOLS / "lakehouse" / "list-tables.py", errors)
    require(CLI_TOOLS / "workspace" / "init.py", errors)
    require(CLI_TOOLS / "workspace" / "switch.py", errors)
    require(CLI_TOOLS / "workspace" / "transfer.py", errors)
    require(CLI_TOOLS / "workspace" / "pick.py", errors)
    require(CLI_TOOLS / "lint" / "__init__.py", errors)
    require(CLI_TOOLS / "lint" / "core.py", errors)
    require(CLI_TOOLS / "precommit" / "pre-commit-check.ps1", errors)
    require(CLI_TOOLS / "precommit" / "pre-commit-check.sh", errors)
    # cli/setup/ — env-setup scripts (shipped to target as tool/setup/).
    require(SETUP / "setup.ps1", errors)
    require(SETUP / "setup.sh", errors)
    # Skills live on the server and are served via graph_get_node — not shipped to target.
    server_skills = skill_names(SERVER / "skills")
    if (PROFILES / "skills").exists():
        error("cli/profiles/skills must not exist; skills moved to server/skills/")
    if server_skills != SKILLS:
        error(f"Server skills mismatch: expected {sorted(SKILLS)}, found {sorted(server_skills)}", errors)

    codex_agents = agent_names(PROFILES / "codex" / "agents", ".toml")
    claude_agents = agent_names(PROFILES / "claude" / "agents", ".md")
    if codex_agents != AGENTS:
        error(f"Codex agents mismatch: expected {sorted(AGENTS)}, found {sorted(codex_agents)}", errors)
    if claude_agents != AGENTS:
        error(f"Claude agents mismatch: expected {sorted(AGENTS)}, found {sorted(claude_agents)}", errors)


def validate_forbidden_text(errors: list[str]) -> None:
    profile_files = [p for p in PROFILES.rglob("*") if p.is_file()]
    for path in profile_files:
        text = path.read_text(errors="ignore")
        rel = path.relative_to(ROOT)
        for phrase in FORBIDDEN:
            if phrase in text:
                error(f"Forbidden phrase {phrase!r} in {rel}", errors)
        if "TARGET_REPO_PATH" in text:
            error(f"Unexpected TARGET_REPO_PATH usage in {rel}", errors)


def validate_safe_datalake_controls(errors: list[str]) -> None:
    settings = PROFILES / "claude" / "settings.local.json"
    if settings.exists():
        text = settings.read_text(errors="ignore")
        for phrase in ("Bash(fab *)", "Bash(rtk *)", "mcp__fabric__fabric_api_get"):
            if phrase in text:
                error(
                    f"Unsafe agent permission {phrase!r} in {settings.relative_to(ROOT)}",
                    errors,
                )


def validate_env_example(errors: list[str]) -> None:
    """Reject real values in the .env.example template. Commented lines are
    treated as illustrative guidance and not scanned."""
    env_text = (PROFILES / "shared" / ".env.example").read_text(errors="ignore")
    suspicious_patterns = [
        r"=https?://",
        r"=abfss://",
        r"=jdbc:",
        r"=AccountKey=",
        r"=SharedAccessSignature=",
        r"=eyJ[A-Za-z0-9_-]+",
    ]
    for line in env_text.splitlines():
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#"):
            continue
        for pattern in suspicious_patterns:
            if re.search(pattern, stripped):
                error(
                    f"Suspicious non-placeholder value in profiles/shared/.env.example matching {pattern}",
                    errors,
                )


def validate_shared_scope(errors: list[str]) -> None:
    shared = PROFILES / "shared"
    forbidden_dirs = [shared / ".agents", shared / ".codex", shared / ".claude", shared / "skills", shared / "agents"]
    for path in forbidden_dirs:
        if path.exists():
            error(f"Shared profile must not contain vendor runtime assets: {path.relative_to(ROOT)}", errors)


def validate_rule_mirrors(errors: list[str]) -> None:
    """Verify source-of-truth rules live under server/content/rules/."""
    for name in ("data-engineering.md", "fabric-platform.md", "security.md"):
        source = RULES / name
        if not source.exists():
            error(f"Missing source rule file: server/content/rules/{name}", errors)

    platform = RULES / "fabric-platform.md"
    if platform.exists():
        text = platform.read_text(errors="ignore")
        forbidden = [
            "fab auth login",
            "fab auth token",
            "fab api ",
        ]
        for phrase in forbidden:
            if phrase in text:
                error(
                    f"server/content/rules/fabric-platform.md must reference the MCP fabric_* tools instead of raw {phrase!r}",
                    errors,
                )


def validate_ps1_syntax(errors: list[str]) -> None:
    """Smoke-test.ps1 must not use PS7-only null-conditional ?. operator."""
    for location in [
        CLI_TOOLS / "notebook" / "smoke-test.ps1",
    ]:
        if not location.exists():
            continue
        text = location.read_text(errors="ignore")
        if "?." in text:
            rel_path = location.relative_to(ROOT)
            errors.append(
                f"PS7-only null-conditional '?.' found in {rel_path} — must be PS5.1 compatible"
            )


def validate_load_env_strips_comments(errors: list[str]) -> None:
    """build.py and deploy.py must strip inline comments from .env values."""
    for name in ("build.py", "deploy.py"):
        for location in [
            CLI_TOOLS / "notebook" / name,
        ]:
            if not location.exists():
                continue
            text = location.read_text(errors="ignore")
            if 'val.split("#")[0]' not in text:
                rel_path = location.relative_to(ROOT)
                errors.append(
                    f"_load_env in {rel_path} does not strip inline comments"
                    " — add val.split(\"#\")[0].strip() before setdefault"
                )


def validate_gitignore_fragment(errors: list[str]) -> None:
    """gitignore.fragment must ignore target-local runtime files.

    The source package tracks profiles/shared/scaffold/.mcp.json so the
    installer can create it, but target projects should ignore the installed
    .mcp.json because MCP settings are local runtime configuration.
    """
    path = PROFILES / "shared" / ".gitignore.fragment"
    if not path.exists():
        return
    text = path.read_text(errors="ignore")
    if ".mcp.json" not in text:
        errors.append(
            "profiles/shared/.gitignore.fragment must ignore .mcp.json"
            " — MCP settings are installed for local target runtime use"
        )


def validate_setup_contract(errors: list[str]) -> None:
    """Setup must prompt for SPN creds + server URL, never workspace IDs."""
    for location in [SETUP / "setup.ps1", SETUP / "setup.sh"]:
        if not location.exists():
            continue
        text = location.read_text(errors="ignore")
        rel_path = location.relative_to(ROOT)
        if "Fabric workspace GUID" in text:
            errors.append(
                f"{rel_path} must not prompt for FABRIC_WORKSPACE_ID; use the workspace_init/workspace_switch MCP tools"
            )
        for phrase in ("FABRIC_TENANT_ID", "FABRIC_CLIENT_ID", "FABRIC_CLIENT_SECRET", "FABRIC_SERVER_URL"):
            if phrase not in text:
                errors.append(f"{rel_path} missing setup contract phrase {phrase!r}")


def validate_setup_no_graph_build(errors: list[str]) -> None:
    """Target-side setup must not invoke the graph builder — the graph lives on the MCP server now."""
    for location in (SETUP / "setup.ps1", SETUP / "setup.sh"):
        if not location.exists():
            continue
        text = location.read_text(errors="ignore").replace("\\", "/")
        rel_path = location.relative_to(ROOT)
        for forbidden in ("server/builders/build-graph.py", "bin/build-graph.py"):
            if forbidden in text:
                errors.append(
                    f"{rel_path} must not reference the graph builder "
                    "(target users do not build graphs; the MCP server owns the graph)"
                )


def main() -> int:
    errors: list[str] = []
    validate_required(errors)
    validate_forbidden_text(errors)
    validate_safe_datalake_controls(errors)
    validate_env_example(errors)
    validate_shared_scope(errors)
    validate_rule_mirrors(errors)
    validate_ps1_syntax(errors)
    validate_load_env_strips_comments(errors)
    validate_gitignore_fragment(errors)
    validate_setup_contract(errors)
    validate_setup_no_graph_build(errors)

    if errors:
        print("FAIL: install package validation failed")
        for item in errors:
            print(f"- {item}")
        return 1
    print("PASS: install package layout is vendor-native and aligned")
    return 0


if __name__ == "__main__":
    sys.exit(main())
