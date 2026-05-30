"""BM25 + edge-aware re-rank tests."""
from __future__ import annotations

from graph.schema import Edge, Node
from graph.search import build_bm25_index, load_index, save_index, search
from graph.store import GraphStore


def _make_store_with_bodies():
    store = GraphStore()
    bodies = {
        "skills/fabric-transform": "Silver Gold transformations with Delta MERGE idempotent upsert pattern.",
        "rules/data-engineering": "Pipelines must be idempotent and use MERGE not INSERT OVERWRITE.",
        "skills/fabric-ingest": "Bronze ingestion from raw source files. No MERGE here.",
        "rules/security": "Security rules for secrets handling and PII masking before persistence.",
    }
    for nid, body in bodies.items():
        title = nid.split("/")[-1].replace("-", " ")
        store.add_node(
            Node(id=nid, path=f"{nid}.md", title=title, description="", kind="content", frontmatter={}, mtime=1.0)
        )
    store.add_edge(Edge(src="skills/fabric-transform", dst="rules/data-engineering", kind="curated"))
    return store, bodies


def test_bm25_ranks_direct_match_first():
    store, bodies = _make_store_with_bodies()
    index = build_bm25_index(store, bodies)
    hits = search(store, index, "Silver Gold MERGE upsert", k=3)
    assert hits[0].id == "skills/fabric-transform"
    assert hits[0].why_matched.startswith("direct")


def test_edge_expansion_surfaces_neighbor():
    store, bodies = _make_store_with_bodies()
    index = build_bm25_index(store, bodies)
    hits = search(store, index, "idempotent MERGE", k=4)
    ids = [h.id for h in hits]
    assert "skills/fabric-transform" in ids
    assert "rules/data-engineering" in ids


def test_search_empty_query_returns_nothing():
    store, bodies = _make_store_with_bodies()
    index = build_bm25_index(store, bodies)
    assert search(store, index, "   ") == []


def test_index_json_round_trip(tmp_path):
    store, bodies = _make_store_with_bodies()
    index = build_bm25_index(store, bodies)
    out = tmp_path / "bm25.json"
    save_index(out, index)
    loaded = load_index(out)
    assert loaded.node_ids == index.node_ids
    hits = search(store, loaded, "secrets PII masking", k=2)
    assert hits[0].id == "rules/security"


def test_search_unranked_token_returns_empty_results():
    store, bodies = _make_store_with_bodies()
    index = build_bm25_index(store, bodies)
    hits = search(store, index, "zzz-no-such-token-anywhere", k=5)
    assert hits == []
