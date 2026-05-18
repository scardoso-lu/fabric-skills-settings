#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Validate vendor-native Fabric agent profile package layout."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILES = ROOT / "profiles"
SKILLS = {
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
MIRRORED_HELPERS = [
    "data/mock-data-generator.py",
    "lakehouse/list-tables.py",
    "semantic-model/inspect.py",
    "mcp/server.py",
    "pipeline/manage.py",
    "notebook/build.py",
    "notebook/deploy.py",
    "notebook/smoke-test.ps1",
    "notebook/smoke-test.sh",
    "pre-commit-check.ps1",
    "pre-commit-check.sh",
    "setup/fab-sandbox",
    "setup/fab-sandbox.ps1",
    "setup/fabric-inventory-readonly",
    "setup/fabric-inventory-readonly.ps1",
    "setup/setup.ps1",
    "setup/setup.sh",
    "validate/pipeline-lineage.py",
]
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
    require(PROFILES / "claude" / "settings.json", errors)
    require(PROFILES / "shared" / "memory" / "MEMORY.md", errors)
    require(PROFILES / "shared" / ".env.example", errors)
    require(PROFILES / "shared" / ".gitignore.fragment", errors)
    require(PROFILES / "shared" / "project-layout" / ".mcp.json", errors)
    require(PROFILES / "shared" / "project-layout" / "memory" / "rules" / "data-engineering.md", errors)
    require(PROFILES / "shared" / "project-layout" / "memory" / "rules" / "fabric-platform.md", errors)
    require(PROFILES / "shared" / "project-layout" / "memory" / "rules" / "security.md", errors)
    require(PROFILES / "shared" / "project-layout" / "tool" / "mcp" / "server.py", errors)
    require(PROFILES / "shared" / "project-layout" / "tool" / "notebook" / "build.py", errors)
    require(PROFILES / "shared" / "project-layout" / "tool" / "notebook" / "deploy.py", errors)
    require(PROFILES / "shared" / "project-layout" / "tool" / "notebook" / "smoke-test.ps1", errors)
    require(PROFILES / "shared" / "project-layout" / "tool" / "notebook" / "smoke-test.sh", errors)
    require(PROFILES / "shared" / "project-layout" / "tool" / "pre-commit-check.ps1", errors)
    require(PROFILES / "shared" / "project-layout" / "tool" / "pre-commit-check.sh", errors)
    require(PROFILES / "shared" / "project-layout" / "tool" / "setup" / "fab-sandbox", errors)
    require(PROFILES / "shared" / "project-layout" / "tool" / "setup" / "fab-sandbox.ps1", errors)
    require(PROFILES / "shared" / "project-layout" / "tool" / "setup" / "fabric-inventory-readonly", errors)
    require(PROFILES / "shared" / "project-layout" / "tool" / "setup" / "fabric-inventory-readonly.ps1", errors)
    require(PROFILES / "shared" / "project-layout" / "tool" / "setup" / "setup.ps1", errors)
    require(PROFILES / "shared" / "project-layout" / "tool" / "setup" / "setup.sh", errors)
    require(PROFILES / "shared" / "project-layout" / "tool" / "lakehouse" / "list-tables.py", errors)
    require(PROFILES / "shared" / "project-layout" / "tool" / "semantic-model" / "inspect.py", errors)
    require(PROFILES / "shared" / "project-layout" / "tool" / "data" / "mock-data-generator.py", errors)
    require(PROFILES / "shared" / "project-layout" / "tool" / "pipeline" / "manage.py", errors)
    require(PROFILES / "shared" / "project-layout" / "tool" / "validate" / "pipeline-lineage.py", errors)

    shared_skills = skill_names(PROFILES / "skills")
    codex_skills_dir = PROFILES / "codex" / "skills"
    claude_skills_dir = PROFILES / "claude" / "skills"
    if codex_skills_dir.exists():
        error("profiles/codex/skills must not exist; installer copies profiles/skills into .agents/skills")
    if claude_skills_dir.exists():
        error("profiles/claude/skills must not exist; installer copies profiles/skills into .claude/skills")
    if shared_skills != SKILLS:
        error(f"Shared skills mismatch: expected {sorted(SKILLS)}, found {sorted(shared_skills)}", errors)

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
    settings = PROFILES / "claude" / "settings.json"
    if settings.exists():
        text = settings.read_text(errors="ignore")
        for phrase in ("Bash(fab *)", "Bash(rtk *)", "mcp__fabric__fabric_api_get"):
            if phrase in text:
                error(
                    f"Unsafe agent permission {phrase!r} in {settings.relative_to(ROOT)}",
                    errors,
                )


def validate_env_example(errors: list[str]) -> None:
    env_text = (PROFILES / "shared" / ".env.example").read_text(errors="ignore")
    suspicious_patterns = [
        r"=https?://",
        r"=abfss://",
        r"=jdbc:",
        r"=AccountKey=",
        r"=SharedAccessSignature=",
        r"=eyJ[A-Za-z0-9_-]+",
    ]
    for pattern in suspicious_patterns:
        if re.search(pattern, env_text):
            error(f"Suspicious non-placeholder value in profiles/shared/.env.example matching {pattern}", errors)


def validate_shared_scope(errors: list[str]) -> None:
    shared = PROFILES / "shared"
    forbidden_dirs = [shared / ".agents", shared / ".codex", shared / ".claude", shared / "skills", shared / "agents"]
    for path in forbidden_dirs:
        if path.exists():
            error(f"Shared profile must not contain vendor runtime assets: {path.relative_to(ROOT)}", errors)


def validate_root_helper_mirrors(errors: list[str]) -> None:
    for name in MIRRORED_HELPERS:
        source = PROFILES / "shared" / "project-layout" / "tool" / name
        mirror = ROOT / "tool" / name
        if not mirror.exists():
            error(f"Missing root helper mirror: {mirror.relative_to(ROOT)}", errors)
            continue
        if source.read_text(errors="ignore") != mirror.read_text(errors="ignore"):
            error(f"Root helper mirror differs from install profile: tool/{name}", errors)


def validate_rule_mirrors(errors: list[str]) -> None:
    for name in ("data-engineering.md", "fabric-platform.md", "security.md"):
        source = ROOT / "rules" / name
        installed = PROFILES / "shared" / "project-layout" / "memory" / "rules" / name
        if not source.exists():
            error(f"Missing source rule file: rules/{name}", errors)
            continue
        if not installed.exists():
            error(f"Missing installed rule file: profiles/shared/project-layout/memory/rules/{name}", errors)
            continue
        if source.read_text(errors="ignore") != installed.read_text(errors="ignore"):
            error(f"Installed rule mirror differs from source: memory/rules/{name}", errors)

    platform = ROOT / "rules" / "fabric-platform.md"
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
                    f"rules/fabric-platform.md must use tool/setup/fab-sandbox instead of raw {phrase!r}",
                    errors,
                )


def validate_ps1_syntax(errors: list[str]) -> None:
    """Smoke-test.ps1 must not use PS7-only null-conditional ?. operator."""
    for location in [
        PROFILES / "shared" / "project-layout" / "tool" / "notebook" / "smoke-test.ps1",
        ROOT / "tool" / "notebook" / "smoke-test.ps1",
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
            PROFILES / "shared" / "project-layout" / "tool" / "notebook" / name,
            ROOT / "tool" / "notebook" / name,
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

    The source package tracks profiles/shared/project-layout/.mcp.json so the
    installer can create it, but target projects should ignore the installed
    .mcp.json because MCP settings are local runtime configuration.
    """
    path = PROFILES / "shared" / ".gitignore.fragment"
    if not path.exists():
        return
    text = path.read_text(errors="ignore")
    if "tool/" not in text:
        errors.append(
            "profiles/shared/.gitignore.fragment must ignore tool/"
            " — agent tooling is installed by the package manager, not committed by humans"
        )
    if ".mcp.json" not in text:
        errors.append(
            "profiles/shared/.gitignore.fragment must ignore .mcp.json"
            " — MCP settings are installed for local target runtime use"
        )


def main() -> int:
    errors: list[str] = []
    validate_required(errors)
    validate_forbidden_text(errors)
    validate_safe_datalake_controls(errors)
    validate_env_example(errors)
    validate_shared_scope(errors)
    validate_root_helper_mirrors(errors)
    validate_rule_mirrors(errors)
    validate_ps1_syntax(errors)
    validate_load_env_strips_comments(errors)
    validate_gitignore_fragment(errors)

    if errors:
        print("FAIL: install package validation failed")
        for item in errors:
            print(f"- {item}")
        return 1
    print("PASS: install package layout is vendor-native and aligned")
    return 0


if __name__ == "__main__":
    sys.exit(main())
