#!/usr/bin/env python3
"""MCP server exposing the knowledge graph through the `fabric-graph` MCP `graph_*` tools.

Read-only surface (Phase P2):
  graph_get_entry   - root entry node (mandatory first call per profile rule)
  graph_get_node    - one node's full body
  graph_get_linked  - 1-hop neighbors of a node
  graph_search      - BM25 + 1-hop edge-aware re-rank
  graph_list_kinds  - node kind counts

Write surface (Phase P5) — added in a follow-up commit.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tool"))

from graph.schema import parse_frontmatter  # noqa: E402
from graph.search import BM25Index, build_bm25_index, load_index, search  # noqa: E402
from graph.store import GraphStore  # noqa: E402
from graph import writes as graph_writes  # noqa: E402

GRAPH_DIR = ROOT / "memory" / ".graph"
GRAPH_PATH = GRAPH_DIR / "graph.json"
BM25_PATH = GRAPH_DIR / "graph-bm25.pkl"
ENTRY_NODE_ID = "graph-content/entry"


def _audit_log_path() -> Path:
    if os.name == "nt":
        localappdata = os.environ.get("LOCALAPPDATA", "")
        base = Path(localappdata) if localappdata else Path.home()
    else:
        base = Path.home() / ".cache"
    log_dir = base / "fabric-mcp"
    log_dir.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        log_dir.chmod(0o700)
    return log_dir / "audit.log"


def _audit(tool: str, arguments: dict, success: bool) -> None:
    ts = datetime.now(timezone.utc).isoformat()
    args_hash = hashlib.sha256(json.dumps(arguments, sort_keys=True).encode()).hexdigest()[:16]
    status = "success" if success else "error"
    entry = f"{ts} server=fabric-graph tool={tool} args_hash={args_hash} result={status}\n"
    try:
        with _audit_log_path().open("a", encoding="utf-8") as fh:
            fh.write(entry)
    except OSError:
        pass


_store: GraphStore | None = None
_index: BM25Index | None = None
_index_mtime: float = 0.0


def _load_graph() -> GraphStore:
    global _store
    if _store is None:
        if not GRAPH_PATH.exists():
            raise RuntimeError(
                f"graph not built: {GRAPH_PATH.relative_to(ROOT)} missing — run python bin/build-graph.py"
            )
        _store = GraphStore.load(GRAPH_PATH)
    return _store


def _load_search_index(store: GraphStore) -> BM25Index:
    """Load the BM25 pickle if fresh; otherwise rebuild in-memory from current node bodies."""
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
    """Read the body (frontmatter stripped) of a node's underlying markdown file."""
    try:
        text = (ROOT / rel_path).read_text(encoding="utf-8", errors="ignore")
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


def _dispatch(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    store = _load_graph()

    if name == "graph_get_entry":
        if not store.has_node(ENTRY_NODE_ID):
            raise RuntimeError(
                f"entry node {ENTRY_NODE_ID!r} not present in graph — content tree may not be installed yet"
            )
        return _text(_node_payload(store, ENTRY_NODE_ID, include_body=True))

    if name == "graph_get_node":
        node_id = str(arguments.get("id", "")).strip()
        if not node_id:
            raise RuntimeError("graph_get_node requires 'id'")
        if not store.has_node(node_id):
            raise RuntimeError(f"unknown node id: {node_id!r}")
        return _text(_node_payload(store, node_id, include_body=True))

    if name == "graph_get_linked":
        node_id = str(arguments.get("id", "")).strip()
        if not node_id:
            raise RuntimeError("graph_get_linked requires 'id'")
        if not store.has_node(node_id):
            raise RuntimeError(f"unknown node id: {node_id!r}")
        kinds = arguments.get("kinds")
        if kinds is not None and not isinstance(kinds, list):
            raise RuntimeError("'kinds' must be a list of strings")
        neighbors = []
        for neighbor in sorted(store.graph.successors(node_id)):
            data = store.graph.nodes[neighbor]
            edge_kind = store.graph.get_edge_data(node_id, neighbor).get("kind", "curated")
            kind = data.get("kind", "content")
            if kinds and kind not in kinds:
                continue
            neighbors.append(
                {
                    "id": neighbor,
                    "title": data.get("title", neighbor),
                    "description": data.get("description", ""),
                    "kind": kind,
                    "edge_kind": edge_kind,
                }
            )
        return _text({"id": node_id, "neighbors": neighbors})

    if name == "graph_search":
        query = str(arguments.get("query", "")).strip()
        if not query:
            raise RuntimeError("graph_search requires non-empty 'query'")
        try:
            k = int(arguments.get("k", 5))
        except (TypeError, ValueError):
            raise RuntimeError("'k' must be an integer")
        k = max(1, min(k, 25))
        index = _load_search_index(store)
        hits = search(store, index, query, k=k)
        return _text(
            {
                "query": query,
                "hits": [
                    {"id": h.id, "title": h.title, "score": h.score, "why_matched": h.why_matched}
                    for h in hits
                ],
            }
        )

    if name == "graph_list_kinds":
        return _text({"counts": store.kinds(), "total": store.graph.number_of_nodes(), "edges": store.graph.number_of_edges()})

    if name == "graph_create_node":
        node_id = str(arguments.get("id", "")).strip()
        body = str(arguments.get("body", ""))
        if not node_id or not body:
            raise RuntimeError("graph_create_node requires 'id' and 'body'")
        fm = arguments.get("frontmatter") or {}
        if not isinstance(fm, dict):
            raise RuntimeError("'frontmatter' must be an object")
        links = arguments.get("links")
        if links is not None and not isinstance(links, list):
            raise RuntimeError("'links' must be a list of strings")
        path = arguments.get("path") or None
        result = graph_writes.create_node(
            ROOT, node_id=node_id, body=body, frontmatter=fm,
            links=list(links) if links else None,
            path=str(path) if path else None,
        )
        _invalidate_caches()
        return _text(_result_payload(result))

    if name == "graph_update_node":
        node_id = str(arguments.get("id", "")).strip()
        if not node_id:
            raise RuntimeError("graph_update_node requires 'id'")
        body = arguments.get("body")
        fm = arguments.get("frontmatter")
        if body is None and fm is None:
            raise RuntimeError("graph_update_node requires 'body' or 'frontmatter'")
        if fm is not None and not isinstance(fm, dict):
            raise RuntimeError("'frontmatter' must be an object")
        result = graph_writes.update_node(
            ROOT, node_id=node_id,
            body=body if body is None else str(body),
            frontmatter=fm,
        )
        _invalidate_caches()
        return _text(_result_payload(result))

    if name == "graph_delete_node":
        node_id = str(arguments.get("id", "")).strip()
        if not node_id:
            raise RuntimeError("graph_delete_node requires 'id'")
        allow_orphans = bool(arguments.get("allow_orphans", False))
        result = graph_writes.delete_node(ROOT, node_id=node_id, allow_orphans=allow_orphans)
        _invalidate_caches()
        return _text(_result_payload(result))

    if name == "graph_add_edge":
        src = str(arguments.get("src", "")).strip()
        dst = str(arguments.get("dst", "")).strip()
        if not src or not dst:
            raise RuntimeError("graph_add_edge requires 'src' and 'dst'")
        result = graph_writes.add_edge(ROOT, src=src, dst=dst)
        _invalidate_caches()
        return _text(_result_payload(result))

    if name == "graph_remove_edge":
        src = str(arguments.get("src", "")).strip()
        dst = str(arguments.get("dst", "")).strip()
        if not src or not dst:
            raise RuntimeError("graph_remove_edge requires 'src' and 'dst'")
        result = graph_writes.remove_edge(ROOT, src=src, dst=dst)
        _invalidate_caches()
        return _text(_result_payload(result))

    raise RuntimeError(f"unknown tool: {name}")


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


def _text(payload: Any) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(payload, indent=2, ensure_ascii=False)}]}


TOOLS = [
    {
        "name": "graph_get_entry",
        "description": "Return the root entry node of the project knowledge graph. MUST be the first tool call in any session. The entry node contains the mandatory setup gate and links to the rest of the graph.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "graph_get_node",
        "description": "Return the full content of one node by id, including its body and outbound link ids. Only call with ids returned by graph_get_entry, graph_get_linked, or graph_search.",
        "inputSchema": {
            "type": "object",
            "properties": {"id": {"type": "string", "description": "Canonical node id (e.g. graph-content/workflow/pipeline-structure)"}},
            "required": ["id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "graph_get_linked",
        "description": "Return the 1-hop neighbors (outbound edges) of a node. Use this to traverse the graph after reading a node's body.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Node id whose neighbors to fetch."},
                "kinds": {"type": "array", "items": {"type": "string"}, "description": "Optional list of node kinds to filter neighbors (e.g. ['skill', 'rule'])."},
            },
            "required": ["id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "graph_search",
        "description": "BM25 + 1-hop edge-aware search across the graph. Use only when no linked node looks relevant and a new entry point is needed.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Free-text query."},
                "k": {"type": "integer", "description": "Number of hits to return (default 5, max 25)."},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "graph_list_kinds",
        "description": "Return a count of nodes by kind and the total node + edge counts. Useful for understanding the shape of the graph.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "graph_create_node",
        "description": "Author a new node. The underlying .md file is written atomically and the graph is rebuilt. Refuses to overwrite. Use this instead of Write/Edit when authoring knowledge content (e.g. a new skill-fix entry).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "description": "Canonical node id (e.g. skill-fixes/silver-do-not-trust-bronze-types)"},
                "body": {"type": "string", "description": "Markdown body of the node (without frontmatter)."},
                "frontmatter": {"type": "object", "description": "Top-level frontmatter fields (name, description, kind, metadata.*)."},
                "links": {"type": "array", "items": {"type": "string"}, "description": "Optional list of node ids to add as curated outbound links."},
                "path": {"type": "string", "description": "Optional explicit repo-relative path; defaults to the conventional path for the node kind."},
            },
            "required": ["id", "body"],
            "additionalProperties": False,
        },
    },
    {
        "name": "graph_update_node",
        "description": "Modify an existing node's body and/or frontmatter. Atomic; rebuilds the graph after the write.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "body": {"type": "string", "description": "New markdown body (replaces existing). Omit to leave unchanged."},
                "frontmatter": {"type": "object", "description": "Frontmatter fields to merge into the existing frontmatter. Omit to leave unchanged."},
            },
            "required": ["id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "graph_delete_node",
        "description": "Delete a node and its file. Refuses if other nodes have curated edges pointing at it unless allow_orphans=true (cascade — also removes the curated links from the linking files).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "allow_orphans": {"type": "boolean", "description": "If true, cascade-remove curated links from other files that point at this node. Default false."},
            },
            "required": ["id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "graph_add_edge",
        "description": "Add a curated edge from src to dst by appending to the src node's `links:` frontmatter. Refuses if either endpoint does not exist or if the edge already exists.",
        "inputSchema": {
            "type": "object",
            "properties": {"src": {"type": "string"}, "dst": {"type": "string"}},
            "required": ["src", "dst"],
            "additionalProperties": False,
        },
    },
    {
        "name": "graph_remove_edge",
        "description": "Remove a curated edge from src to dst. Refuses if the edge is auto-extracted (auto edges are removed by editing the prose that mentions the target).",
        "inputSchema": {
            "type": "object",
            "properties": {"src": {"type": "string"}, "dst": {"type": "string"}},
            "required": ["src", "dst"],
            "additionalProperties": False,
        },
    },
]


def response(request_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def error_response(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def handle(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    request_id = message.get("id")
    if method == "initialize":
        return response(
            request_id,
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "fabric-graph", "version": "0.1.0"},
            },
        )
    if method == "notifications/initialized":
        return None
    if method == "tools/list":
        return response(request_id, {"tools": TOOLS})
    if method == "tools/call":
        params = message.get("params", {})
        name = params.get("name", "")
        arguments = params.get("arguments", {}) or {}
        success = False
        try:
            result = _dispatch(name, arguments)
            success = True
            return response(request_id, result)
        except Exception as exc:
            return error_response(request_id, -32000, str(exc))
        finally:
            _audit(name, arguments, success)
    if request_id is None:
        return None
    return error_response(request_id, -32601, f"Unsupported method: {method}")


def main() -> int:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            outgoing = handle(json.loads(line))
        except Exception as exc:
            outgoing = error_response(None, -32700, str(exc))
        if outgoing is not None:
            print(json.dumps(outgoing), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
