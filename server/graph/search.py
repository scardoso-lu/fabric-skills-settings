"""BM25 + edge-aware re-rank over the knowledge graph."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from rank_bm25 import BM25Okapi

from .store import GraphStore

_TOKEN_RE = re.compile(r"[A-Za-z0-9_-]+")
NEIGHBOR_BONUS = 0.5


def tokenize(text: str) -> list[str]:
    return [tok.lower() for tok in _TOKEN_RE.findall(text)]


@dataclass
class BM25Index:
    node_ids: list[str]
    bm25: BM25Okapi
    # corpus is stored alongside the BM25 object so save_index can serialise
    # to JSON without depending on pickle (which allows arbitrary code execution
    # when loading untrusted data — OWASP A03).
    corpus: list[list[str]] = field(default_factory=list)


def build_bm25_index(store: GraphStore, bodies: dict[str, str]) -> BM25Index:
    """Tokenize title + description + body per node and build a BM25 index.

    Title and description are duplicated three and two times respectively so
    matches there outrank pure body hits without rolling a custom scorer.
    """
    node_ids = sorted(store.graph.nodes)
    corpus: list[list[str]] = []
    for nid in node_ids:
        data = store.graph.nodes[nid]
        title = data.get("title", "") or ""
        description = data.get("description", "") or ""
        body = bodies.get(nid, "")
        tokens = tokenize(title) * 3 + tokenize(description) * 2 + tokenize(body)
        corpus.append(tokens or [nid])
    return BM25Index(node_ids=node_ids, bm25=BM25Okapi(corpus), corpus=corpus)


def save_index(path: Path, index: BM25Index) -> None:
    """Serialise the BM25 index to JSON (safe, no pickle/RCE risk)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    payload = {"node_ids": index.node_ids, "corpus": index.corpus}
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, separators=(",", ":"))
    tmp.replace(path)


def load_index(path: Path) -> BM25Index:
    """Load and reconstruct a BM25 index from its JSON serialisation."""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    node_ids: list[str] = data["node_ids"]
    corpus: list[list[str]] = data["corpus"]
    return BM25Index(node_ids=node_ids, bm25=BM25Okapi(corpus), corpus=corpus)


@dataclass
class SearchHit:
    id: str
    title: str
    score: float
    why_matched: str


def search(
    store: GraphStore,
    index: BM25Index,
    query: str,
    *,
    k: int = 5,
    bm25_top_k: int = 10,
) -> list[SearchHit]:
    """Return top-k hits: BM25 over (title+description+body), then re-rank with 1-hop edge bonus.

    For each BM25 candidate, the bonus is `NEIGHBOR_BONUS * max(score of any 1-hop neighbor in the candidate pool)`.
    This surfaces nodes that are structurally adjacent to direct matches.
    """
    tokens = tokenize(query)
    if not tokens:
        return []
    scores = index.bm25.get_scores(tokens)
    pairs = list(zip(index.node_ids, scores))
    pairs.sort(key=lambda pair: pair[1], reverse=True)
    top = pairs[: max(bm25_top_k, k)]

    score_map = {nid: float(sc) for nid, sc in top}
    combined: dict[str, tuple[float, str]] = {}
    for nid, sc in top:
        if sc <= 0:
            continue
        combined[nid] = (float(sc), "direct")

    for nid, sc in top:
        if sc <= 0:
            continue
        for neighbor in store.graph.successors(nid):
            n_score = score_map.get(neighbor, 0.0)
            bonus = NEIGHBOR_BONUS * n_score
            if bonus <= 0:
                continue
            cur = combined.get(nid, (0.0, "direct"))
            new_total = cur[0] + bonus
            combined[nid] = (new_total, "direct + neighbor" if cur[1] == "direct" else cur[1])
            if neighbor not in combined:
                combined[neighbor] = (NEIGHBOR_BONUS * float(sc), f"via {nid}")

    ranked = sorted(combined.items(), key=lambda item: item[1][0], reverse=True)[:k]
    out: list[SearchHit] = []
    for nid, (score, why) in ranked:
        data = store.graph.nodes[nid]
        out.append(SearchHit(id=nid, title=data.get("title", nid), score=round(score, 4), why_matched=why))
    return out
