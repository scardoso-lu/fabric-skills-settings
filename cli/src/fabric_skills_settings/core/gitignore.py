"""Manage the `.gitignore` block fenced by `# BEGIN/END MANAGED BY ...` markers."""

from __future__ import annotations

from pathlib import Path

from .files import WriteOptions
from .markers import GITIGNORE_BEGIN, GITIGNORE_END
from .paths import profiles_root

_PROFILE_IGNORES: dict[str, list[str]] = {
    "shared": [],
    "codex": ["AGENTS.md", ".agents/", ".codex/"],
    "claude": ["CLAUDE.md", ".claude/"],
}


def merge_gitignore(target: Path, profiles: list[str], options: WriteOptions) -> str:
    src = profiles_root() / "shared" / ".gitignore.fragment"
    lines = [src.read_text(encoding="utf-8").rstrip()]
    profile_entries = [e for p in ["shared"] + profiles for e in _PROFILE_IGNORES.get(p, [])]
    if profile_entries:
        lines.append("\n# Installed agent profiles")
        lines.extend(profile_entries)
    fragment = "\n".join(lines)
    block = f"{GITIGNORE_BEGIN}\n{fragment}\n{GITIGNORE_END}\n"
    dest = target / ".gitignore"

    if options.check:
        if not dest.exists():
            return "MISSING .gitignore managed block"
        text = dest.read_text(encoding="utf-8", errors="ignore")
        return "OK .gitignore" if block in text else "DIFF .gitignore managed block"

    if dest.exists():
        text = dest.read_text(encoding="utf-8", errors="ignore")
        if block in text:
            return "UNCHANGED .gitignore"
        if GITIGNORE_BEGIN in text and GITIGNORE_END in text:
            before, rest = text.split(GITIGNORE_BEGIN, 1)
            _, after = rest.split(GITIGNORE_END, 1)
            new_text = before.rstrip() + "\n" + block + after.lstrip("\n")
        else:
            new_text = text.rstrip() + "\n\n" + block
        action = "UPDATE .gitignore"
    else:
        new_text = block
        action = "CREATE .gitignore"

    if options.dry_run:
        return action
    dest.write_text(new_text, encoding="utf-8")
    return action
