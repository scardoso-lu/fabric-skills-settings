#!/usr/bin/env python3
"""Validate vendor-native Fabric agent profile package layout."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROFILES = ROOT / "profiles"
SKILLS = {"fabric-ingest", "fabric-transform", "fabric-model", "fabric-validate", "fabric-notebook-loop", "fabric-ops"}
AGENTS = {"orchestrator", "developer", "tester", "operator"}
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
    require(PROFILES / "shared" / "project-layout" / "bin" / "build_fabric_notebooks.py", errors)
    require(PROFILES / "shared" / "project-layout" / "bin" / "fab-sandbox", errors)
    require(PROFILES / "shared" / "project-layout" / "bin" / "nbmon-sandbox", errors)
    require(PROFILES / "shared" / "project-layout" / "bin" / "smoke-test-sandbox.sh", errors)
    require(PROFILES / "shared" / "project-layout" / "bin" / "post-smoke-update.py", errors)

    codex_skills = skill_names(PROFILES / "codex" / "skills")
    claude_skills = skill_names(PROFILES / "claude" / "skills")
    if codex_skills != SKILLS:
        error(f"Codex skills mismatch: expected {sorted(SKILLS)}, found {sorted(codex_skills)}", errors)
    if claude_skills != SKILLS:
        error(f"Claude skills mismatch: expected {sorted(SKILLS)}, found {sorted(claude_skills)}", errors)
    if codex_skills != claude_skills:
        error("Codex and Claude skill names differ", errors)

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


def main() -> int:
    errors: list[str] = []
    validate_required(errors)
    validate_forbidden_text(errors)
    validate_env_example(errors)
    validate_shared_scope(errors)

    if errors:
        print("FAIL: install package validation failed")
        for item in errors:
            print(f"- {item}")
        return 1
    print("PASS: install package layout is vendor-native and aligned")
    return 0


if __name__ == "__main__":
    sys.exit(main())
