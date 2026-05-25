"""Discover markdown files, parse them, and assemble a graph."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .extract import extract_paths
from .schema import Edge, Node, first_h1, id_from_path, kind_for_id
from .store import GraphStore

DISCOVER_PATTERNS: tuple[tuple[str, str], ...] = (
    # Source-package layout (this repo): content/ is the single source of truth.
    ("content/graph-content/**/*.md", "content"),
    ("content/rules/*.md", "rule"),
    ("profiles/skills/*/SKILL.md", "skill"),
    ("profiles/skills/*/sections/*.md", "content"),
    # Target-repo layout: installer mirrors content/ into memory/.
    ("memory/graph-content/**/*.md", "content"),
    ("memory/rules/*.md", "rule"),
    ("memory/skill-fixes/*.md", "skill-fix"),
    (".claude/skills/*/SKILL.md", "skill"),
    (".claude/skills/*/sections/*.md", "content"),
    (".agents/skills/*/SKILL.md", "skill"),
    (".agents/skills/*/sections/*.md", "content"),
)

SKIP_NAME_PARTS: frozenset[str] = frozenset(
    {".venv", "__pycache__", ".graph", "node_modules", ".git"}
)


@dataclass
class BuildResult:
    store: GraphStore
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


def _read_markdown(path: Path) -> tuple[dict, str]:
    from .schema import parse_frontmatter

    text = path.read_text(encoding="utf-8", errors="ignore")
    return parse_frontmatter(text)


def _discover(root: Path) -> list[Path]:
    """Walk DISCOVER_PATTERNS in declared order; sort within each pattern for determinism.

    The pattern order is meaningful: when two paths resolve to the same node id,
    the source-of-truth pattern listed first wins.
    """
    found: list[Path] = []
    seen: set[Path] = set()
    for pattern, _ in DISCOVER_PATTERNS:
        matches: list[Path] = []
        for match in root.glob(pattern):
            if not match.is_file():
                continue
            if any(part in SKIP_NAME_PARTS for part in match.parts):
                continue
            resolved = match.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            matches.append(match)
        found.extend(sorted(matches))
    return found


def build(root: Path, *, built_by: str = "bin/build-graph.py") -> BuildResult:
    """Walk DISCOVER_PATTERNS under `root`, parse each file, and return a populated GraphStore."""
    root = root.resolve()
    store = GraphStore()
    result = BuildResult(store=store)

    by_id: dict[str, Path] = {}
    bodies: dict[str, str] = {}
    seen_ids: set[str] = set()

    for path in _discover(root):
        repo_rel = path.relative_to(root).as_posix()
        node_id = id_from_path(repo_rel)
        if node_id is None:
            result.skipped.append(repo_rel)
            continue
        if node_id in seen_ids:
            existing = by_id[node_id].relative_to(root).as_posix()
            result.warnings.append(
                f"duplicate node id {node_id!r}: keeping {existing}, skipping {repo_rel}"
            )
            continue
        try:
            frontmatter, body = _read_markdown(path)
        except OSError as exc:
            result.errors.append(f"read failed for {repo_rel}: {exc}")
            continue
        title = first_h1(body) or frontmatter.get("name", "") or node_id
        description = frontmatter.get("description", "")
        kind = kind_for_id(node_id, frontmatter)
        node = Node(
            id=node_id,
            path=repo_rel,
            title=title,
            description=description,
            kind=kind,
            frontmatter=frontmatter,
            mtime=path.stat().st_mtime,
        )
        store.add_node(node)
        seen_ids.add(node_id)
        by_id[node_id] = path
        bodies[node_id] = body

    for node_id, body in bodies.items():
        for mention in extract_paths(body):
            target_id = id_from_path(mention)
            if target_id and store.has_node(target_id) and target_id != node_id:
                store.add_edge(Edge(src=node_id, dst=target_id, kind="auto-path"))

    for node_id, _ in by_id.items():
        node = store.get_node(node_id)
        links = node.frontmatter.get("links") or []
        if isinstance(links, str):
            links = [links]
        for raw in links:
            target_id = _resolve_link(raw, store)
            if target_id is None:
                result.errors.append(
                    f"unresolved curated link from {node_id}: {raw!r}"
                )
                continue
            if target_id == node_id:
                continue
            store.add_edge(Edge(src=node_id, dst=target_id, kind="curated"))

    for orphan in store.orphans():
        result.warnings.append(f"orphan node: {orphan}")

    return result


def _resolve_link(raw: str, store: GraphStore) -> str | None:
    """Resolve a frontmatter `links:` entry to a node id.

    Accepts either a bare node id (e.g. 'rules/data-engineering') or a repo-relative path
    (e.g. 'memory/skill-fixes/foo.md').
    """
    if store.has_node(raw):
        return raw
    candidate = id_from_path(raw)
    if candidate and store.has_node(candidate):
        return candidate
    return None
