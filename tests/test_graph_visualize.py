"""Materialized graph SVG rendering tests."""

from __future__ import annotations

import pickle
import re

import pytest

from graph.schema import Edge, Node
from graph.search import build_bm25_index, save_index
from graph.store import GraphStore
from graph_build.visualize import (
    render_agent_capability_graph_svg,
    render_graph_svg,
    render_materialized_graph_svg,
    validate_materialized_index,
)


def _node(node_id: str, kind: str) -> Node:
    return Node(
        id=node_id,
        path=f"memory/{node_id}.md",
        title=node_id,
        description="",
        kind=kind,
        frontmatter={},
        mtime=1.0,
    )


def _store() -> GraphStore:
    store = GraphStore()
    store.add_node(_node("graph-content/entry", "entry"))
    store.add_node(_node("graph-content/session/session-start", "content"))
    store.add_node(_node("skills/fabric-ingest", "skill"))
    store.add_edge(Edge(src="graph-content/entry", dst="graph-content/session/session-start", kind="curated"))
    store.add_edge(Edge(src="graph-content/session/session-start", dst="skills/fabric-ingest", kind="auto-path"))
    return store


def test_render_materialized_graph_svg_validates_bm25_and_writes_svg(tmp_path):
    store = _store()
    graph_json = tmp_path / "graph.json"
    bm25_path = tmp_path / "graph-bm25.pkl"
    out = tmp_path / "materialized-graph.svg"
    store.save(graph_json, built_by="test")
    save_index(
        bm25_path,
        build_bm25_index(
            store,
            {
                "graph-content/entry": "mandatory setup gate",
                "graph-content/session/session-start": "session traversal order",
                "skills/fabric-ingest": "ingest staged files into bronze",
            },
        ),
    )

    result = render_materialized_graph_svg(
        graph_json,
        bm25_path,
        out,
        width=640,
        height=420,
        seed=3,
        edge_mode="all",
    )

    assert result == out
    text = out.read_text(encoding="utf-8")
    assert text.startswith('<?xml version="1.0" encoding="UTF-8"?>')
    assert "Materialized knowledge graph" in text
    assert 'data-node-count="3"' in text
    assert 'data-edge-count="2"' in text
    assert 'data-layout="top-down"' in text
    assert 'data-edge-mode="all"' in text
    assert 'data-central-node="graph-content/entry"' in text
    assert 'data-visible-edge-count="2"' in text
    assert 'data-node-id="graph-content/entry"' in text
    assert 'data-kind="auto-path"' in text


def test_validate_materialized_index_rejects_stale_bm25(tmp_path):
    store = _store()
    bm25_path = tmp_path / "graph-bm25.pkl"
    with bm25_path.open("wb") as fh:
        pickle.dump({"node_ids": ["graph-content/entry", "ghost"], "bm25": object()}, fh)

    with pytest.raises(ValueError, match="node sets differ"):
        validate_materialized_index(store, bm25_path)

def test_top_down_layout_node_boxes_do_not_overlap(tmp_path):
    store = GraphStore()
    previous_id = None
    for idx in range(32):
        node_id = f"skills/node-{idx:02d}"
        store.add_node(_node(node_id, "skill" if idx % 2 else "content"))
        if previous_id is not None:
            store.add_edge(Edge(src=previous_id, dst=node_id, kind="curated"))
        previous_id = node_id
    graph_json = tmp_path / "graph.json"
    bm25_path = tmp_path / "graph-bm25.pkl"
    out = tmp_path / "materialized-graph.svg"
    store.save(graph_json, built_by="test")
    save_index(bm25_path, build_bm25_index(store, {node_id: node_id for node_id in store.graph.nodes}))

    render_materialized_graph_svg(graph_json, bm25_path, out, width=800, height=600, seed=3)

    text = out.read_text(encoding="utf-8")
    assert 'data-layout="top-down"' in text
    boxes = [tuple(float(part) for part in raw.split(",")) for raw in re.findall(r'data-node-box="([^\"]+)"', text)]
    assert len(boxes) == 32
    for x, y, width, height in boxes:
        assert x >= 0
        assert y >= 0
        assert x + width <= 800
        assert y + height <= 600
    for idx, (x1, y1, w1, h1) in enumerate(boxes):
        for x2, y2, w2, h2 in boxes[idx + 1 :]:
            horizontal_gap = x1 + w1 <= x2 or x2 + w2 <= x1
            vertical_gap = y1 + h1 <= y2 or y2 + h2 <= y1
            assert horizontal_gap or vertical_gap


def test_render_graph_svg_without_bm25(tmp_path):
    store = GraphStore()
    store.add_node(
        Node(
            id="capabilities/orchestrator",
            path="",
            title="Orchestrator capability",
            description="",
            kind="capability",
            frontmatter={},
            mtime=0.0,
        )
    )
    store.add_node(
        Node(
            id="capabilities/developer",
            path="",
            title="Developer capability",
            description="",
            kind="capability",
            frontmatter={},
            mtime=0.0,
        )
    )
    store.add_node(_node("graph-content/workflow/notebook", "content"))
    store.add_edge(Edge(src="capabilities/orchestrator", dst="capabilities/developer", kind="capability-route"))
    store.add_edge(Edge(src="capabilities/developer", dst="graph-content/workflow/notebook", kind="capability-covers"))

    out = tmp_path / "agent-capabilities.svg"
    result = render_graph_svg(store, out, title="Agent capability graph", edge_mode="all")

    assert result == out
    text = out.read_text(encoding="utf-8")
    assert text.startswith('<?xml version="1.0" encoding="UTF-8"?>')
    assert "Agent capability graph" in text
    assert 'data-node-id="capabilities/orchestrator"' in text
    assert 'data-kind="capability-route"' in text
    assert 'data-kind="capability-covers"' in text


def test_render_agent_capability_graph_svg_from_disk(tmp_path):
    store = GraphStore()
    store.add_node(
        Node(
            id="capabilities/orchestrator",
            path="",
            title="Orchestrator capability",
            description="",
            kind="capability",
            frontmatter={},
            mtime=0.0,
        )
    )
    graph_json = tmp_path / "agent-capabilities.json"
    store.save(graph_json, built_by="test")
    out = tmp_path / "agent-capabilities.svg"

    result = render_agent_capability_graph_svg(graph_json, out)

    assert result == out
    text = out.read_text(encoding="utf-8")
    assert "Agent capability graph" in text
    assert 'data-node-id="capabilities/orchestrator"' in text


def test_default_render_hides_non_tree_edges_for_readability(tmp_path):
    store = _store()
    store.add_edge(Edge(src="skills/fabric-ingest", dst="graph-content/session/session-start", kind="auto-path"))
    graph_json = tmp_path / "graph.json"
    bm25_path = tmp_path / "graph-bm25.pkl"
    out = tmp_path / "materialized-graph.svg"
    store.save(graph_json, built_by="test")
    save_index(
        bm25_path,
        build_bm25_index(
            store,
            {
                "graph-content/entry": "mandatory setup gate",
                "graph-content/session/session-start": "session traversal order",
                "skills/fabric-ingest": "ingest staged files into bronze",
            },
        ),
    )

    render_materialized_graph_svg(graph_json, bm25_path, out, width=640, height=420, seed=3)

    text = out.read_text(encoding="utf-8")
    assert 'data-edge-count="3"' in text
    assert 'data-edge-mode="tree"' in text
    assert 'data-visible-edge-count="2"' in text
