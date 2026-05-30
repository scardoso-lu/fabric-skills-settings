"""FastMCP wrappers for the knowledge-graph tools.

Logic ported from the legacy ``mcp/graph-server.py``. The graph runtime
modules under ``tool/graph/`` are reused unchanged — only the transport
layer (FastMCP HTTP instead of hand-rolled stdio JSON-RPC) is new.

Graph data lives under ``$FABRIC_PROJECT_ROOT/memory/.graph/`` (mounted
into the container at ``/data/memory/.graph/``). The graph is rebuilt
atomically by ``tool/graph/writes.py`` on every write call.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from ...audit import CallTimer
from ...graph.schema import parse_frontmatter
from ...graph.search import BM25Index, build_bm25_index, load_index, search
from ...graph.store import GraphStore
from ...graph import writes as graph_writes

# Where to read the graph artifact + node markdown bodies from at runtime.
# Local dev: _PROJECT_ROOT defaults to the repo root (one level above server/);
#            FABRIC_GRAPH_DIR defaults to <repo>/dist/.graph.
# Docker:    FABRIC_PROJECT_ROOT and FABRIC_GRAPH_DIR are both set by the
#            Dockerfile so source-relative node paths and the graph artifact
#            both resolve correctly inside the container.
_DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[3]  # server/tools/graph/tools.py → repo root
_PROJECT_ROOT = Path(os.environ.get("FABRIC_PROJECT_ROOT") or _DEFAULT_PROJECT_ROOT).resolve()

GRAPH_DIR = Path(os.environ.get("FABRIC_GRAPH_DIR") or (_PROJECT_ROOT / "dist" / ".graph")).resolve()
GRAPH_PATH = GRAPH_DIR / "graph.json"
BM25_PATH = GRAPH_DIR / "graph-bm25.json"
ENTRY_NODE_ID = "graph-content/entry"

_store: GraphStore | None = None
_index: BM25Index | None = None
_index_mtime: float = 0.0


def _load_graph() -> GraphStore:
    global _store
    if _store is None:
        if not GRAPH_PATH.exists():
            raise RuntimeError(
                f"graph not built: {GRAPH_PATH} missing — install the project content "
                "into FABRIC_PROJECT_ROOT (mounted at /data)."
            )
        _store = GraphStore.load(GRAPH_PATH)
    return _store


def _load_search_index(store: GraphStore) -> BM25Index:
    global _index, _index_mtime
    if BM25_PATH.exists():
        mtime = BM25_PATH.stat().st_mtime
        if _index is None or mtime != _index_mtime:
            _index = load_index(BM25_PATH)
            _index_mtime = mtime
        return _index
    if _index is None:
        _index = build_bm25_index(store, _read_all_bodies(store))
    return _index


def _read_body(rel_path: str) -> str:
    try:
        text = (_PROJECT_ROOT / rel_path).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
    _, body = parse_frontmatter(text)
    return body


def _read_all_bodies(store: GraphStore) -> dict[str, str]:
    return {nid: _read_body(store.graph.nodes[nid]["path"]) for nid in store.graph.nodes}


def _node_payload(store: GraphStore, node_id: str, *, include_body: bool) -> dict[str, Any]:
    data = store.graph.nodes[node_id]
    out: dict[str, Any] = {
        "id": node_id,
        "title": data.get("title", node_id),
        "description": data.get("description", ""),
        "kind": data.get("kind", "content"),
        "path": data.get("path", ""),
        "links": sorted(store.graph.successors(node_id)),
    }
    if include_body:
        out["body"] = _read_body(data["path"])
    return out


def _invalidate_caches() -> None:
    global _store, _index, _index_mtime
    _store = None
    _index = None
    _index_mtime = 0.0


def _result_payload(result) -> dict[str, Any]:
    return {
        "id": result.node_id,
        "path": result.path,
        "action": result.action,
        "nodes": result.nodes,
        "edges": result.edges,
    }


def register(mcp: FastMCP) -> None:
    """Register all 9 graph tools on the given FastMCP app."""

    # ── Read surface ──────────────────────────────────────────────────────────

    @mcp.tool()
    def graph_get_entry() -> str:
        """Return the root entry node of the project knowledge graph.

        MUST be the first call in any session. The entry node contains the
        mandatory setup gate and links to the rest of the graph.
        """
        with CallTimer("graph_get_entry", {}) as t:
            store = _load_graph()
            if not store.has_node(ENTRY_NODE_ID):
                raise RuntimeError(
                    f"entry node {ENTRY_NODE_ID!r} not present in graph — "
                    "content tree may not be installed yet"
                )
            t.ok()
            return json.dumps(_node_payload(store, ENTRY_NODE_ID, include_body=True), indent=2)

    @mcp.tool()
    def graph_get_node(id: str) -> str:
        """Return the full content of one node by id, including its body and outbound link ids.

        Only call with ids returned by graph_get_entry, graph_get_linked, or graph_search.
        """
        with CallTimer("graph_get_node", {"id": id}) as t:
            node_id = id.strip()
            if not node_id:
                raise RuntimeError("graph_get_node requires 'id'")
            store = _load_graph()
            if not store.has_node(node_id):
                raise RuntimeError(f"unknown node id: {node_id!r}")
            t.ok()
            return json.dumps(_node_payload(store, node_id, include_body=True), indent=2)

    @mcp.tool()
    def graph_get_linked(id: str, kinds: list[str] | None = None) -> str:
        """Return the 1-hop neighbours (outbound edges) of a node.

        Use to traverse the graph after reading a node's body. Optionally
        filter neighbours by node kind (e.g. ['rule', 'skill']).
        """
        with CallTimer("graph_get_linked", {"id": id, "kinds": kinds}) as t:
            node_id = id.strip()
            if not node_id:
                raise RuntimeError("graph_get_linked requires 'id'")
            store = _load_graph()
            if not store.has_node(node_id):
                raise RuntimeError(f"unknown node id: {node_id!r}")
            neighbors = []
            for neighbor in sorted(store.graph.successors(node_id)):
                data = store.graph.nodes[neighbor]
                edge_kind = store.graph.get_edge_data(node_id, neighbor).get("kind", "curated")
                kind = data.get("kind", "content")
                if kinds and kind not in kinds:
                    continue
                neighbors.append({
                    "id": neighbor,
                    "title": data.get("title", neighbor),
                    "description": data.get("description", ""),
                    "kind": kind,
                    "edge_kind": edge_kind,
                })
            t.ok()
            return json.dumps({"id": node_id, "neighbors": neighbors}, indent=2)

    @mcp.tool()
    def graph_search(query: str, k: int = 5) -> str:
        """BM25 search across the graph with a 1-hop edge-aware re-rank. k clamped to [1, 25]."""
        with CallTimer("graph_search", {"query": query, "k": k}) as t:
            q = query.strip()
            if not q:
                raise RuntimeError("graph_search requires non-empty 'query'")
            k = max(1, min(int(k), 25))
            store = _load_graph()
            index = _load_search_index(store)
            hits = search(store, index, q, k=k)
            t.ok()
            return json.dumps({
                "query": q,
                "hits": [
                    {"id": h.id, "title": h.title, "score": h.score, "why_matched": h.why_matched}
                    for h in hits
                ],
            }, indent=2)

    @mcp.tool()
    def graph_list_kinds() -> str:
        """Return node-kind counts plus total node/edge counts in the graph."""
        with CallTimer("graph_list_kinds", {}) as t:
            store = _load_graph()
            t.ok()
            return json.dumps({
                "counts": store.kinds(),
                "total": store.graph.number_of_nodes(),
                "edges": store.graph.number_of_edges(),
            }, indent=2)

    # ── Write surface ─────────────────────────────────────────────────────────
    # Every write goes through tool/graph/writes.py which:
    #   1. acquires an exclusive lock on memory/.graph/graph.lock
    #   2. writes the source markdown file
    #   3. rebuilds graph.json + graph-bm25.pkl atomically

    @mcp.tool()
    def graph_create_node(
        id: str,
        body: str,
        frontmatter: dict | None = None,
        links: list[str] | None = None,
        path: str | None = None,
    ) -> str:
        """Create a new node. frontmatter is merged into the new file's YAML head; links is
        a list of canonical node ids to add as curated outbound edges; path overrides the
        default target file location."""
        args = {"id": id, "frontmatter": frontmatter, "links": links, "path": path}
        with CallTimer("graph_create_node", args) as t:
            node_id = id.strip()
            if not node_id or not body:
                raise RuntimeError("graph_create_node requires 'id' and 'body'")
            fm = frontmatter or {}
            if not isinstance(fm, dict):
                raise RuntimeError("'frontmatter' must be an object")
            result = graph_writes.create_node(
                _PROJECT_ROOT,
                node_id=node_id,
                body=body,
                frontmatter=fm,
                links=list(links) if links else None,
                path=str(path) if path else None,
            )
            _invalidate_caches()
            t.ok()
            return json.dumps(_result_payload(result), indent=2)

    @mcp.tool()
    def graph_update_node(
        id: str,
        body: str | None = None,
        frontmatter: dict | None = None,
    ) -> str:
        """Replace the body and/or frontmatter of an existing node."""
        args = {"id": id, "has_body": body is not None, "has_frontmatter": frontmatter is not None}
        with CallTimer("graph_update_node", args) as t:
            node_id = id.strip()
            if not node_id:
                raise RuntimeError("graph_update_node requires 'id'")
            if body is None and frontmatter is None:
                raise RuntimeError("graph_update_node requires 'body' or 'frontmatter'")
            if frontmatter is not None and not isinstance(frontmatter, dict):
                raise RuntimeError("'frontmatter' must be an object")
            result = graph_writes.update_node(
                _PROJECT_ROOT,
                node_id=node_id,
                body=None if body is None else str(body),
                frontmatter=frontmatter,
            )
            _invalidate_caches()
            t.ok()
            return json.dumps(_result_payload(result), indent=2)

    @mcp.tool()
    def graph_delete_node(id: str, allow_orphans: bool = False) -> str:
        """Delete a node. Refuses if other nodes link to it via curated edges, unless
        allow_orphans=True (cascades the orphaned curated edges away)."""
        with CallTimer("graph_delete_node", {"id": id, "allow_orphans": allow_orphans}) as t:
            node_id = id.strip()
            if not node_id:
                raise RuntimeError("graph_delete_node requires 'id'")
            result = graph_writes.delete_node(
                _PROJECT_ROOT, node_id=node_id, allow_orphans=bool(allow_orphans),
            )
            _invalidate_caches()
            t.ok()
            return json.dumps(_result_payload(result), indent=2)

    @mcp.tool()
    def graph_add_edge(src: str, dst: str) -> str:
        """Add a curated edge by writing 'dst' into 'src's frontmatter `links:` list."""
        with CallTimer("graph_add_edge", {"src": src, "dst": dst}) as t:
            s, d = src.strip(), dst.strip()
            if not s or not d:
                raise RuntimeError("graph_add_edge requires 'src' and 'dst'")
            result = graph_writes.add_edge(_PROJECT_ROOT, src=s, dst=d)
            _invalidate_caches()
            t.ok()
            return json.dumps(_result_payload(result), indent=2)

    @mcp.tool()
    def graph_remove_edge(src: str, dst: str) -> str:
        """Remove a curated edge from 'src's frontmatter `links:` list. Auto-extracted
        edges (raw path mentions in prose) cannot be removed via this tool — edit the
        prose instead."""
        with CallTimer("graph_remove_edge", {"src": src, "dst": dst}) as t:
            s, d = src.strip(), dst.strip()
            if not s or not d:
                raise RuntimeError("graph_remove_edge requires 'src' and 'dst'")
            result = graph_writes.remove_edge(_PROJECT_ROOT, src=s, dst=d)
            _invalidate_caches()
            t.ok()
            return json.dumps(_result_payload(result), indent=2)
