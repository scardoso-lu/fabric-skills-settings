#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Validate source-package guidance for the vendor-native installer setup."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_SKILLS = {
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
    require(ROOT / "profiles" / "shared" / "memory" / "MEMORY.md", errors)
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

    for path in [ROOT / "profiles" / "codex" / "AGENTS.md", ROOT / "profiles" / "claude" / "CLAUDE.md"]:
        if not path.exists():
            continue
        text = path.read_text(errors="ignore")
        for skill in REQUIRED_SKILLS:
            if f"`{skill}`" not in text:
                errors.append(f"{rel(path)} must list installed skill `{skill}`")


def validate_setup_guidance(errors: list[str]) -> None:
    required = [
        "tool\\setup\\setup.ps1",
        "tool/setup/setup.sh",
        "FABRIC_WORKSPACE_ID",
        "fab-sandbox auth login",
        "Do **not** read `.env` contents",
        "Setup incomplete",
    ]
    forbidden = [
        "FABRIC_WORKSPACE_ID` is missing",
        "If `bin/setup.sh`, `.env`, or `FABRIC_WORKSPACE_ID` is missing",
        "If `bin/setup.ps1`, `bin/setup.sh`, `.env`, or `FABRIC_WORKSPACE_ID` is missing",
    ]
    for path in [ROOT / "profiles" / "codex" / "AGENTS.md", ROOT / "profiles" / "claude" / "CLAUDE.md"]:
        if not path.exists():
            continue
        text = path.read_text(errors="ignore")
        for phrase in required:
            if phrase not in text:
                errors.append(f"missing setup guidance phrase {phrase!r} in {rel(path)}")
        for phrase in forbidden:
            if phrase in text:
                errors.append(f"setup guidance implies reading .env via {phrase!r} in {rel(path)}")

    codex = ROOT / "profiles" / "codex" / "AGENTS.md"
    if codex.exists():
        text = codex.read_text(errors="ignore")
        codex_required = [
            "Mandatory setup gate",
            "verify `.env`, `fab`, and `fab auth`",
            "before accepting any Fabric work",
        ]
        for phrase in codex_required:
            if phrase not in text:
                errors.append(f"missing Codex setup gate phrase {phrase!r} in {rel(codex)}")

    setup_autoload = ROOT / "docs" / "setup-autoload.md"
    if setup_autoload.exists():
        text = setup_autoload.read_text(errors="ignore")
        if "Runs mandatory setup gate" not in text:
            errors.append("docs/setup-autoload.md must show the Codex mandatory setup gate")
        if "(.env, fab, fab auth)" not in text:
            errors.append("docs/setup-autoload.md must name .env, fab, and fab auth in setup checks")


def validate_auth_network_guidance(errors: list[str]) -> None:
    """Auth-failure guidance must mention network restriction so agents don't treat firewalls as auth errors."""
    for path in [ROOT / "profiles" / "codex" / "AGENTS.md", ROOT / "profiles" / "claude" / "CLAUDE.md"]:
        if not path.exists():
            continue
        text = path.read_text(errors="ignore")
        if "network" not in text.lower():
            errors.append(
                f"auth failure row in {rel(path)} must mention network restriction"
                " — agents must not treat a firewall block as a permanent auth failure"
            )


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
        (
            ROOT / "docs" / "tooling-map.md",
            ["fabric-transform", "fabric-model", "fabric-validate", "DE-06", "FP-08", "DE-04"],
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


def validate_item_creation_guidance(errors: list[str]) -> None:
    """Guidance must distinguish what humans create (workspace/lakehouses) from what agents auto-create (notebooks/folders)."""
    for path in [ROOT / "profiles" / "codex" / "AGENTS.md", ROOT / "profiles" / "claude" / "CLAUDE.md"]:
        if not path.exists():
            continue
        text = path.read_text(errors="ignore")
        if "lakehouse" not in text.lower():
            errors.append(
                f"{rel(path)} must state that humans create lakehouses"
                " — missing item-creation boundary guidance"
            )
        if "notebook items" not in text and "notebook" not in text.lower():
            errors.append(
                f"{rel(path)} must clarify that agents may create notebook items automatically"
            )


def validate_no_root_runtime(errors: list[str]) -> None:
    for path in FORBIDDEN_ROOT_RUNTIME:
        if path.exists():
            errors.append(f"root runtime directory should not exist in source package: {rel(path)}")


def main() -> int:
    errors: list[str] = []
    validate_root_guidance(errors)
    validate_profiles(errors)
    validate_setup_guidance(errors)
    validate_auth_network_guidance(errors)
    validate_platform_rules_use_wrapper(errors)
    validate_skill_wiring(errors)
    validate_item_creation_guidance(errors)
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
