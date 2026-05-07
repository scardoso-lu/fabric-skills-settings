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
    require(ROOT / "profiles" / "claude" / "settings.json", errors)
    require(ROOT / "profiles" / "shared" / "memory" / "MEMORY.md", errors)

    codex_skills = skill_names(ROOT / "profiles" / "codex" / "skills")
    claude_skills = skill_names(ROOT / "profiles" / "claude" / "skills")
    if codex_skills != REQUIRED_SKILLS:
        errors.append(f"Codex skill set mismatch: {sorted(codex_skills)}")
    if claude_skills != REQUIRED_SKILLS:
        errors.append(f"Claude skill set mismatch: {sorted(claude_skills)}")
    if codex_skills != claude_skills:
        errors.append("Codex and Claude profile skills differ")

    codex_agents = agent_names(ROOT / "profiles" / "codex" / "agents", ".toml")
    claude_agents = agent_names(ROOT / "profiles" / "claude" / "agents", ".md")
    if codex_agents != REQUIRED_AGENTS:
        errors.append(f"Codex agent set mismatch: {sorted(codex_agents)}")
    if claude_agents != REQUIRED_AGENTS:
        errors.append(f"Claude agent set mismatch: {sorted(claude_agents)}")
    if codex_agents != claude_agents:
        errors.append("Codex and Claude profile agents differ")


def validate_no_root_runtime(errors: list[str]) -> None:
    for path in FORBIDDEN_ROOT_RUNTIME:
        if path.exists():
            errors.append(f"root runtime directory should not exist in source package: {rel(path)}")


def main() -> int:
    errors: list[str] = []
    validate_root_guidance(errors)
    validate_profiles(errors)
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
