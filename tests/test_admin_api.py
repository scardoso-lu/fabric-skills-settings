"""Tests for the admin REST API (server/api/routes.py).

Uses a temporary project root so reads/writes don't touch real content.
Follows the same ASGI-test pattern as test_server_auth.py.
"""

from __future__ import annotations

import asyncio
import importlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


# ── helpers ───────────────────────────────────────────────────────────────────

class _Captured:
    """Minimal ASGI send/receive collector."""

    def __init__(self, body: bytes = b"") -> None:
        self._body = body
        self.responses: list[dict] = []

    async def receive(self):
        return {"type": "http.request", "body": self._body, "more_body": False}

    async def send(self, event):
        self.responses.append(event)

    @property
    def status(self) -> int:
        return next(r["status"] for r in self.responses if r["type"] == "http.response.start")

    @property
    def body(self) -> dict:
        raw = next(r["body"] for r in self.responses if r["type"] == "http.response.body")
        return json.loads(raw)


def _scope(method: str, path: str, body: bytes = b"") -> dict:
    return {"type": "http", "method": method, "path": path,
            "query_string": b"", "headers": []}


def _async(coro):
    return asyncio.run(coro)


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def project_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a minimal project root with a built graph and redirect module globals."""
    # Directory structure
    skills_dir = tmp_path / "server" / "skills"
    content_dir = tmp_path / "server" / "content"
    managed_dir = tmp_path / "server" / "managed"
    graph_dir = tmp_path / "dist" / ".graph"

    # Bundled skill (template)
    skill_dir = skills_dir / "git-commit"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: git-commit\ndescription: Conventional commits\n---\n# Git Commit\n\nFollow conventional commit format.\n"
    )

    # Bundled content node
    content_dir.mkdir(parents=True)
    (content_dir / "entry.md").write_text(
        "---\nname: entry\ndescription: Entry node\nkind: entry\n---\n# Entry\n"
    )
    (content_dir / "rules").mkdir()
    (content_dir / "rules" / "security.md").write_text(
        "---\nname: security\ndescription: Security rules\nkind: rule\n---\n# Security\n\nRules here.\n"
    )

    # Managed dirs (empty)
    (managed_dir / "skills").mkdir(parents=True)
    (managed_dir / "content" / "rules").mkdir(parents=True)
    (managed_dir / "content" / "memory").mkdir(parents=True)

    graph_dir.mkdir(parents=True)

    # Patch tools module globals before importing routes
    monkeypatch.setenv("FABRIC_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("FABRIC_GRAPH_DIR", str(graph_dir))

    # Force reload of tools and api modules so they pick up patched env
    for mod_name in list(sys.modules.keys()):
        if "server.tools.graph.tools" in mod_name or "server.api" in mod_name:
            del sys.modules[mod_name]

    # Build the graph
    from server.graph.builder import build as build_graph
    from server.graph.search import build_bm25_index, save_index
    result = build_graph(tmp_path)
    assert not result.errors, result.errors
    store = result.store
    store.save(graph_dir / "graph.json", built_by="test")
    bodies = {nid: "" for nid in store.graph.nodes}
    save_index(graph_dir / "graph-bm25.json", build_bm25_index(store, bodies))

    return tmp_path


@pytest.fixture()
def routes(project_root: Path):
    """Import and return the make_routes() list, bound to project_root."""
    # Re-import with fresh globals pointing to project_root
    if "server.api.routes" in sys.modules:
        del sys.modules["server.api.routes"]
    if "server.tools.graph.tools" in sys.modules:
        del sys.modules["server.tools.graph.tools"]

    from server.api.routes import make_routes
    return make_routes()


async def _call_route(routes, method: str, path: str, body: bytes = b"") -> _Captured:
    """Find the matching route and call its endpoint."""
    from starlette.routing import Router
    router = Router(routes=routes)
    app = router

    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "query_string": b"",
        "headers": [],
        "path_params": {},
    }
    cap = _Captured(body)

    async def fallback(scope, receive, send):
        await send({"type": "http.response.start", "status": 404, "headers": []})
        await send({"type": "http.response.body", "body": b'{"error":"not_found"}'})

    try:
        await app(scope, cap.receive, cap.send)
    except Exception:
        await fallback(scope, cap.receive, cap.send)
    return cap


# ── stats ──────────────────────────────────────────────────────────────────────

def test_stats_returns_node_and_edge_counts(project_root, routes):
    from starlette.testclient import TestClient
    from starlette.routing import Router
    app = Router(routes=routes)
    client = TestClient(app, raise_server_exceptions=True)
    resp = client.get("/v1/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "nodes" in data
    assert data["nodes"] >= 2  # entry + security


# ── list nodes ─────────────────────────────────────────────────────────────────

def test_list_nodes_returns_all(project_root, routes):
    from starlette.testclient import TestClient
    from starlette.routing import Router
    client = TestClient(Router(routes=routes))
    resp = client.get("/v1/nodes")
    assert resp.status_code == 200
    nodes = resp.json()["nodes"]
    ids = [n["id"] for n in nodes]
    assert "rules/security" in ids


def test_list_nodes_kind_filter(project_root, routes):
    from starlette.testclient import TestClient
    from starlette.routing import Router
    client = TestClient(Router(routes=routes))
    resp = client.get("/v1/nodes?kind=rule")
    assert resp.status_code == 200
    nodes = resp.json()["nodes"]
    assert all(n["kind"] == "rule" for n in nodes)


# ── get node ───────────────────────────────────────────────────────────────────

def test_get_existing_node(project_root, routes):
    from starlette.testclient import TestClient
    from starlette.routing import Router
    client = TestClient(Router(routes=routes))
    resp = client.get("/v1/nodes/rules/security")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "rules/security"
    assert "body" in data
    assert "frontmatter" in data


def test_get_missing_node_returns_404(project_root, routes):
    from starlette.testclient import TestClient
    from starlette.routing import Router
    client = TestClient(Router(routes=routes))
    resp = client.get("/v1/nodes/rules/nonexistent")
    assert resp.status_code == 404


# ── create node ────────────────────────────────────────────────────────────────

def test_create_managed_skill(project_root, routes):
    from starlette.testclient import TestClient
    from starlette.routing import Router
    client = TestClient(Router(routes=routes))
    payload = {
        "id": "skills/my-new-skill",
        "body": "# My New Skill\n\nDoes stuff.",
        "frontmatter": {"name": "my-new-skill", "description": "Test skill"},
    }
    resp = client.post("/v1/nodes", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["id"] == "skills/my-new-skill"
    assert data["action"] == "created"
    # Verify file was written to managed dir
    expected = project_root / "server/managed/skills/my-new-skill/SKILL.md"
    assert expected.exists()


def test_create_duplicate_node_returns_409(project_root, routes):
    from starlette.testclient import TestClient
    from starlette.routing import Router
    client = TestClient(Router(routes=routes))
    payload = {"id": "rules/security", "body": "# Dupe"}
    resp = client.post("/v1/nodes", json=payload)
    assert resp.status_code == 409


def test_create_node_missing_id_returns_400(project_root, routes):
    from starlette.testclient import TestClient
    from starlette.routing import Router
    client = TestClient(Router(routes=routes))
    resp = client.post("/v1/nodes", json={"body": "no id here"})
    assert resp.status_code == 400


# ── update node ────────────────────────────────────────────────────────────────

def test_update_existing_node(project_root, routes):
    from starlette.testclient import TestClient
    from starlette.routing import Router
    client = TestClient(Router(routes=routes))
    resp = client.put("/v1/nodes/rules/security", json={"body": "# Updated\n\nNew body."})
    assert resp.status_code == 200
    assert resp.json()["action"] == "updated"


def test_update_missing_node_returns_404(project_root, routes):
    from starlette.testclient import TestClient
    from starlette.routing import Router
    client = TestClient(Router(routes=routes))
    resp = client.put("/v1/nodes/rules/ghost", json={"body": "x"})
    assert resp.status_code == 404


def test_update_empty_payload_returns_400(project_root, routes):
    from starlette.testclient import TestClient
    from starlette.routing import Router
    client = TestClient(Router(routes=routes))
    resp = client.put("/v1/nodes/rules/security", json={})
    assert resp.status_code == 400


# ── delete node ────────────────────────────────────────────────────────────────

def test_delete_existing_node(project_root, routes):
    from starlette.testclient import TestClient
    from starlette.routing import Router
    client = TestClient(Router(routes=routes))
    # First create a managed node to delete safely
    client.post("/v1/nodes", json={"id": "rules/to-delete", "body": "# Delete me"})
    resp = client.delete("/v1/nodes/rules/to-delete")
    assert resp.status_code == 200
    assert resp.json()["action"] == "deleted"


def test_delete_missing_node_returns_404(project_root, routes):
    from starlette.testclient import TestClient
    from starlette.routing import Router
    client = TestClient(Router(routes=routes))
    resp = client.delete("/v1/nodes/rules/ghost")
    assert resp.status_code == 404


# ── search ─────────────────────────────────────────────────────────────────────

def test_search_returns_hits(project_root, routes):
    from starlette.testclient import TestClient
    from starlette.routing import Router
    client = TestClient(Router(routes=routes))
    resp = client.get("/v1/search?q=security")
    assert resp.status_code == 200
    data = resp.json()
    assert "hits" in data
    assert len(data["hits"]) >= 1


def test_search_missing_query_returns_400(project_root, routes):
    from starlette.testclient import TestClient
    from starlette.routing import Router
    client = TestClient(Router(routes=routes))
    resp = client.get("/v1/search")
    assert resp.status_code == 400


# ── templates ──────────────────────────────────────────────────────────────────

def test_list_templates_returns_bundled_skills(project_root, routes):
    from starlette.testclient import TestClient
    from starlette.routing import Router
    client = TestClient(Router(routes=routes))
    resp = client.get("/v1/templates")
    assert resp.status_code == 200
    templates = resp.json()["templates"]
    names = [t["name"] for t in templates]
    assert "git-commit" in names


def test_get_template_returns_body(project_root, routes):
    from starlette.testclient import TestClient
    from starlette.routing import Router
    client = TestClient(Router(routes=routes))
    resp = client.get("/v1/templates/git-commit")
    assert resp.status_code == 200
    data = resp.json()
    assert "body" in data
    assert "frontmatter" in data
    assert data["name"] == "git-commit"


def test_get_nonexistent_template_returns_404(project_root, routes):
    from starlette.testclient import TestClient
    from starlette.routing import Router
    client = TestClient(Router(routes=routes))
    resp = client.get("/v1/templates/nonexistent")
    assert resp.status_code == 404


def test_get_template_path_traversal_rejected(project_root, routes):
    from starlette.testclient import TestClient
    from starlette.routing import Router
    client = TestClient(Router(routes=routes))
    resp = client.get("/v1/templates/../etc/passwd")
    # Either 400 (caught by our validation) or 404 (route mismatch) is acceptable.
    assert resp.status_code in (400, 404)


# ── schema changes ────────────────────────────────────────────────────────────

def test_managed_skill_path_maps_to_node_id():
    """id_from_path must resolve managed skill paths."""
    from server.graph.schema import id_from_path
    assert id_from_path("server/managed/skills/foo/SKILL.md") == "skills/foo"


def test_managed_content_path_maps_to_node_id():
    from server.graph.schema import id_from_path
    assert id_from_path("server/managed/content/rules/my-rule.md") == "rules/my-rule"


def test_managed_memory_path_maps_to_node_id():
    from server.graph.schema import id_from_path
    assert id_from_path("server/managed/content/memory/note.md") == "memory/note"


def test_managed_graph_content_path_maps_to_node_id():
    from server.graph.schema import id_from_path
    assert id_from_path("server/managed/content/my-page.md") == "graph-content/my-page"


# ── builder discovers managed files ───────────────────────────────────────────

def test_builder_discovers_managed_skill(tmp_path: Path):
    managed = tmp_path / "server" / "managed" / "skills" / "my-skill"
    managed.mkdir(parents=True)
    (managed / "SKILL.md").write_text(
        "---\nname: my-skill\ndescription: A managed skill\n---\n# My Skill\n"
    )
    from server.graph.builder import build as build_graph
    result = build_graph(tmp_path)
    assert result.store.has_node("skills/my-skill")


def test_managed_overrides_bundled_on_collision(tmp_path: Path):
    # Bundled skill
    bundled = tmp_path / "server" / "skills" / "shared-skill"
    bundled.mkdir(parents=True)
    (bundled / "SKILL.md").write_text(
        "---\nname: shared-skill\ndescription: Bundled\n---\n# Bundled\n"
    )
    # Managed override
    managed = tmp_path / "server" / "managed" / "skills" / "shared-skill"
    managed.mkdir(parents=True)
    (managed / "SKILL.md").write_text(
        "---\nname: shared-skill\ndescription: Managed override\n---\n# Managed\n"
    )
    from server.graph.builder import build as build_graph
    result = build_graph(tmp_path)
    node = result.store.get_node("skills/shared-skill")
    assert node.description == "Managed override"
