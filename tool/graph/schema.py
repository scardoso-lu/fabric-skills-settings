"""Node, Edge, frontmatter parser, and path -> id mapping for the graph."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

NODE_KINDS = frozenset(
    {
        "entry",
        "content",
        "skill",
        "rule",
        "memory",
        "skill-fix",
        "capability",
        "profile",
    }
)

EDGE_KINDS = frozenset({"curated", "auto-path", "capability-route", "capability-covers"})


@dataclass(frozen=True)
class Node:
    id: str
    path: str
    title: str
    description: str
    kind: str
    frontmatter: dict[str, Any]
    mtime: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "path": self.path,
            "title": self.title,
            "description": self.description,
            "kind": self.kind,
            "frontmatter": self.frontmatter,
            "mtime": self.mtime,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Node":
        return cls(
            id=data["id"],
            path=data["path"],
            title=data.get("title", ""),
            description=data.get("description", ""),
            kind=data.get("kind", "content"),
            frontmatter=dict(data.get("frontmatter") or {}),
            mtime=float(data.get("mtime", 0.0)),
        )


@dataclass(frozen=True)
class Edge:
    src: str
    dst: str
    kind: str

    def to_dict(self) -> dict[str, str]:
        return {"src": self.src, "dst": self.dst, "kind": self.kind}

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> "Edge":
        return cls(src=data["src"], dst=data["dst"], kind=data.get("kind", "curated"))


_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)", re.DOTALL)


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Minimal YAML-ish frontmatter parser.

    Handles scalars, quoted strings, lists of strings ('- item' lines),
    and one level of nested mapping (flattened to 'parent.child' keys).
    Comments (# ...) and blank lines are ignored. Anything more exotic
    (tags, anchors, flow style, multi-doc) is unsupported on purpose —
    this graph package owns the frontmatter contract.
    """
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    fm_text, body = match.group(1), match.group(2)
    data: dict[str, Any] = {}
    open_list_key: str | None = None
    open_list: list[str] | None = None
    open_map_key: str | None = None
    for raw in fm_text.splitlines():
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        if open_list is not None and indent >= 2 and stripped.startswith("- "):
            open_list.append(_strip_quotes(stripped[2:].strip()))
            continue
        if open_list is not None:
            data[open_list_key] = open_list  # type: ignore[index]
            open_list = None
            open_list_key = None
        if open_map_key is not None and indent >= 2 and ":" in stripped:
            sub_key, _, sub_val = stripped.partition(":")
            data[f"{open_map_key}.{sub_key.strip()}"] = _strip_quotes(sub_val.strip())
            continue
        if indent == 0:
            open_map_key = None
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if val == "":
            open_list_key = key
            open_list = []
            open_map_key = key
        else:
            data[key] = _strip_quotes(val)
            open_list_key = None
            open_list = None
            open_map_key = None
    if open_list is not None and open_list_key is not None:
        data[open_list_key] = open_list
    return data, body


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        return value[1:-1]
    return value


_H1_RE = re.compile(r"^\s*#\s+(.+?)\s*$", re.MULTILINE)


def first_h1(body: str) -> str:
    m = _H1_RE.search(body)
    return m.group(1).strip() if m else ""


_PATH_PREFIX_TO_ID: tuple[tuple[str, str], ...] = (
    # Target-repo layout (memory/ is the runtime root).
    ("memory/graph-content/", "graph-content/"),
    ("memory/rules/", "rules/"),
    ("memory/skill-fixes/", "skill-fixes/"),
    ("memory/", "memory/"),
    # Source-package layout (content/ is the single source).
    ("content/graph-content/", "graph-content/"),
    ("content/rules/", "rules/"),
    ("profiles/shared/memory/", "memory/"),
    # Bare canonical-id prefixes — prose often references these directly
    # ("rules/security.md", "graph-content/entry.md") without a parent path.
    ("rules/", "rules/"),
    ("graph-content/", "graph-content/"),
    ("skill-fixes/", "skill-fixes/"),
)


def id_from_path(repo_relative: str) -> str | None:
    """Map a repo-relative .md path to its canonical node id.

    Returns None if the path is not in an indexed location.
    """
    p = repo_relative.replace("\\", "/")
    if not p.endswith(".md"):
        return None
    base = p[:-3]

    parts = base.split("/")
    if "skills" in parts:
        idx = parts.index("skills")
        if (
            idx + 3 < len(parts)
            and parts[idx + 2] == "sections"
        ):
            return f"skills/{parts[idx + 1]}/{parts[idx + 3]}"
        if parts[-1] == "SKILL" and idx + 1 < len(parts) and parts[idx + 2] == "SKILL":
            return f"skills/{parts[idx + 1]}"

    for prefix, replacement in _PATH_PREFIX_TO_ID:
        if base.startswith(prefix):
            rest = base[len(prefix):]
            return f"{replacement}{rest}".rstrip("/")
    return None


def kind_for_id(node_id: str, frontmatter: dict[str, Any] | None = None) -> str:
    """Infer node kind from its id prefix and optional frontmatter hint."""
    fm_kind = (frontmatter or {}).get("kind") or (frontmatter or {}).get("metadata.type")
    if isinstance(fm_kind, str) and fm_kind in NODE_KINDS:
        return fm_kind
    if node_id == "graph-content/entry":
        return "entry"
    if node_id.startswith("graph-content/"):
        return "content"
    if node_id.startswith("skills/"):
        return "skill"
    if node_id.startswith("rules/"):
        return "rule"
    if node_id.startswith("skill-fixes/"):
        return "skill-fix"
    return "memory"
