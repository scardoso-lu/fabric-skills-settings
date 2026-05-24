"""Render materialized knowledge graph artifacts as an SVG image."""

from __future__ import annotations

import argparse
import html
import math
from collections import deque
from pathlib import Path
from typing import Any, Literal

import networkx as nx

from graph.search import load_index
from graph.store import GraphStore

LayoutMode = Literal["auto", "top-down", "spring"]
EdgeMode = Literal["tree", "curated", "all", "none"]

NODE_COLORS = {
    "entry": "#d64545",
    "content": "#4575b4",
    "skill": "#2f9e44",
    "rule": "#8e44ad",
    "memory": "#6c757d",
    "capability": "#1971c2",
}
DEFAULT_NODE_COLOR = "#495057"
EDGE_COLORS = {
    "curated": "#343a40",
    "auto-path": "#adb5bd",
    "capability-route": "#1971c2",
    "capability-covers": "#74c0fc",
}
KIND_ORDER = {
    "entry": 0,
    "capability": 1,
    "content": 2,
    "skill": 3,
    "rule": 4,
    "memory": 5,
}


def validate_materialized_index(store: GraphStore, bm25_path: Path) -> None:
    """Raise when the BM25 artifact does not describe the same node set."""
    index = load_index(bm25_path)
    graph_nodes = set(store.graph.nodes)
    index_nodes = set(index.node_ids)
    missing_from_index = sorted(graph_nodes - index_nodes)
    missing_from_graph = sorted(index_nodes - graph_nodes)
    if missing_from_index or missing_from_graph:
        detail = []
        if missing_from_index:
            detail.append("missing from BM25: " + ", ".join(missing_from_index[:5]))
        if missing_from_graph:
            detail.append("missing from graph: " + ", ".join(missing_from_graph[:5]))
        raise ValueError("graph.json and graph-bm25.pkl node sets differ; " + "; ".join(detail))


def render_graph_svg(
    store: GraphStore,
    output: Path,
    *,
    title: str = "Materialized knowledge graph",
    source: Path | None = None,
    width: int = 1800,
    height: int = 1200,
    seed: int = 17,
    layout: LayoutMode = "auto",
    edge_mode: EdgeMode = "tree",
    central_node: str | None = None,
) -> Path:
    """Render any GraphStore as an SVG. No BM25 dependency.

    ``central_node`` forces a specific node id as the layout root (for top-down)
    and edge-tree origin. When None, falls back to ``_central_node`` heuristics.
    """
    output.parent.mkdir(parents=True, exist_ok=True)
    resolved_layout = _resolve_layout(store.graph, layout=layout, width=width, height=height)
    explicit_central = central_node if central_node and central_node in store.graph else None
    if resolved_layout == "top-down":
        positions, boxes, layout_central = _top_down_card_layout(
            store.graph, width=width, height=height, central=explicit_central
        )
        central_node = layout_central
    else:
        positions = _spring_layout(store.graph, width=width, height=height, seed=seed)
        boxes = {}
        central_node = explicit_central or _central_node(store.graph)
    svg = _svg(
        store,
        positions,
        boxes,
        width=width,
        height=height,
        source=source,
        layout_name=resolved_layout,
        edge_mode=edge_mode,
        central_node=central_node,
        title=title,
    )
    output.write_text(svg, encoding="utf-8")
    return output


def render_materialized_graph_svg(
    graph_json: Path,
    bm25_path: Path,
    output: Path,
    *,
    width: int = 1800,
    height: int = 1200,
    seed: int = 17,
    layout: LayoutMode = "auto",
    edge_mode: EdgeMode = "tree",
) -> Path:
    """Render graph.json as an SVG after validating the adjacent BM25 index."""
    store = GraphStore.load(graph_json)
    validate_materialized_index(store, bm25_path)
    return render_graph_svg(
        store,
        output,
        title="Materialized knowledge graph",
        source=graph_json,
        width=width,
        height=height,
        seed=seed,
        layout=layout,
        edge_mode=edge_mode,
    )


def render_agent_capability_graph_svg(
    graph_json: Path,
    output: Path,
    *,
    width: int = 1800,
    height: int = 1200,
    seed: int = 17,
    layout: LayoutMode = "auto",
    edge_mode: EdgeMode = "all",
    central_node: str | None = "capabilities/orchestrator",
) -> Path:
    """Render an agent-capabilities graph as an SVG. No BM25 required."""
    store = GraphStore.load(graph_json)
    return render_graph_svg(
        store,
        output,
        title="Agent capability graph",
        source=graph_json,
        width=width,
        height=height,
        seed=seed,
        layout=layout,
        edge_mode=edge_mode,
        central_node=central_node,
    )


def _resolve_layout(graph: nx.DiGraph, *, layout: LayoutMode, width: int, height: int) -> str:
    if layout != "auto":
        return layout
    if graph.number_of_nodes() > 12 or width <= 1000 or height <= 800:
        return "top-down"
    return "spring"


def _central_node(graph: nx.DiGraph) -> str | None:
    if not graph.nodes:
        return None
    for preferred in ("graph-content/entry", "entry"):
        if preferred in graph:
            return preferred
    entry_nodes = [node_id for node_id, data in graph.nodes(data=True) if data.get("kind") == "entry"]
    if entry_nodes:
        return sorted(entry_nodes)[0]
    return max(graph.nodes, key=lambda node_id: (graph.degree(node_id), str(node_id)))


def _spring_layout(graph: nx.DiGraph, *, width: int, height: int, seed: int) -> dict[str, tuple[float, float]]:
    nodes = list(graph.nodes)
    if not nodes:
        return {}
    if len(nodes) == 1:
        return {nodes[0]: (width / 2, height / 2)}

    undirected = graph.to_undirected()
    raw = nx.spring_layout(
        undirected,
        seed=seed,
        k=1.6 / math.sqrt(max(len(nodes), 1)),
        iterations=250,
    )
    return _scale_positions(raw, width=width, height=height, margin=140)


def _top_down_card_layout(
    graph: nx.DiGraph,
    *,
    width: int,
    height: int,
    central: str | None = None,
) -> tuple[dict[str, tuple[float, float]], dict[str, tuple[float, float, float, float]], str | None]:
    if central is None or central not in graph:
        central = _central_node(graph)
    if central is None:
        return {}, {}, None

    levels = _levels_from_central(graph, central)
    left = 48
    right = 48
    top = 104
    bottom = 56
    gap_x = 18
    max_card_width = 360
    min_card_width = 170
    effective_min_card_width = min_card_width
    row_width = width - left - right
    max_per_row = max(1, int((row_width + gap_x) // (min_card_width + gap_x)))

    display_rows: list[list[str]] = []
    for level in sorted(levels):
        nodes = sorted(levels[level], key=lambda node_id: (_sort_key(graph, node_id)))
        for start in range(0, len(nodes), max_per_row):
            display_rows.append(nodes[start : start + max_per_row])

    min_gap_y = 12
    min_card_height = 34
    max_rows_for_canvas = max(1, int((height - top - bottom + min_gap_y) // (min_card_height + min_gap_y)))
    if len(display_rows) > max_rows_for_canvas:
        ordered_nodes: list[str] = []
        for level in sorted(levels):
            ordered_nodes.extend(sorted(levels[level], key=lambda node_id: (_sort_key(graph, node_id))))
        remaining = [node_id for node_id in ordered_nodes if node_id != central]
        remaining_row_capacity = max(1, max_rows_for_canvas - 1)
        max_per_row = max(max_per_row, math.ceil(len(remaining) / remaining_row_capacity))
        effective_min_card_width = 120
        display_rows = [[central]]
        for start in range(0, len(remaining), max_per_row):
            display_rows.append(remaining[start : start + max_per_row])

    max_nodes_in_row = max((len(nodes) for nodes in display_rows), default=1)
    gap_y = max(min_gap_y, min(80, (height - top - bottom) / max(len(display_rows), 1) * 0.22))
    card_height = max(
        34,
        min(48, (height - top - bottom - gap_y * max(len(display_rows) - 1, 0)) / max(len(display_rows), 1)),
    )
    card_width = min(
        max_card_width,
        max(effective_min_card_width, (row_width - gap_x * max(max_nodes_in_row - 1, 0)) / max(max_nodes_in_row, 1)),
    )

    positions: dict[str, tuple[float, float]] = {}
    boxes: dict[str, tuple[float, float, float, float]] = {}
    for row_idx, nodes in enumerate(display_rows):
        total_width = len(nodes) * card_width + max(len(nodes) - 1, 0) * gap_x
        start_x = left + max(0, (row_width - total_width) / 2)
        y = top + row_idx * (card_height + gap_y)
        for idx, node_id in enumerate(nodes):
            x = start_x + idx * (card_width + gap_x)
            boxes[node_id] = (x, y, card_width, card_height)
            positions[node_id] = (x + card_width / 2, y + card_height / 2)
    return positions, boxes, central


def _levels_from_central(graph: nx.DiGraph, central: str) -> dict[int, list[str]]:
    levels: dict[str, int] = {central: 0}
    queue: deque[str] = deque([central])
    while queue:
        node_id = queue.popleft()
        for neighbor in sorted(graph.successors(node_id)):
            if neighbor not in levels:
                levels[neighbor] = levels[node_id] + 1
                queue.append(neighbor)

    undirected = graph.to_undirected()
    fallback_base = max(levels.values(), default=0) + 1
    for node_id in sorted(graph.nodes):
        if node_id in levels:
            continue
        try:
            levels[node_id] = fallback_base + nx.shortest_path_length(undirected, central, node_id)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            levels[node_id] = fallback_base + KIND_ORDER.get(str(graph.nodes[node_id].get("kind", "unknown")), 99)

    grouped: dict[int, list[str]] = {}
    for node_id, level in levels.items():
        grouped.setdefault(level, []).append(node_id)
    return grouped


def _sort_key(graph: nx.DiGraph, node_id: str) -> tuple[int, int, str]:
    data = graph.nodes[node_id]
    return (KIND_ORDER.get(str(data.get("kind", "unknown")), 99), -graph.degree(node_id), str(node_id))


def _scale_positions(
    raw: dict[str, Any],
    *,
    width: int,
    height: int,
    margin: int,
) -> dict[str, tuple[float, float]]:
    xs = [float(pos[0]) for pos in raw.values()]
    ys = [float(pos[1]) for pos in raw.values()]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max(max_x - min_x, 1e-9)
    span_y = max(max_y - min_y, 1e-9)

    out: dict[str, tuple[float, float]] = {}
    for node_id, pos in raw.items():
        x = margin + ((float(pos[0]) - min_x) / span_x) * (width - 2 * margin)
        y = margin + ((float(pos[1]) - min_y) / span_y) * (height - 2 * margin)
        out[node_id] = (x, y)
    return out


def _svg(
    store: GraphStore,
    positions: dict[str, tuple[float, float]],
    boxes: dict[str, tuple[float, float, float, float]],
    *,
    width: int,
    height: int,
    source: Path | None,
    layout_name: str,
    edge_mode: EdgeMode,
    central_node: str | None,
    title: str = "Materialized knowledge graph",
) -> str:
    graph = store.graph
    node_count = graph.number_of_nodes()
    edge_count = graph.number_of_edges()
    visible_edges = _visible_edges(graph, edge_mode=edge_mode, central_node=central_node)
    kind_counts = store.kinds()
    source_text = html.escape(str(source)) if source is not None else "(in-memory store)"

    parts: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc" data-layout="{layout_name}" data-edge-mode="{edge_mode}" data-central-node="{html.escape(central_node or "")}">',
        f'<title id="title">{html.escape(title)}</title>',
        f'<desc id="desc">{node_count} nodes and {edge_count} directed edges loaded from {source_text}.</desc>',
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#495057"/></marker></defs>',
        '<rect width="100%" height="100%" fill="#f8f9fa"/>',
        '<style>.label{font:11px Arial,sans-serif;fill:#212529}.small{font:10px Arial,sans-serif;fill:#495057}.title{font:700 24px Arial,sans-serif;fill:#212529}.meta{font:13px Arial,sans-serif;fill:#495057}.card-label{font:12px Arial,sans-serif;fill:#212529}.kind-label{font:10px Arial,sans-serif;fill:#6c757d}</style>',
        f'<text x="48" y="42" class="title">{html.escape(title)}</text>',
        f'<text x="48" y="68" class="meta" data-node-count="{node_count}" data-edge-count="{edge_count}" data-visible-edge-count="{len(visible_edges)}">{node_count} nodes, {len(visible_edges)} shown edges ({edge_mode}), built_by={html.escape(store.built_by or "unknown")}</text>',
    ]

    for src, dst, data in visible_edges:
        if src not in positions or dst not in positions:
            continue
        kind = data.get("kind", "curated")
        color = EDGE_COLORS.get(kind, "#868e96")
        dash = ' stroke-dasharray="5 5"' if kind == "auto-path" else ""
        opacity = "0.42" if boxes else "0.62"
        path = _edge_path(src, dst, positions, boxes)
        parts.append(
            f'<path data-kind="{html.escape(kind)}" d="{path}" fill="none" stroke="{color}" stroke-width="1.1" opacity="{opacity}" marker-end="url(#arrow)"{dash}/>'
        )

    degrees = dict(graph.degree())
    for node_id in sorted(graph.nodes):
        data = graph.nodes[node_id]
        kind = data.get("kind", "unknown")
        color = NODE_COLORS.get(kind, DEFAULT_NODE_COLOR)
        title = data.get("title") or node_id
        if node_id in boxes:
            x, y, card_width, card_height = boxes[node_id]
            cx = x + card_width / 2
            radius = min(16.0, max(7.0, min(card_width, card_height) * 0.32))
            cy = y + radius + 2
            label = _short_label(node_id, max_len=max(10, int(card_width / 6.5)))
            stroke_width = "3" if node_id == central_node else "1.8"
            label_y = min(y + card_height - 2, cy + radius + 12)
            parts.append(
                f'<g data-node-id="{html.escape(node_id)}" data-kind="{html.escape(kind)}" data-node-box="{x:.1f},{y:.1f},{card_width:.1f},{card_height:.1f}">'
                f'<title>{html.escape(node_id)} - {html.escape(str(title))}</title>'
                f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{radius:.1f}" fill="{color}" stroke="#fff" stroke-width="{stroke_width}"/>'
                f'<text x="{cx:.1f}" y="{label_y:.1f}" class="card-label" text-anchor="middle">{html.escape(label)}</text>'
                '</g>'
            )
        else:
            x, y = positions[node_id]
            radius = min(20, 7 + degrees.get(node_id, 0) * 1.8)
            label = _short_label(node_id)
            parts.append(
                f'<g data-node-id="{html.escape(node_id)}" data-kind="{html.escape(kind)}">'
                f'<title>{html.escape(node_id)} - {html.escape(str(title))}</title>'
                f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius:.1f}" fill="{color}" stroke="#fff" stroke-width="2"/>'
                f'<text x="{x + radius + 4:.1f}" y="{y + 4:.1f}" class="label">{html.escape(label)}</text>'
                '</g>'
            )

    parts.extend(_legend(kind_counts, width=width, height=height, compact=bool(boxes), edge_mode=edge_mode))
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def _visible_edges(
    graph: nx.DiGraph,
    *,
    edge_mode: EdgeMode,
    central_node: str | None,
) -> list[tuple[str, str, dict[str, Any]]]:
    if edge_mode == "none":
        return []
    edges = sorted(graph.edges(data=True), key=lambda e: (e[0], e[1]))
    if edge_mode == "tree":
        return _tree_edges(graph, central_node=central_node)
    if edge_mode == "curated":
        return [(src, dst, data) for src, dst, data in edges if data.get("kind", "curated") == "curated"]
    return edges


def _tree_edges(graph: nx.DiGraph, *, central_node: str | None) -> list[tuple[str, str, dict[str, Any]]]:
    if central_node is None or central_node not in graph:
        return []

    undirected = graph.to_undirected()
    parent: dict[str, str] = {}
    seen = {central_node}
    queue: deque[str] = deque([central_node])
    while queue:
        node_id = queue.popleft()
        for neighbor in sorted(undirected.neighbors(node_id), key=str):
            if neighbor in seen:
                continue
            seen.add(neighbor)
            parent[neighbor] = node_id
            queue.append(neighbor)

    tree: list[tuple[str, str, dict[str, Any]]] = []
    for node_id, parent_id in sorted(parent.items(), key=lambda item: (_sort_key(graph, item[1]), _sort_key(graph, item[0]))):
        if graph.has_edge(parent_id, node_id):
            data = dict(graph.edges[parent_id, node_id])
            tree.append((parent_id, node_id, data))
        elif graph.has_edge(node_id, parent_id):
            data = dict(graph.edges[node_id, parent_id])
            tree.append((node_id, parent_id, data))
    return tree


def _edge_path(
    src: str,
    dst: str,
    positions: dict[str, tuple[float, float]],
    boxes: dict[str, tuple[float, float, float, float]],
) -> str:
    sx, sy = positions[src]
    dx, dy = positions[dst]
    if src in boxes and dst in boxes:
        sx, sy = _box_port(boxes[src], target=positions[dst], outgoing=True)
        dx, dy = _box_port(boxes[dst], target=positions[src], outgoing=False)
        mid_y = sy + (dy - sy) * 0.5
        return f"M {sx:.1f} {sy:.1f} V {mid_y:.1f} H {dx:.1f} V {dy:.1f}"
    return f"M {sx:.1f} {sy:.1f} L {dx:.1f} {dy:.1f}"


def _box_port(
    box: tuple[float, float, float, float],
    *,
    target: tuple[float, float],
    outgoing: bool,
) -> tuple[float, float]:
    x, y, width, height = box
    cx = x + width / 2
    radius = min(16.0, max(7.0, min(width, height) * 0.32))
    cy = y + radius + 2
    target_y = target[1]
    if target_y >= cy:
        return cx, cy + radius
    return cx, cy - radius


def _legend(kind_counts: dict[str, int], *, width: int, height: int, compact: bool, edge_mode: EdgeMode) -> list[str]:
    legend_width = 360 if compact else 300
    x = width - legend_width - 48
    y = height - 74 if compact else 34
    parts = [f'<g id="legend" transform="translate({x},{y})">']
    if compact:
        parts.append('<text x="0" y="0" class="small">Kinds: ' + _compact_kind_text(kind_counts) + '</text>')
        parts.append(f'<text x="0" y="18" class="small">Edges shown: {html.escape(edge_mode)}</text>')
    else:
        parts.extend([
            f'<rect x="0" y="0" width="{legend_width}" height="210" rx="6" fill="#ffffff" stroke="#dee2e6"/>',
            '<text x="16" y="28" class="meta">Node kinds</text>',
        ])
        for i, (kind, count) in enumerate(sorted(kind_counts.items())):
            row_y = 54 + i * 22
            color = NODE_COLORS.get(kind, DEFAULT_NODE_COLOR)
            parts.append(f'<circle cx="20" cy="{row_y}" r="6" fill="{color}"/>')
            parts.append(f'<text x="34" y="{row_y + 4}" class="small">{html.escape(kind)} ({count})</text>')
        parts.append(f'<text x="16" y="190" class="small">Edges shown: {html.escape(edge_mode)}</text>')
    parts.append('</g>')
    return parts


def _compact_kind_text(kind_counts: dict[str, int]) -> str:
    chunks = [f"{kind} {count}" for kind, count in sorted(kind_counts.items())]
    return html.escape(", ".join(chunks))


def _short_label(node_id: str, *, max_len: int = 34) -> str:
    parts = node_id.split("/")
    label = "/".join(parts[-2:]) if len(parts) > 1 else node_id
    if len(label) <= max_len:
        return label
    return label[: max_len - 1] + "..."


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("knowledge", "capability"), default="knowledge")
    parser.add_argument("--graph", type=Path, default=None)
    parser.add_argument("--bm25", type=Path, default=Path("memory/.graph/graph-bm25.pkl"))
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--width", type=int, default=1800)
    parser.add_argument("--height", type=int, default=1200)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--layout", choices=("auto", "top-down", "spring"), default="auto")
    parser.add_argument("--edge-mode", choices=("tree", "curated", "all", "none"), default="tree")
    args = parser.parse_args()

    if args.mode == "capability":
        graph = args.graph or Path("memory/.graph/agent-capabilities.json")
        out = args.out or Path("memory/.graph/agent-capabilities.svg")
        render_agent_capability_graph_svg(
            graph,
            out,
            width=args.width,
            height=args.height,
            seed=args.seed,
            layout=args.layout,
            edge_mode=args.edge_mode,
        )
    else:
        graph = args.graph or Path("memory/.graph/graph.json")
        out = args.out or Path("memory/.graph/materialized-graph.svg")
        render_materialized_graph_svg(
            graph,
            args.bm25,
            out,
            width=args.width,
            height=args.height,
            seed=args.seed,
            layout=args.layout,
            edge_mode=args.edge_mode,
        )
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
