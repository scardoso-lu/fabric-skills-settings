"""Admin REST API routes for the fabric-server management UI.

All routes are mounted under /api/v1/ and require a valid JWT Bearer token
(enforced by FabricAuthMiddleware on the parent Starlette app).

Security notes (OWASP):
- Path traversal prevented by _resolve_graph_path in writes.py (validates id_from_path).
- All request payloads are validated via _parse_json / explicit field checks before use.
- node_id segments are validated by _validate_id_segments in writes.py.
- Body length is capped at 512 KiB.
- Security headers (X-Content-Type-Options, X-Frame-Options) are added to every response.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from ..graph import writes as graph_writes
from ..graph.schema import parse_frontmatter
from ..graph.search import search
from ..tools.graph.tools import (
    BM25_PATH,
    GRAPH_PATH,
    _PROJECT_ROOT,
    _invalidate_caches,
    _load_graph,
    _load_search_index,
    _node_payload,
    _read_body,
)

_MAX_BODY_BYTES = 512 * 1024  # 512 KiB
_MAX_SEARCH_QUERY_LEN = 200  # characters


def _json(data: Any, status: int = 200) -> JSONResponse:
    r = JSONResponse(data, status_code=status)
    r.headers["X-Content-Type-Options"] = "nosniff"
    r.headers["X-Frame-Options"] = "DENY"
    return r


def _error(msg: str, status: int = 400) -> JSONResponse:
    return _json({"error": msg}, status)


async def _parse_json(request: Request) -> dict | None:
    """Read and parse the request body as JSON; return None if malformed or too large."""
    try:
        body = await request.body()
    except Exception:
        return None
    if len(body) > _MAX_BODY_BYTES:
        return None
    try:
        return json.loads(body)
    except (json.JSONDecodeError, ValueError):
        return None


def _managed_path_for_id(node_id: str) -> str:
    """Compute the default managed-directory path for a new node id."""
    prefix, _, rest = node_id.partition("/")
    if prefix == "skills":
        name = rest.split("/")[0]
        return f"server/managed/skills/{name}/SKILL.md"
    if prefix == "rules":
        return f"server/managed/content/rules/{rest}.md"
    if prefix == "skill-fixes":
        return f"server/managed/content/skill-fixes/{rest}.md"
    if prefix == "memory":
        return f"server/managed/content/memory/{rest}.md"
    # graph-content/* or anything else
    return f"server/managed/content/{rest}.md"


def _is_managed(path: str) -> bool:
    return path.startswith("server/managed/")


# ── stats ──────────────────────────────────────────────────────────────────────

async def stats(request: Request) -> Response:
    try:
        store = _load_graph()
    except RuntimeError as exc:
        return _error(str(exc), 503)
    return _json({
        "nodes": store.graph.number_of_nodes(),
        "edges": store.graph.number_of_edges(),
        "by_kind": store.kinds(),
        "built_at": store.built_at,
    })


# ── node list ──────────────────────────────────────────────────────────────────

async def list_nodes(request: Request) -> Response:
    try:
        store = _load_graph()
    except RuntimeError as exc:
        return _error(str(exc), 503)
    kind_filter = request.query_params.get("kind")
    nodes = []
    for nid, data in store.graph.nodes(data=True):
        if kind_filter and data.get("kind") != kind_filter:
            continue
        nodes.append({
            "id": nid,
            "title": data.get("title", nid),
            "description": data.get("description", ""),
            "kind": data.get("kind", "content"),
            "path": data.get("path", ""),
            "managed": _is_managed(data.get("path", "")),
        })
    nodes.sort(key=lambda n: (n["kind"], n["id"]))
    return _json({"nodes": nodes})


# ── node detail ────────────────────────────────────────────────────────────────

async def get_node(request: Request) -> Response:
    node_id = request.path_params["node_id"]
    try:
        store = _load_graph()
    except RuntimeError as exc:
        return _error(str(exc), 503)
    if not store.has_node(node_id):
        return _error(f"node not found: {node_id!r}", 404)
    payload = _node_payload(store, node_id, include_body=True)
    data = store.graph.nodes[node_id]
    payload["managed"] = _is_managed(data.get("path", ""))
    payload["frontmatter"] = data.get("frontmatter", {})
    payload["inbound_links"] = sorted(store.graph.predecessors(node_id))
    return _json(payload)


# ── create node ────────────────────────────────────────────────────────────────

async def create_node(request: Request) -> Response:
    payload = await _parse_json(request)
    if payload is None:
        return _error("invalid or oversized JSON body")
    node_id = (payload.get("id") or "").strip()
    body = payload.get("body") or ""
    if not node_id:
        return _error("'id' is required")
    frontmatter = payload.get("frontmatter") or {}
    links = payload.get("links")
    if links is not None and not isinstance(links, list):
        return _error("'links' must be a list")
    explicit_path: str | None = payload.get("path")
    managed_path = explicit_path or _managed_path_for_id(node_id)
    try:
        result = graph_writes.create_node(
            _PROJECT_ROOT,
            node_id=node_id,
            body=body,
            frontmatter=frontmatter,
            links=links,
            path=managed_path,
        )
        _invalidate_caches()
    except ValueError as exc:
        return _error(str(exc), 409)
    except Exception:
        return _error("internal error", 500)
    return _json({"id": result.node_id, "path": result.path, "action": result.action,
                  "nodes": result.nodes, "edges": result.edges}, 201)


# ── update node ────────────────────────────────────────────────────────────────

async def update_node(request: Request) -> Response:
    node_id = request.path_params["node_id"]
    payload = await _parse_json(request)
    if payload is None:
        return _error("invalid or oversized JSON body")
    body = payload.get("body")
    frontmatter = payload.get("frontmatter")
    if body is None and frontmatter is None:
        return _error("at least one of 'body' or 'frontmatter' is required")
    try:
        result = graph_writes.update_node(
            _PROJECT_ROOT,
            node_id=node_id,
            body=body,
            frontmatter=frontmatter,
        )
        _invalidate_caches()
    except ValueError as exc:
        return _error(str(exc), 404 if "unknown node" in str(exc) else 400)
    except Exception:
        return _error("internal error", 500)
    return _json({"id": result.node_id, "path": result.path, "action": result.action,
                  "nodes": result.nodes, "edges": result.edges})


# ── delete node ────────────────────────────────────────────────────────────────

async def delete_node(request: Request) -> Response:
    node_id = request.path_params["node_id"]
    allow_orphans = request.query_params.get("allow_orphans", "false").lower() == "true"
    try:
        result = graph_writes.delete_node(
            _PROJECT_ROOT,
            node_id=node_id,
            allow_orphans=allow_orphans,
        )
        _invalidate_caches()
    except ValueError as exc:
        status = 404 if "unknown node" in str(exc) else 409
        return _error(str(exc), status)
    except Exception:
        return _error("internal error", 500)
    return _json({"id": result.node_id, "path": result.path, "action": result.action,
                  "nodes": result.nodes, "edges": result.edges})


# ── search ─────────────────────────────────────────────────────────────────────

async def search_nodes(request: Request) -> Response:
    query = (request.query_params.get("q") or "").strip()
    if not query:
        return _error("'q' query parameter is required")
    if len(query) > _MAX_SEARCH_QUERY_LEN:
        return _error(f"'q' must be at most {_MAX_SEARCH_QUERY_LEN} characters")
    try:
        k = min(max(int(request.query_params.get("k", "10")), 1), 25)
    except ValueError:
        return _error("'k' must be an integer between 1 and 25")
    try:
        store = _load_graph()
        index = _load_search_index(store)
    except RuntimeError as exc:
        return _error(str(exc), 503)
    hits = search(store, index, query, k=k)
    return _json({
        "query": query,
        "hits": [{"id": h.id, "title": h.title, "score": round(h.score, 4),
                  "why_matched": h.why_matched} for h in hits],
    })


# ── edges ──────────────────────────────────────────────────────────────────────

async def add_edge(request: Request) -> Response:
    payload = await _parse_json(request)
    if payload is None:
        return _error("invalid or oversized JSON body")
    src = (payload.get("src") or "").strip()
    dst = (payload.get("dst") or "").strip()
    if not src or not dst:
        return _error("'src' and 'dst' are required")
    try:
        result = graph_writes.add_edge(_PROJECT_ROOT, src=src, dst=dst)
        _invalidate_caches()
    except ValueError as exc:
        return _error(str(exc), 404 if "unknown" in str(exc) else 409)
    except Exception:
        return _error("internal error", 500)
    return _json({"action": result.action, "nodes": result.nodes, "edges": result.edges}, 201)


async def remove_edge(request: Request) -> Response:
    payload = await _parse_json(request)
    if payload is None:
        return _error("invalid or oversized JSON body")
    src = (payload.get("src") or "").strip()
    dst = (payload.get("dst") or "").strip()
    if not src or not dst:
        return _error("'src' and 'dst' are required")
    try:
        result = graph_writes.remove_edge(_PROJECT_ROOT, src=src, dst=dst)
        _invalidate_caches()
    except ValueError as exc:
        return _error(str(exc), 404 if "unknown" in str(exc) else 409)
    except Exception:
        return _error("internal error", 500)
    return _json({"action": result.action, "nodes": result.nodes, "edges": result.edges})


# ── templates ──────────────────────────────────────────────────────────────────

def _bundled_skills_dir() -> Path:
    return _PROJECT_ROOT / "server" / "skills"


async def list_templates(request: Request) -> Response:
    skills_dir = _bundled_skills_dir()
    templates = []
    if skills_dir.is_dir():
        for skill_dir in sorted(skills_dir.iterdir()):
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.is_file():
                continue
            try:
                fm, _ = parse_frontmatter(skill_file.read_text(encoding="utf-8"))
            except OSError:
                continue
            templates.append({
                "name": skill_dir.name,
                "description": fm.get("description", ""),
                "allowed_tools": fm.get("allowed-tools", ""),
            })
    return _json({"templates": templates})


async def get_template(request: Request) -> Response:
    name = request.path_params["name"]
    # Prevent path traversal: name must be a single path segment with no separators.
    if "/" in name or "\\" in name or name in ("", ".", ".."):
        return _error("invalid template name", 400)
    skill_file = _bundled_skills_dir() / name / "SKILL.md"
    if not skill_file.is_file():
        return _error(f"template not found: {name!r}", 404)
    try:
        text = skill_file.read_text(encoding="utf-8")
    except OSError:
        return _error("could not read template", 500)
    fm, body = parse_frontmatter(text)
    return _json({"name": name, "frontmatter": fm, "body": body})


# ── OpenAPI spec + ReDoc docs ──────────────────────────────────────────────────

_OPENAPI_SPEC: dict = {
    "openapi": "3.1.0",
    "info": {
        "title": "Fabric Admin REST API",
        "version": "1.0.0",
        "description": (
            "Admin API for the fabric-skills-settings knowledge graph server. "
            "All `/api/v1/*` endpoints require a Bearer JWT obtained from `POST /auth/login`."
        ),
    },
    "servers": [{"url": "/", "description": "This server"}],
    "components": {
        "securitySchemes": {
            "bearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"},
        },
        "schemas": {
            "Error": {
                "type": "object",
                "properties": {"error": {"type": "string"}},
                "required": ["error"],
            },
            "NodeSummary": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "kind": {"type": "string", "enum": ["skill", "content", "rule", "skill-fix", "memory", "entry"]},
                    "path": {"type": "string"},
                    "managed": {"type": "boolean"},
                },
                "required": ["id", "title", "kind", "path", "managed"],
            },
            "NodeDetail": {
                "allOf": [{"$ref": "#/components/schemas/NodeSummary"}],
                "properties": {
                    "body": {"type": "string"},
                    "frontmatter": {"type": "object"},
                    "outbound_links": {"type": "array", "items": {"type": "string"}},
                    "inbound_links": {"type": "array", "items": {"type": "string"}},
                },
            },
            "WriteResult": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "path": {"type": "string"},
                    "action": {"type": "string"},
                    "nodes": {"type": "integer"},
                    "edges": {"type": "integer"},
                },
                "required": ["id", "path", "action", "nodes", "edges"],
            },
            "EdgeResult": {
                "type": "object",
                "properties": {
                    "action": {"type": "string"},
                    "nodes": {"type": "integer"},
                    "edges": {"type": "integer"},
                },
                "required": ["action", "nodes", "edges"],
            },
        },
    },
    "security": [{"bearerAuth": []}],
    "paths": {
        "/auth/login": {
            "post": {
                "tags": ["Auth"],
                "summary": "Exchange API key for a JWT",
                "security": [],
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {
                        "type": "object",
                        "properties": {"api_key": {"type": "string"}},
                        "required": ["api_key"],
                    }}},
                },
                "responses": {
                    "200": {"description": "JWT issued", "content": {"application/json": {"schema": {
                        "type": "object",
                        "properties": {
                            "token": {"type": "string"},
                            "expires_at": {"type": "number"},
                            "token_type": {"type": "string", "example": "Bearer"},
                        },
                    }}}},
                    "401": {"description": "Invalid API key"},
                    "429": {"description": "Rate limit exceeded"},
                },
            },
        },
        "/auth/refresh": {
            "post": {
                "tags": ["Auth"],
                "summary": "Refresh a JWT (old token revoked)",
                "responses": {
                    "200": {"description": "New JWT issued"},
                    "401": {"description": "Token missing or invalid"},
                },
            },
        },
        "/api/v1/stats": {
            "get": {
                "tags": ["Graph"],
                "summary": "Graph statistics",
                "responses": {
                    "200": {"description": "Node/edge counts and build timestamp", "content": {"application/json": {"schema": {
                        "type": "object",
                        "properties": {
                            "nodes": {"type": "integer"},
                            "edges": {"type": "integer"},
                            "by_kind": {"type": "object"},
                            "built_at": {"type": "string", "nullable": True},
                        },
                    }}}},
                },
            },
        },
        "/api/v1/nodes": {
            "get": {
                "tags": ["Nodes"],
                "summary": "List all nodes",
                "parameters": [{"name": "kind", "in": "query", "schema": {"type": "string"}, "description": "Filter by node kind"}],
                "responses": {
                    "200": {"description": "Node list", "content": {"application/json": {"schema": {
                        "type": "object",
                        "properties": {"nodes": {"type": "array", "items": {"$ref": "#/components/schemas/NodeSummary"}}},
                    }}}},
                },
            },
            "post": {
                "tags": ["Nodes"],
                "summary": "Create a new node",
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "body": {"type": "string"},
                            "frontmatter": {"type": "object"},
                            "links": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["id"],
                    }}},
                },
                "responses": {
                    "201": {"description": "Node created", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/WriteResult"}}}},
                    "409": {"description": "Node ID already exists"},
                },
            },
        },
        "/api/v1/nodes/{node_id}": {
            "get": {
                "tags": ["Nodes"],
                "summary": "Get a single node with body",
                "parameters": [{"name": "node_id", "in": "path", "required": True, "schema": {"type": "string"}}],
                "responses": {
                    "200": {"description": "Node detail", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/NodeDetail"}}}},
                    "404": {"description": "Node not found"},
                },
            },
            "put": {
                "tags": ["Nodes"],
                "summary": "Update a node's body and/or frontmatter",
                "parameters": [{"name": "node_id", "in": "path", "required": True, "schema": {"type": "string"}}],
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {
                        "type": "object",
                        "properties": {
                            "body": {"type": "string"},
                            "frontmatter": {"type": "object"},
                        },
                    }}},
                },
                "responses": {
                    "200": {"description": "Node updated", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/WriteResult"}}}},
                    "404": {"description": "Node not found"},
                },
            },
            "delete": {
                "tags": ["Nodes"],
                "summary": "Delete a node",
                "parameters": [
                    {"name": "node_id", "in": "path", "required": True, "schema": {"type": "string"}},
                    {"name": "allow_orphans", "in": "query", "schema": {"type": "boolean", "default": False}, "description": "Delete even if other nodes link to this one"},
                ],
                "responses": {
                    "200": {"description": "Node deleted", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/WriteResult"}}}},
                    "404": {"description": "Node not found"},
                    "409": {"description": "Node has inbound curated links"},
                },
            },
        },
        "/api/v1/search": {
            "get": {
                "tags": ["Search"],
                "summary": "BM25 full-text search with 1-hop edge re-ranking",
                "parameters": [
                    {"name": "q", "in": "query", "required": True, "schema": {"type": "string", "maxLength": 200}},
                    {"name": "k", "in": "query", "schema": {"type": "integer", "minimum": 1, "maximum": 25, "default": 10}},
                ],
                "responses": {
                    "200": {"description": "Search results", "content": {"application/json": {"schema": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "hits": {"type": "array", "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string"},
                                    "title": {"type": "string"},
                                    "score": {"type": "number"},
                                    "why_matched": {"type": "string"},
                                },
                            }},
                        },
                    }}}},
                },
            },
        },
        "/api/v1/edges": {
            "post": {
                "tags": ["Edges"],
                "summary": "Add a curated edge",
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {
                        "type": "object",
                        "properties": {"src": {"type": "string"}, "dst": {"type": "string"}},
                        "required": ["src", "dst"],
                    }}},
                },
                "responses": {
                    "201": {"description": "Edge added", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/EdgeResult"}}}},
                    "404": {"description": "Source or destination node not found"},
                    "409": {"description": "Edge already exists or self-edge"},
                },
            },
            "delete": {
                "tags": ["Edges"],
                "summary": "Remove a curated edge",
                "requestBody": {
                    "required": True,
                    "content": {"application/json": {"schema": {
                        "type": "object",
                        "properties": {"src": {"type": "string"}, "dst": {"type": "string"}},
                        "required": ["src", "dst"],
                    }}},
                },
                "responses": {
                    "200": {"description": "Edge removed", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/EdgeResult"}}}},
                    "404": {"description": "Node or edge not found"},
                    "409": {"description": "Edge is auto-generated (not curated)"},
                },
            },
        },
        "/api/v1/templates": {
            "get": {
                "tags": ["Templates"],
                "summary": "List bundled skill templates",
                "responses": {
                    "200": {"description": "Template list", "content": {"application/json": {"schema": {
                        "type": "object",
                        "properties": {"templates": {"type": "array", "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "description": {"type": "string"},
                                "allowed_tools": {"type": "string"},
                            },
                        }}},
                    }}}},
                },
            },
        },
        "/api/v1/templates/{name}": {
            "get": {
                "tags": ["Templates"],
                "summary": "Get a skill template's body and frontmatter",
                "parameters": [{"name": "name", "in": "path", "required": True, "schema": {"type": "string"}}],
                "responses": {
                    "200": {"description": "Template content"},
                    "404": {"description": "Template not found"},
                },
            },
        },
    },
}

_REdoc_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Fabric Admin API — docs</title>
  <link href="https://fonts.googleapis.com/css?family=Montserrat:300,400,700|Roboto:300,400,700" rel="stylesheet">
  <style>body{margin:0;padding:0;}</style>
</head>
<body>
  <redoc spec-url="/api/v1/openapi.json" hide-download-button></redoc>
  <script src="https://cdn.jsdelivr.net/npm/redoc@2.1.5/bundles/redoc.standalone.js"></script>
</body>
</html>
"""


async def openapi_spec(request: Request) -> Response:
    return _json(_OPENAPI_SPEC)


async def api_docs(request: Request) -> Response:
    from starlette.responses import HTMLResponse
    return HTMLResponse(_REdoc_HTML, status_code=200)


# ── route table ────────────────────────────────────────────────────────────────

def make_routes() -> list[Route]:
    """Return Starlette Route objects to be mounted under /api."""
    return [
        Route("/v1/openapi.json",             openapi_spec,  methods=["GET"]),
        Route("/v1/docs",                     api_docs,      methods=["GET"]),
        Route("/v1/stats",                    stats,         methods=["GET"]),
        Route("/v1/nodes",                    list_nodes,    methods=["GET"]),
        Route("/v1/nodes",                    create_node,   methods=["POST"]),
        Route("/v1/nodes/{node_id:path}",     get_node,      methods=["GET"]),
        Route("/v1/nodes/{node_id:path}",     update_node,   methods=["PUT"]),
        Route("/v1/nodes/{node_id:path}",     delete_node,   methods=["DELETE"]),
        Route("/v1/search",                   search_nodes,  methods=["GET"]),
        Route("/v1/edges",                    add_edge,      methods=["POST"]),
        Route("/v1/edges",                    remove_edge,   methods=["DELETE"]),
        Route("/v1/templates",                list_templates, methods=["GET"]),
        Route("/v1/templates/{name}",         get_template,  methods=["GET"]),
    ]
