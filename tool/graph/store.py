"""networkx-backed graph store with atomic JSON save/load."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import networkx as nx

from .lock import file_lock
from .schema import Edge, Node

SCHEMA_VERSION = 1


class GraphStore:
    def __init__(self) -> None:
        self.graph: nx.DiGraph = nx.DiGraph()
        self.built_at: str = ""
        self.built_by: str = ""

    def add_node(self, node: Node) -> None:
        if node.id in self.graph:
            raise ValueError(f"duplicate node id: {node.id}")
        self.graph.add_node(node.id, **node.to_dict())

    def has_node(self, node_id: str) -> bool:
        return node_id in self.graph

    def get_node(self, node_id: str) -> Node:
        if node_id not in self.graph:
            raise KeyError(node_id)
        return Node.from_dict(self.graph.nodes[node_id])

    def add_edge(self, edge: Edge) -> None:
        if edge.src not in self.graph or edge.dst not in self.graph:
            raise ValueError(f"edge endpoints must exist: {edge.src} -> {edge.dst}")
        existing = self.graph.get_edge_data(edge.src, edge.dst)
        if existing is None or existing.get("kind") == "auto-path" and edge.kind == "curated":
            self.graph.add_edge(edge.src, edge.dst, kind=edge.kind)

    def linked(self, node_id: str, kinds: Iterable[str] | None = None) -> list[Node]:
        if node_id not in self.graph:
            raise KeyError(node_id)
        kind_filter = set(kinds) if kinds else None
        out: list[Node] = []
        for neighbor in self.graph.successors(node_id):
            node = Node.from_dict(self.graph.nodes[neighbor])
            if kind_filter is None or node.kind in kind_filter:
                out.append(node)
        return out

    def kinds(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for _, data in self.graph.nodes(data=True):
            counts[data.get("kind", "unknown")] = counts.get(data.get("kind", "unknown"), 0) + 1
        return counts

    def orphans(self) -> list[str]:
        return [
            nid
            for nid in self.graph.nodes
            if self.graph.in_degree(nid) == 0 and self.graph.out_degree(nid) == 0
        ]

    def to_payload(self, built_by: str) -> dict:
        return {
            "version": SCHEMA_VERSION,
            "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "built_by": built_by,
            "nodes": [Node.from_dict(self.graph.nodes[n]).to_dict() for n in sorted(self.graph.nodes)],
            "edges": [
                {"src": s, "dst": d, "kind": data.get("kind", "curated")}
                for s, d, data in sorted(self.graph.edges(data=True), key=lambda e: (e[0], e[1]))
            ],
        }

    def save(self, path: Path, *, built_by: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = path.parent / f"{path.name}.lock"
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        payload = self.to_payload(built_by=built_by)
        with file_lock(lock_path):
            with open(tmp_path, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2, sort_keys=False)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_path, path)
        self.built_at = payload["built_at"]
        self.built_by = built_by

    @classmethod
    def load(cls, path: Path) -> "GraphStore":
        with open(path, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
        if payload.get("version") != SCHEMA_VERSION:
            raise ValueError(f"unsupported graph schema version: {payload.get('version')}")
        store = cls()
        for raw_node in payload.get("nodes", []):
            store.graph.add_node(raw_node["id"], **raw_node)
        for raw_edge in payload.get("edges", []):
            edge = Edge.from_dict(raw_edge)
            store.graph.add_edge(edge.src, edge.dst, kind=edge.kind)
        store.built_at = payload.get("built_at", "")
        store.built_by = payload.get("built_by", "")
        return store
