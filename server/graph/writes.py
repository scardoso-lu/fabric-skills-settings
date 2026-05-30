"""CRUD writes for the knowledge graph.

Each operation:
  1. acquires an exclusive lock on memory/.graph/graph.lock
  2. writes/updates/deletes the .md file atomically (tmp + rename)
  3. rebuilds the full graph from disk via builder.build()
  4. saves graph.json + BM25 pickle atomically
  5. releases the lock

This is simple and correct: the file system is the source of truth, the graph
is a derived artifact. We pay a full rebuild on every write — fine for the
~50-file corpus this profile pack targets. Optimize later if needed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .builder import build
from .lock import file_lock
from .schema import id_from_path
from .search import build_bm25_index, save_index
from .store import GraphStore


@dataclass
class WriteResult:
    node_id: str
    path: str
    action: str
    nodes: int
    edges: int


def _graph_paths(root: Path) -> tuple[Path, Path, Path]:
    """Return (lock, graph.json, graph-bm25.json) paths.

    Honors FABRIC_GRAPH_DIR if set; otherwise defaults to <root>/dist/.graph
    in the new server-only layout. Older target-repo callers should pass the
    root and rely on FABRIC_GRAPH_DIR being unset (legacy memory/.graph dir
    is no longer the default).
    """
    import os as _os
    override = _os.environ.get("FABRIC_GRAPH_DIR")
    graph_dir = Path(override) if override else (root / "dist" / ".graph")
    return (
        graph_dir / "graph.lock",
        graph_dir / "graph.json",
        graph_dir / "graph-bm25.json",
    )


_KIND_PATH_TEMPLATES: dict[str, str] = {
    "graph-content": "server/content/{rest}.md",
    "rule": "server/content/rules/{name}.md",
    "rules": "server/content/rules/{name}.md",
    "skill-fix": "server/content/skill-fixes/{name}.md",
    "skill-fixes": "server/content/skill-fixes/{name}.md",
    "memory": "server/content/memory/{rest}.md",
}


def _validate_id_segments(node_id: str) -> None:
    normalized = node_id.replace("\\", "/")
    if normalized != node_id:
        raise ValueError(f"node id contains invalid path separator: {node_id!r}")
    if normalized.startswith("/") or ":" in normalized:
        raise ValueError(f"node id must be repo-relative: {node_id!r}")
    parts = normalized.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"node id contains invalid path segment: {node_id!r}")


def _resolve_graph_path(root: Path, rel_path: str) -> Path:
    normalized = rel_path.replace("\\", "/")
    path = Path(normalized)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"path must be a safe repo-relative path: {rel_path!r}")
    if id_from_path(normalized) is None:
        raise ValueError(f"path is not in an indexed graph location: {rel_path!r}")
    resolved_root = root.resolve()
    target = (resolved_root / normalized).resolve()
    if not target.is_relative_to(resolved_root):
        raise ValueError(f"path escapes repository root: {rel_path!r}")
    return target


def default_path_for_id(node_id: str) -> str:
    """Map a node id to its canonical repo-relative path in a target repo."""
    _validate_id_segments(node_id)
    prefix, _, rest = node_id.partition("/")
    if prefix in _KIND_PATH_TEMPLATES:
        template = _KIND_PATH_TEMPLATES[prefix]
        if "{rest}" in template:
            return template.format(rest=rest)
        return template.format(name=rest)
    if prefix == "skills" and "/" not in rest:
        return f"server/skills/{rest}/SKILL.md"
    raise ValueError(f"no default path for node id prefix {prefix!r}")


def _serialize_frontmatter(frontmatter: dict[str, Any], links: list[str] | None) -> str:
    """Serialize a frontmatter dict back to YAML-ish front matter.

    Supports the same subset as parse_frontmatter: scalars, quoted strings,
    one-level mapping (dotted keys), and lists of strings under `links:`.
    """
    if not frontmatter and not links:
        return ""
    lines: list[str] = ["---"]
    seen_keys: set[str] = set()
    nested: dict[str, list[tuple[str, Any]]] = {}
    flat: list[tuple[str, Any]] = []
    for k, v in frontmatter.items():
        if "." in k:
            parent, _, child = k.partition(".")
            nested.setdefault(parent, []).append((child, v))
        else:
            flat.append((k, v))
    for k, v in flat:
        if k == "links":
            continue
        if isinstance(v, str):
            lines.append(f"{k}: {_quote_if_needed(v)}")
        elif isinstance(v, list):
            lines.append(f"{k}:")
            for item in v:
                lines.append(f"  - {item}")
        seen_keys.add(k)
    for parent, children in nested.items():
        if parent in seen_keys:
            continue
        lines.append(f"{parent}:")
        for child_k, child_v in children:
            lines.append(f"  {child_k}: {_quote_if_needed(str(child_v))}")
    if links is not None:
        lines.append("links:")
        for target in links:
            lines.append(f"  - {target}")
    elif "links" in frontmatter and isinstance(frontmatter["links"], list):
        lines.append("links:")
        for target in frontmatter["links"]:
            lines.append(f"  - {target}")
    lines.append("---")
    return "\n".join(lines) + "\n\n"


def _quote_if_needed(value: str) -> str:
    needs_quoting = (
        ":" in value
        or '"' in value
        or "\\" in value
        or value.startswith("#")
        or value.strip() != value
    )
    if needs_quoting:
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _rebuild_and_save(root: Path) -> tuple[GraphStore, int, int]:
    result = build(root)
    if result.errors:
        raise RuntimeError(
            "graph build failed after write: " + "; ".join(result.errors)
        )
    _, graph_path, bm25_path = _graph_paths(root)
    result.store.save(graph_path, built_by="fabric-graph:graph_write")
    bodies = _read_bodies(root, result.store)
    save_index(bm25_path, build_bm25_index(result.store, bodies))
    return result.store, result.store.graph.number_of_nodes(), result.store.graph.number_of_edges()


def _read_bodies(root: Path, store: GraphStore) -> dict[str, str]:
    from .schema import parse_frontmatter

    out: dict[str, str] = {}
    for nid in store.graph.nodes:
        rel = store.graph.nodes[nid]["path"]
        try:
            text = (root / rel).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        _, body = parse_frontmatter(text)
        out[nid] = body
    return out


def create_node(
    root: Path,
    *,
    node_id: str,
    body: str,
    frontmatter: dict[str, Any] | None = None,
    links: list[str] | None = None,
    path: str | None = None,
) -> WriteResult:
    """Author a new node. Fails if the id already exists."""
    lock_path, graph_path, _ = _graph_paths(root)
    with file_lock(lock_path):
        if graph_path.exists():
            store = GraphStore.load(graph_path)
            if store.has_node(node_id):
                raise ValueError(f"node id already exists: {node_id}")
        rel_path = path or default_path_for_id(node_id)
        target = _resolve_graph_path(root, rel_path)
        if id_from_path(rel_path) != node_id:
            raise ValueError(
                f"path {rel_path!r} does not map to node id {node_id!r}"
            )
        if target.exists():
            raise ValueError(f"file already exists: {rel_path}")
        fm = dict(frontmatter or {})
        content = _serialize_frontmatter(fm, links) + body.lstrip("\n")
        if not content.endswith("\n"):
            content += "\n"
        _atomic_write(target, content)
        _, nodes, edges = _rebuild_and_save(root)
    return WriteResult(node_id=node_id, path=rel_path, action="created", nodes=nodes, edges=edges)


def update_node(
    root: Path,
    *,
    node_id: str,
    body: str | None = None,
    frontmatter: dict[str, Any] | None = None,
) -> WriteResult:
    """Update an existing node's body and/or frontmatter."""
    from .schema import parse_frontmatter

    lock_path, graph_path, _ = _graph_paths(root)
    with file_lock(lock_path):
        if not graph_path.exists():
            raise RuntimeError("graph not built")
        store = GraphStore.load(graph_path)
        if not store.has_node(node_id):
            raise ValueError(f"unknown node: {node_id}")
        rel_path = store.graph.nodes[node_id]["path"]
        target = _resolve_graph_path(root, rel_path)
        existing = target.read_text(encoding="utf-8")
        existing_fm, existing_body = parse_frontmatter(existing)
        new_fm = dict(existing_fm)
        if frontmatter is not None:
            new_fm.update(frontmatter)
        new_body = body if body is not None else existing_body
        links = new_fm.pop("links", None) if isinstance(new_fm.get("links"), list) else None
        if frontmatter and "links" in frontmatter and isinstance(frontmatter["links"], list):
            links = frontmatter["links"]
        content = _serialize_frontmatter(new_fm, links) + new_body.lstrip("\n")
        if not content.endswith("\n"):
            content += "\n"
        _atomic_write(target, content)
        _, nodes, edges = _rebuild_and_save(root)
    return WriteResult(node_id=node_id, path=rel_path, action="updated", nodes=nodes, edges=edges)


def delete_node(
    root: Path,
    *,
    node_id: str,
    allow_orphans: bool = False,
) -> WriteResult:
    """Delete a node. Refuses if other nodes have curated edges pointing at it,
    unless allow_orphans=True (cascades — the curated links from other files
    become unresolved, which the next build will flag as errors)."""
    lock_path, graph_path, _ = _graph_paths(root)
    with file_lock(lock_path):
        if not graph_path.exists():
            raise RuntimeError("graph not built")
        store = GraphStore.load(graph_path)
        if not store.has_node(node_id):
            raise ValueError(f"unknown node: {node_id}")
        inbound_curated = [
            src
            for src in store.graph.predecessors(node_id)
            if store.graph.get_edge_data(src, node_id).get("kind") == "curated"
        ]
        if inbound_curated and not allow_orphans:
            raise ValueError(
                f"refusing to delete {node_id}: curated links from "
                + ", ".join(sorted(inbound_curated))
                + " (re-run with allow_orphans=True to override)"
            )
        rel_path = store.graph.nodes[node_id]["path"]
        target = _resolve_graph_path(root, rel_path)
        if target.exists():
            target.unlink()
        if allow_orphans:
            for src in inbound_curated:
                _remove_curated_link_from_file(root, store, src, node_id)
        _, nodes, edges = _rebuild_and_save(root)
    return WriteResult(node_id=node_id, path=rel_path, action="deleted", nodes=nodes, edges=edges)


def add_edge(
    root: Path,
    *,
    src: str,
    dst: str,
) -> WriteResult:
    """Add a curated edge by updating the src node's `links:` frontmatter."""
    lock_path, graph_path, _ = _graph_paths(root)
    with file_lock(lock_path):
        if not graph_path.exists():
            raise RuntimeError("graph not built")
        store = GraphStore.load(graph_path)
        if not store.has_node(src):
            raise ValueError(f"unknown src node: {src}")
        if not store.has_node(dst):
            raise ValueError(f"unknown dst node: {dst}")
        if src == dst:
            raise ValueError("cannot add a self-edge")
        _add_curated_link_to_file(root, store, src, dst)
        _, nodes, edges = _rebuild_and_save(root)
    return WriteResult(node_id=src, path=store.graph.nodes[src]["path"], action="edge-added", nodes=nodes, edges=edges)


def remove_edge(
    root: Path,
    *,
    src: str,
    dst: str,
) -> WriteResult:
    """Remove a curated edge. Auto edges can only be removed by editing prose."""
    lock_path, graph_path, _ = _graph_paths(root)
    with file_lock(lock_path):
        if not graph_path.exists():
            raise RuntimeError("graph not built")
        store = GraphStore.load(graph_path)
        if not store.has_node(src):
            raise ValueError(f"unknown src node: {src}")
        edge = store.graph.get_edge_data(src, dst)
        if edge is None:
            raise ValueError(f"no edge {src} -> {dst}")
        if edge.get("kind") != "curated":
            raise ValueError(
                f"edge {src} -> {dst} is {edge.get('kind')!r}, not curated; "
                "auto edges must be removed by editing the prose that mentions the target"
            )
        _remove_curated_link_from_file(root, store, src, dst)
        _, nodes, edges = _rebuild_and_save(root)
    return WriteResult(node_id=src, path=store.graph.nodes[src]["path"], action="edge-removed", nodes=nodes, edges=edges)


def _add_curated_link_to_file(root: Path, store: GraphStore, src: str, dst: str) -> None:
    from .schema import parse_frontmatter

    rel_path = store.graph.nodes[src]["path"]
    target = _resolve_graph_path(root, rel_path)
    text = target.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)
    existing_links = fm.get("links") or []
    if isinstance(existing_links, str):
        existing_links = [existing_links]
    if dst in existing_links:
        return
    fm["links"] = list(existing_links) + [dst]
    content = _serialize_frontmatter({k: v for k, v in fm.items() if k != "links"}, fm["links"]) + body.lstrip("\n")
    if not content.endswith("\n"):
        content += "\n"
    _atomic_write(target, content)


def _remove_curated_link_from_file(root: Path, store: GraphStore, src: str, dst: str) -> None:
    from .schema import parse_frontmatter

    rel_path = store.graph.nodes[src]["path"]
    target = _resolve_graph_path(root, rel_path)
    text = target.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(text)
    existing_links = fm.get("links") or []
    if isinstance(existing_links, str):
        existing_links = [existing_links]
    new_links = [link for link in existing_links if link != dst]
    if new_links == existing_links:
        return
    if new_links:
        fm["links"] = new_links
        content = _serialize_frontmatter({k: v for k, v in fm.items() if k != "links"}, new_links) + body.lstrip("\n")
    else:
        fm.pop("links", None)
        content = _serialize_frontmatter(fm, None) + body.lstrip("\n")
    if not content.endswith("\n"):
        content += "\n"
    _atomic_write(target, content)
