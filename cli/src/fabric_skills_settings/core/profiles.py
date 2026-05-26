"""Enumerate source files that ship into a target repo for each profile.

Each helper returns a list of `(source, target_rel, managed)` tuples consumed
by the install/check commands.

Skills are NOT enumerated here: they live on the MCP server and are accessed
by Claude through `graph_get_node('skills/<name>')`.
"""

from __future__ import annotations

from pathlib import Path

from .paths import profiles_root


def collect_profile_files(profile: str) -> list[tuple[Path, Path, bool]]:
    if profile not in {"codex", "claude"}:
        raise ValueError(f"Unknown profile: {profile}")
    profiles = profiles_root()
    entries: list[tuple[Path, Path, bool]] = []
    if profile == "codex":
        entries.append((profiles / "codex" / "AGENTS.md", Path("AGENTS.md"), True))
        entries.append((profiles / "codex" / "config.toml", Path(".codex/config.toml"), False))
        for src in sorted((profiles / "codex" / "agents").glob("*.toml")):
            entries.append((src, Path(".codex/agents") / src.name, False))
    else:
        entries.append((profiles / "claude" / "CLAUDE.md", Path("CLAUDE.md"), True))
        entries.append((profiles / "claude" / "settings.local.json", Path(".claude/settings.local.json"), False))
        for src in sorted((profiles / "claude" / "agents").glob("*.md")):
            entries.append((src, Path(".claude/agents") / src.name, True))
    return entries


def collect_shared_files() -> list[tuple[Path, Path, bool]]:
    """Scaffold files plus the .env.example template."""
    entries: list[tuple[Path, Path, bool]] = []
    shared = profiles_root() / "shared"
    scaffold = shared / "scaffold"
    if scaffold.is_dir():
        for src in sorted(scaffold.rglob("*")):
            if src.is_file() and "__pycache__" not in src.parts and src.suffix not in {".pyc", ".pyo", ".pyd"}:
                entries.append((src, src.relative_to(scaffold), False))
    entries.append((shared / ".env.example", Path(".env.example"), False))
    return entries


def planned_profiles(profile: str) -> list[str]:
    if profile == "all":
        return ["codex", "claude"]
    return [profile]
