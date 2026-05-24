"""GraphStore round-trip + atomic write tests."""
from __future__ import annotations

import json

import pytest

from graph.schema import Edge, Node
from graph.store import GraphStore


def _node(node_id: str, kind: str = "content") -> Node:
    return Node(
        id=node_id,
        path=f"memory/{node_id}.md",
        title=node_id,
        description="",
        kind=kind,
        frontmatter={},
        mtime=1.0,
    )


def test_add_node_rejects_duplicates():
    store = GraphStore()
    store.add_node(_node("a"))
    with pytest.raises(ValueError):
        store.add_node(_node("a"))


def test_add_edge_requires_both_endpoints():
    store = GraphStore()
    store.add_node(_node("a"))
    with pytest.raises(ValueError):
        store.add_edge(Edge(src="a", dst="ghost", kind="curated"))


def test_curated_edge_overwrites_auto_edge():
    store = GraphStore()
    store.add_node(_node("a"))
    store.add_node(_node("b"))
    store.add_edge(Edge(src="a", dst="b", kind="auto-path"))
    store.add_edge(Edge(src="a", dst="b", kind="curated"))
    assert store.graph.get_edge_data("a", "b")["kind"] == "curated"


def test_round_trip_save_load(tmp_path):
    store = GraphStore()
    store.add_node(_node("a", kind="entry"))
    store.add_node(_node("b", kind="skill"))
    store.add_edge(Edge(src="a", dst="b", kind="curated"))
    out = tmp_path / "graph.json"
    store.save(out, built_by="test")

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["version"] == 1
    assert payload["built_by"] == "test"
    assert {n["id"] for n in payload["nodes"]} == {"a", "b"}
    assert payload["edges"] == [{"src": "a", "dst": "b", "kind": "curated"}]

    loaded = GraphStore.load(out)
    assert loaded.kinds() == {"entry": 1, "skill": 1}
    assert loaded.get_node("a").kind == "entry"
    assert [(s, d) for s, d, _ in loaded.graph.edges(data=True)] == [("a", "b")]


def test_save_is_atomic_via_temp_file(tmp_path):
    store = GraphStore()
    store.add_node(_node("a"))
    out = tmp_path / "graph.json"
    store.save(out, built_by="test")
    assert out.exists()
    assert not out.with_suffix(".json.tmp").exists()


def test_orphans_returns_unlinked_nodes():
    store = GraphStore()
    store.add_node(_node("a"))
    store.add_node(_node("b"))
    store.add_node(_node("c"))
    store.add_edge(Edge(src="a", dst="b", kind="curated"))
    assert store.orphans() == ["c"]


def test_linked_filters_by_kind():
    store = GraphStore()
    store.add_node(_node("a", kind="content"))
    store.add_node(_node("b", kind="skill"))
    store.add_node(_node("c", kind="rule"))
    store.add_edge(Edge(src="a", dst="b", kind="curated"))
    store.add_edge(Edge(src="a", dst="c", kind="curated"))
    skills = store.linked("a", kinds=["skill"])
    assert [n.id for n in skills] == ["b"]
