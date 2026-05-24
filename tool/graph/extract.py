"""Auto-edge extraction from markdown prose.

Per the locked decision in plan.md (§4 #11), the only auto-edge source is raw
path mentions like `memory/skill-fixes/foo.md` or `profiles/skills/bar/SKILL.md`.
Wiki-link syntax (`[[name]]`) is intentionally not supported — curated edges
live in frontmatter `links:` instead.
"""

from __future__ import annotations

import re

_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`]*`")
_PATH_RE = re.compile(r"[A-Za-z0-9_./-]+?\.md\b")


def strip_code(text: str) -> str:
    """Remove fenced code blocks and inline code spans so example paths don't leak in as edges."""
    text = _FENCE_RE.sub("", text)
    text = _INLINE_CODE_RE.sub("", text)
    return text


def extract_paths(body: str) -> list[str]:
    """Return the set of `.md` path references in `body`, in first-occurrence order, excluding code regions."""
    stripped = strip_code(body)
    seen: dict[str, None] = {}
    for match in _PATH_RE.finditer(stripped):
        candidate = match.group(0)
        if candidate.startswith("./"):
            candidate = candidate[2:]
        segments = candidate.split("/")
        if any(seg == ".." for seg in segments):
            continue
        seen.setdefault(candidate, None)
    return list(seen.keys())
