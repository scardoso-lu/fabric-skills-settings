"""MCP graph-server dispatch tests (read-only surface, Phase P2)."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SERVER_PATH = ROOT / "tool" / "mcp" / "graph-server.py"


def _load_server_module(tmp_root: Path):
    """Load graph-server.py as a module rebound to a temp ROOT for hermetic tests."""
    spec = importlib.util.spec_from_file_location("graph_server_under_test", SERVER_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.ROOT = tmp_root
    module.GRAPH_DIR = tmp_root / "memory" / ".graph"
    module.GRAPH_PATH = module.GRAPH_DIR / "graph.json"
    module.BM25_PATH = module.GRAPH_DIR / "graph-bm25.pkl"
    module._store = None
    module._index = None
    module._index_mtime = 0.0
    return module


def _build_graph(tmp_root: Path) -> None:
    from graph.builder import build
    from graph.search import build_bm25_index, save_index

    _write(tmp_root / "memory" / "graph-content" / "entry.md",
           "---\nname: entry\ndescription: Mandatory setup gate.\nlinks:\n  - rules/security\n---\n\n# Mandatory setup gate\nVerify .env, fab, fab auth. Setup incomplete blocks all work.\n")
    _write(tmp_root / "rules" / "security.md",
           "---\nname: security\ndescription: Credential and PII rules\n---\n\n# Security\nNever commit credentials.\n")
    _write(tmp_root / "rules" / "data-engineering.md",
           "---\nname: data-engineering\ndescription: Pipeline rules\n---\n\n# Data engineering\nIdempotent MERGE only.\n")
    _write(tmp_root / "profiles" / "skills" / "fabric-transform" / "SKILL.md",
           "---\nname: fabric-transform\ndescription: Silver/Gold MERGE\n---\n\n# fabric-transform\nDelta MERGE pattern.\n")

    result = build(tmp_root)
    assert not result.errors, result.errors
    graph_dir = tmp_root / "memory" / ".graph"
    result.store.save(graph_dir / "graph.json", built_by="test")
    save_index(graph_dir / "graph-bm25.pkl",
               build_bm25_index(result.store, _bodies(tmp_root, result.store)))


def _bodies(root: Path, store) -> dict[str, str]:
    from graph.schema import parse_frontmatter

    out: dict[str, str] = {}
    for nid in store.graph.nodes:
        rel = store.graph.nodes[nid]["path"]
        _, body = parse_frontmatter((root / rel).read_text(encoding="utf-8"))
        out[nid] = body
    return out


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def server(tmp_path):
    _build_graph(tmp_path)
    return _load_server_module(tmp_path)


def _parse_text(result: dict) -> dict:
    return json.loads(result["content"][0]["text"])


def test_get_entry_returns_entry_node_with_body_and_links(server):
    payload = _parse_text(server._dispatch("graph_get_entry", {}))
    assert payload["id"] == "graph-content/entry"
    assert "Mandatory setup gate" in payload["body"]
    assert "rules/security" in payload["links"]


def test_get_node_returns_body(server):
    payload = _parse_text(server._dispatch("graph_get_node", {"id": "rules/security"}))
    assert payload["id"] == "rules/security"
    assert "Never commit credentials" in payload["body"]


def test_get_node_rejects_unknown_id(server):
    with pytest.raises(RuntimeError, match="unknown node id"):
        server._dispatch("graph_get_node", {"id": "ghost/node"})


def test_get_linked_returns_neighbors_with_edge_kind(server):
    payload = _parse_text(server._dispatch("graph_get_linked", {"id": "graph-content/entry"}))
    assert payload["id"] == "graph-content/entry"
    ids = [n["id"] for n in payload["neighbors"]]
    assert "rules/security" in ids
    sec = next(n for n in payload["neighbors"] if n["id"] == "rules/security")
    assert sec["edge_kind"] in {"curated", "auto-path"}


def test_get_linked_filters_by_kind(server):
    payload = _parse_text(
        server._dispatch("graph_get_linked", {"id": "graph-content/entry", "kinds": ["skill"]})
    )
    assert payload["neighbors"] == []


def test_search_returns_ranked_hits(server):
    payload = _parse_text(server._dispatch("graph_search", {"query": "MERGE Silver Delta", "k": 3}))
    ids = [h["id"] for h in payload["hits"]]
    assert "skills/fabric-transform" in ids


def test_search_clamps_k(server):
    payload = _parse_text(server._dispatch("graph_search", {"query": "rules", "k": 999}))
    assert len(payload["hits"]) <= 25


def test_list_kinds_reports_counts(server):
    payload = _parse_text(server._dispatch("graph_list_kinds", {}))
    assert payload["total"] == 4
    assert payload["counts"].get("entry") == 1
    assert payload["counts"].get("rule") == 2


def test_dispatch_rejects_unknown_tool(server):
    with pytest.raises(RuntimeError, match="unknown tool"):
        server._dispatch("graph_no_such_tool", {})


def test_get_entry_errors_when_entry_node_missing(tmp_path):
    """If the content tree isn't installed yet, get_entry must fail with a clear message."""
    from graph.schema import Node
    from graph.store import GraphStore

    store = GraphStore()
    store.add_node(Node(id="rules/security", path="rules/security.md", title="s",
                         description="", kind="rule", frontmatter={}, mtime=1.0))
    (tmp_path / "memory" / ".graph").mkdir(parents=True)
    store.save(tmp_path / "memory" / ".graph" / "graph.json", built_by="test")
    module = _load_server_module(tmp_path)
    with pytest.raises(RuntimeError, match="entry node"):
        module._dispatch("graph_get_entry", {})
