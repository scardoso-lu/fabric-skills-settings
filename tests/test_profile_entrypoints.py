"""Regression tests for installed Codex/Claude profile entrypoints."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CODEX_ENTRYPOINT = ROOT / "profiles" / "codex" / "AGENTS.md"
CLAUDE_ENTRYPOINT = ROOT / "profiles" / "claude" / "CLAUDE.md"
ROOT_AGENTS = ROOT / "AGENTS.md"
ROOT_CLAUDE = ROOT / "CLAUDE.md"
SKILLS_DIR = ROOT / "profiles" / "skills"


def _normalize_profile_text(text: str) -> str:
    replacements = {
        "Codex": "AGENT_RUNTIME",
        "Claude Code": "AGENT_RUNTIME",
        "Claude": "AGENT_RUNTIME",
        ".agents/skills": "SKILLS_PATH",
        ".claude/skills": "SKILLS_PATH",
        ".codex/agents/*.toml": "AGENTS_PATH",
        ".claude/agents/": "AGENTS_PATH",
        "repo skills": "project skills",
        "custom agents": "subagents",
        "manual `rtk` prefixes are AGENT_RUNTIME-specific": "runtime-specific RTK handling",
        "no manual command prefix is required": "runtime-specific RTK handling",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _profile_headings(path: Path) -> list[str]:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("## ")
    ]


def _installed_skill_names() -> set[str]:
    return {path.parent.name for path in SKILLS_DIR.glob("*/SKILL.md")}


def test_codex_and_claude_profile_entrypoints_have_same_layout():
    assert _profile_headings(CODEX_ENTRYPOINT) == _profile_headings(CLAUDE_ENTRYPOINT)


def test_codex_and_claude_profile_entrypoints_are_at_least_80_percent_similar():
    codex_text = _normalize_profile_text(CODEX_ENTRYPOINT.read_text(encoding="utf-8"))
    claude_text = _normalize_profile_text(CLAUDE_ENTRYPOINT.read_text(encoding="utf-8"))

    similarity = SequenceMatcher(None, codex_text, claude_text).ratio()

    assert similarity >= 0.80, f"profile entrypoint similarity is {similarity:.1%}"


def test_all_installed_skills_are_mentioned_in_skills_index_node():
    """Phase P4: skills list moved out of the hard-minimal profile into the
    graph-content/indexes/skills-index node. Profiles no longer mention skills."""
    skills_index = ROOT / "content" / "graph-content" / "indexes" / "skills-index.md"
    skill_names = _installed_skill_names()
    assert skill_names, "expected installed skills under profiles/skills"
    text = skills_index.read_text(encoding="utf-8")
    for skill_name in sorted(skill_names):
        assert f"`{skill_name}`" in text, f"{skill_name} missing from {skills_index.name}"


def test_root_agent_guidance_files_have_same_layout():
    assert _profile_headings(ROOT_AGENTS) == _profile_headings(ROOT_CLAUDE)


def test_root_agent_guidance_files_are_at_least_80_percent_similar():
    agents_text = _normalize_profile_text(ROOT_AGENTS.read_text(encoding="utf-8"))
    claude_text = _normalize_profile_text(ROOT_CLAUDE.read_text(encoding="utf-8"))

    similarity = SequenceMatcher(None, agents_text, claude_text).ratio()

    assert similarity >= 0.80, f"root guidance similarity is {similarity:.1%}"


def test_all_installed_skills_are_mentioned_in_both_root_guidance_files():
    skill_names = _installed_skill_names()
    assert skill_names, "expected installed skills under profiles/skills"

    agents_text = ROOT_AGENTS.read_text(encoding="utf-8")
    claude_text = ROOT_CLAUDE.read_text(encoding="utf-8")

    for skill_name in sorted(skill_names):
        assert f"`{skill_name}`" in agents_text, f"{skill_name} missing from root AGENTS.md"
        assert f"`{skill_name}`" in claude_text, f"{skill_name} missing from root CLAUDE.md"
