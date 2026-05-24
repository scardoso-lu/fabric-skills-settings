#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Validate source-package guidance for the vendor-native installer setup.

This validator was rewritten in Phase P4 of the graph-driven-profile branch.
The old per-profile phrase checks now live in profiles/shared/graph-content/
nodes; the profile files themselves are checked only for hard-minimal shape
(<= 50 lines, must mention the graph tool, must NOT contain operational
section names).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_SKILLS = {
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
REQUIRED_AGENTS = {"orchestrator", "developer", "tester", "operator"}
FORBIDDEN_ROOT_RUNTIME = [
    ROOT / ".claude" / "agents",
    ROOT / ".claude" / "skills",
    ROOT / "skills",
]
FORBIDDEN_GUIDANCE_PHRASES = [
    "configuration wrapper",
    "authoritative harness",
    "ignore target repo instructions",
    "everything goes to `$TARGET_REPO_PATH`",
]

PROFILE_FILES = [
    ROOT / "profiles" / "claude" / "CLAUDE.md",
    ROOT / "profiles" / "codex" / "AGENTS.md",
]
GRAPH_CONTENT_DIR = ROOT / "profiles" / "shared" / "graph-content"
ENTRY_FILE = GRAPH_CONTENT_DIR / "entry.md"
SESSION_START_FILE = GRAPH_CONTENT_DIR / "session" / "session-start.md"
OPERATING_RULES_FILE = GRAPH_CONTENT_DIR / "session" / "operating-rules.md"
SKILLS_INDEX_FILE = GRAPH_CONTENT_DIR / "indexes" / "skills-index.md"

PROFILE_MAX_LINES = 50
PROFILE_ANCHOR = "You know NOTHING about this project except how to call the graph tool"
PROFILE_ENTRY_TOOL = "graph_get_entry"
PROFILE_FORBIDDEN_SECTION_NAMES = [
    "## Pipeline Structure",
    "## Tool Layout",
    "## Directory Layout",
    "## Operating Rules",
    "## Notebook Workflow",
    "## Smoke-test Diagnostics",
    "## Semantic Models",
    "## Workspace Management",
]


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def require(path: Path, errors: list[str]) -> None:
    if not path.exists():
        errors.append(f"missing required path: {rel(path)}")


def skill_names(base: Path) -> set[str]:
    return {p.parent.name for p in base.glob("*/SKILL.md")} if base.exists() else set()


def agent_names(base: Path, suffix: str) -> set[str]:
    return {p.stem for p in base.glob(f"*{suffix}")} if base.exists() else set()


def validate_root_guidance(errors: list[str]) -> None:
    for path in [ROOT / "AGENTS.md", ROOT / "CLAUDE.md", ROOT / "README.md"]:
        require(path, errors)
        if not path.exists():
            continue
        text = path.read_text(errors="ignore")
        if "install-fabric-agent" not in text:
            errors.append(f"{rel(path)} must describe installer-first usage")
        if "profiles/codex" not in text and path.name != "README.md":
            errors.append(f"{rel(path)} must reference profiles/codex")
        if "profiles/claude" not in text and path.name != "README.md":
            errors.append(f"{rel(path)} must reference profiles/claude")
        for phrase in FORBIDDEN_GUIDANCE_PHRASES:
            if phrase in text:
                errors.append(f"forbidden wrapper phrase {phrase!r} in {rel(path)}")


def validate_profiles(errors: list[str]) -> None:
    require(ROOT / "profiles" / "codex" / "AGENTS.md", errors)
    require(ROOT / "profiles" / "codex" / "config.toml", errors)
    require(ROOT / "profiles" / "claude" / "CLAUDE.md", errors)
    require(ROOT / "profiles" / "claude" / "settings.local.json", errors)
    if (ROOT / "profiles" / "claude" / "settings.json").exists():
        errors.append("profiles/claude/settings.json must not exist; Claude local installs use settings.local.json")
    require(ROOT / "profiles" / "shared" / "project-layout" / "memory" / "rules" / "data-engineering.md", errors)
    require(ROOT / "profiles" / "shared" / "project-layout" / "memory" / "rules" / "fabric-platform.md", errors)
    require(ROOT / "profiles" / "shared" / "project-layout" / "memory" / "rules" / "security.md", errors)

    shared_skills = skill_names(ROOT / "profiles" / "skills")
    codex_skills_dir = ROOT / "profiles" / "codex" / "skills"
    claude_skills_dir = ROOT / "profiles" / "claude" / "skills"
    if codex_skills_dir.exists():
        errors.append("profiles/codex/skills must not exist; Codex installs skills from profiles/skills")
    if claude_skills_dir.exists():
        errors.append("profiles/claude/skills must not exist; Claude installs skills from profiles/skills")
    if shared_skills != REQUIRED_SKILLS:
        errors.append(f"Shared skill set mismatch: {sorted(shared_skills)}")

    codex_agents = agent_names(ROOT / "profiles" / "codex" / "agents", ".toml")
    claude_agents = agent_names(ROOT / "profiles" / "claude" / "agents", ".md")
    if codex_agents != REQUIRED_AGENTS:
        errors.append(f"Codex agent set mismatch: {sorted(codex_agents)}")
    if claude_agents != REQUIRED_AGENTS:
        errors.append(f"Claude agent set mismatch: {sorted(claude_agents)}")
    if codex_agents != claude_agents:
        errors.append("Codex and Claude profile agents differ")

    settings = ROOT / "profiles" / "claude" / "settings.local.json"
    if settings.exists():
        text = settings.read_text(errors="ignore")
        forbidden_permissions = [
            "Bash(fab *)",
            "Bash(rtk *)",
            "mcp__fabric__fabric_api_get",
        ]
        for phrase in forbidden_permissions:
            if phrase in text:
                errors.append(
                    f"{rel(settings)} must not allow {phrase!r}; agents consume only the safe sandbox workspace"
                )


def validate_profile_minimalism(errors: list[str]) -> None:
    """Hard-minimal profile: <=50 lines, references the graph entry tool,
    contains the anti-drift anchor sentence, and contains NO operational
    section names (anti-bypass - operational content must live in graph nodes)."""
    for path in PROFILE_FILES:
        if not path.exists():
            continue
        text = path.read_text(errors="ignore")
        line_count = text.count("\n") + (0 if text.endswith("\n") else 1)
        if line_count > PROFILE_MAX_LINES:
            errors.append(
                f"{rel(path)} has {line_count} lines; hard-minimal profile must be <= {PROFILE_MAX_LINES}"
            )
        if PROFILE_ENTRY_TOOL not in text:
            errors.append(f"{rel(path)} must reference {PROFILE_ENTRY_TOOL!r}")
        if PROFILE_ANCHOR not in text:
            errors.append(f"{rel(path)} must contain anti-drift anchor sentence: {PROFILE_ANCHOR!r}")
        for forbidden in PROFILE_FORBIDDEN_SECTION_NAMES:
            if forbidden in text:
                errors.append(
                    f"{rel(path)} contains operational section heading {forbidden!r};"
                    " move that content to a graph-content node"
                )


def validate_entry_node(errors: list[str]) -> None:
    """The mandatory setup gate moved into graph-content/entry.md (Phase P4).

    Phrases that USED to be required in the profile must now be present here.
    """
    if not ENTRY_FILE.exists():
        errors.append(f"missing entry node: {rel(ENTRY_FILE)}")
        return
    text = ENTRY_FILE.read_text(errors="ignore")
    required = [
        "tool\\setup\\setup.ps1",
        "tool/setup/setup.sh",
        "FABRIC_WORKSPACE_ID",
        "fab-sandbox auth login",
        "Do **not** read `.env` contents",
        "Setup incomplete",
        "Mandatory setup gate",
        "verify `.env`, `fab`, and `fab auth`",
        "before accepting any Fabric work",
        "network",
        "lakehouse",
        "notebook",
    ]
    for phrase in required:
        if phrase not in text:
            errors.append(f"missing required phrase in {rel(ENTRY_FILE)}: {phrase!r}")
    forbidden = [
        "FABRIC_WORKSPACE_ID` is missing",
    ]
    for phrase in forbidden:
        if phrase in text:
            errors.append(f"entry node {rel(ENTRY_FILE)} implies reading .env via {phrase!r}")


def validate_skills_index_node(errors: list[str]) -> None:
    """All 13 skills must be named in the skills-index node (moved from profile)."""
    if not SKILLS_INDEX_FILE.exists():
        errors.append(f"missing skills index node: {rel(SKILLS_INDEX_FILE)}")
        return
    text = SKILLS_INDEX_FILE.read_text(errors="ignore")
    for skill in REQUIRED_SKILLS:
        if f"`{skill}`" not in text:
            errors.append(f"{rel(SKILLS_INDEX_FILE)} must list installed skill `{skill}`")


def validate_session_nodes(errors: list[str]) -> None:
    """Operating-rules node must reference the three rule files (moved from profile)."""
    if not OPERATING_RULES_FILE.exists():
        errors.append(f"missing operating-rules node: {rel(OPERATING_RULES_FILE)}")
        return
    text = OPERATING_RULES_FILE.read_text(errors="ignore")
    for rule_id in ("rules/security", "rules/data-engineering", "rules/fabric-platform"):
        if rule_id not in text:
            errors.append(f"{rel(OPERATING_RULES_FILE)} must reference {rule_id!r}")


def validate_platform_rules_use_wrapper(errors: list[str]) -> None:
    for path in [
        ROOT / "rules" / "fabric-platform.md",
        ROOT / "profiles" / "shared" / "project-layout" / "memory" / "rules" / "fabric-platform.md",
    ]:
        if not path.exists():
            continue
        text = path.read_text(errors="ignore")
        for phrase in ("fab auth login", "fab auth token", "fab api "):
            if phrase in text:
                errors.append(
                    f"{rel(path)} must use tool/setup/fab-sandbox instead of raw {phrase!r}"
                )


def validate_skill_wiring(errors: list[str]) -> None:
    required = [
        (
            ROOT / "profiles" / "claude" / "agents" / "developer.md",
            ["fabric-transform", "fabric-model"],
        ),
        (
            ROOT / "profiles" / "codex" / "agents" / "developer.toml",
            ["fabric-transform", "fabric-model"],
        ),
        (
            ROOT / "profiles" / "claude" / "agents" / "tester.md",
            ["fabric-validate", "tester"],
        ),
        (
            ROOT / "profiles" / "codex" / "agents" / "tester.toml",
            ["fabric-validate", "tester"],
        ),
        (
            ROOT / "rules" / "data-engineering.md",
            ["fabric-transform", "fabric-validate"],
        ),
        (
            ROOT / "rules" / "fabric-platform.md",
            ["fabric-model"],
        ),
    ]
    for path, phrases in required:
        if not path.exists():
            errors.append(f"missing required path for skill wiring: {rel(path)}")
            continue
        text = path.read_text(errors="ignore")
        for phrase in phrases:
            if phrase not in text:
                errors.append(f"missing skill wiring phrase {phrase!r} in {rel(path)}")


def validate_no_root_runtime(errors: list[str]) -> None:
    for path in FORBIDDEN_ROOT_RUNTIME:
        if path.exists():
            errors.append(f"root runtime directory should not exist in source package: {rel(path)}")


def main() -> int:
    errors: list[str] = []
    validate_root_guidance(errors)
    validate_profiles(errors)
    validate_profile_minimalism(errors)
    validate_entry_node(errors)
    validate_skills_index_node(errors)
    validate_session_nodes(errors)
    validate_platform_rules_use_wrapper(errors)
    validate_skill_wiring(errors)
    validate_no_root_runtime(errors)

    if errors:
        print("FAIL: agent guidance validation failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PASS: agent guidance matches vendor-native installer setup")
    return 0


if __name__ == "__main__":
    sys.exit(main())
