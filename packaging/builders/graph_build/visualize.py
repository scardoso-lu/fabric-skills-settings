"""Render materialized knowledge graph artifacts as SVG or interactive HTML."""

from __future__ import annotations

import argparse
import html
import json as _json
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


# ---------------------------------------------------------------------------
# Interactive HTML renderer
# ---------------------------------------------------------------------------

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>__TITLE__</title>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#0d1117;--surface:#161b22;--border:#30363d;
  --text:#e6edf3;--muted:#8b949e;--accent:#58a6ff;
  --sidebar:260px;--detail:300px;
}
html,body{height:100%;overflow:hidden}
body{display:flex;background:var(--bg);color:var(--text);
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-size:13px}
#sidebar{
  width:var(--sidebar);min-width:var(--sidebar);
  background:var(--surface);border-right:1px solid var(--border);
  display:flex;flex-direction:column;overflow-y:auto;
  padding:14px 12px;gap:14px;
}
#canvas-wrap{flex:1;position:relative;overflow:hidden;cursor:grab}
#canvas-wrap.grabbing{cursor:grabbing}
svg#graph{width:100%;height:100%;display:block}
#detail{
  width:var(--detail);min-width:var(--detail);
  background:var(--surface);border-left:1px solid var(--border);
  display:none;flex-direction:column;overflow-y:auto;
  padding:14px 12px;
}
#detail.open{display:flex}
h1{font-size:15px;font-weight:700;line-height:1.35;word-break:break-word}
.meta{color:var(--muted);font-size:11px;margin-top:3px}
.sec{font-size:11px;font-weight:600;color:var(--muted);text-transform:uppercase;
  letter-spacing:.5px;margin-bottom:6px}
input[type=search]{
  width:100%;padding:6px 8px;background:var(--bg);
  border:1px solid var(--border);border-radius:6px;
  color:var(--text);font-size:12px;outline:none;
}
input[type=search]:focus{border-color:var(--accent)}
.kind-filter{display:flex;flex-direction:column;gap:4px}
.kind-row{display:flex;align-items:center;gap:6px;cursor:pointer;
  user-select:none;padding:2px 0}
.kind-dot{width:10px;height:10px;border-radius:50%;flex-shrink:0}
.kind-lbl{flex:1;font-size:12px}
.kind-cnt{font-size:11px;color:var(--muted)}
.edge-mode{display:flex;flex-direction:column;gap:4px}
.edge-row{display:flex;align-items:center;gap:6px;user-select:none}
.btn-row{display:flex;gap:6px;flex-wrap:wrap}
.btn{padding:5px 10px;background:var(--border);
  border:1px solid var(--border);border-radius:6px;
  color:var(--text);font-size:12px;cursor:pointer}
.btn:hover{background:#3a3f47}
/* detail panel */
.d-title{font-size:14px;font-weight:700;word-break:break-word}
.d-id{font-family:monospace;font-size:11px;color:var(--muted);
  word-break:break-all;margin-top:3px}
.d-kind{display:inline-block;padding:2px 8px;border-radius:10px;
  font-size:11px;font-weight:600;color:#fff;margin:6px 0}
.d-desc{color:var(--muted);font-size:12px;line-height:1.5;margin:6px 0}
.d-path{font-family:monospace;font-size:11px;color:var(--accent);
  word-break:break-all;margin-bottom:10px}
.lnk-sec{margin-top:10px}
.lnk-sec ul{list-style:none;padding:0;display:flex;flex-direction:column;gap:3px}
.lnk{padding:4px 6px;border-radius:4px;cursor:pointer;
  font-family:monospace;font-size:11px;color:var(--accent)}
.lnk:hover{background:var(--border)}
.arr{color:var(--muted);margin-right:3px}
.close-btn{margin-left:auto;cursor:pointer;color:var(--muted);
  font-size:20px;line-height:1;padding:0 4px;flex-shrink:0}
.close-btn:hover{color:var(--text)}
.sim-status{font-size:11px;color:var(--muted);text-align:center}
#tooltip{
  position:fixed;background:rgba(22,27,34,.96);
  border:1px solid var(--border);border-radius:6px;
  padding:6px 10px;font-size:12px;pointer-events:none;
  display:none;z-index:100;max-width:260px;word-break:break-word;
}
</style>
</head>
<body>
<div id="sidebar">
  <div>
    <h1>__TITLE__</h1>
    <p class="meta" id="stats">__STATS__</p>
    <p class="meta">__BUILT_BY__</p>
  </div>
  <div>
    <div class="sec">Search</div>
    <input type="search" id="search-box" placeholder="Filter nodes by id or title…" autocomplete="off">
  </div>
  <div>
    <div class="sec">Node kinds</div>
    <div class="kind-filter" id="kind-filter"></div>
  </div>
  <div>
    <div class="sec">Edges</div>
    <div class="edge-mode" id="edge-mode"></div>
  </div>
  <div>
    <div class="sec">Controls</div>
    <div class="btn-row">
      <button class="btn" id="btn-fit">Fit view</button>
      <button class="btn" id="btn-reheat">Reheat</button>
      <button class="btn" id="btn-freeze">Freeze</button>
    </div>
  </div>
  <div class="sim-status" id="sim-status">Simulating…</div>
</div>
<div id="canvas-wrap">
  <svg id="graph" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <marker id="arr" viewBox="0 0 10 10" refX="9" refY="5"
              markerWidth="5" markerHeight="5" orient="auto-start-reverse">
        <path d="M0 0 L10 5 L0 10 z" fill="#6e7681"/>
      </marker>
      <marker id="arr-hl" viewBox="0 0 10 10" refX="9" refY="5"
              markerWidth="5" markerHeight="5" orient="auto-start-reverse">
        <path d="M0 0 L10 5 L0 10 z" fill="#58a6ff"/>
      </marker>
    </defs>
    <g id="tg">
      <g id="el"></g>
      <g id="nl"></g>
      <g id="ll"></g>
    </g>
  </svg>
</div>
<div id="detail">
  <div style="display:flex;align-items:flex-start;margin-bottom:12px">
    <div class="sec" style="margin:0;flex:1">Node details</div>
    <span class="close-btn" id="d-close">&times;</span>
  </div>
  <div class="d-title" id="d-title"></div>
  <div class="d-id" id="d-id"></div>
  <div class="d-kind" id="d-kind"></div>
  <div class="d-desc" id="d-desc"></div>
  <div class="d-path" id="d-path"></div>
  <div class="lnk-sec" id="d-out">
    <div class="sec">Links to</div>
    <ul id="d-out-list"></ul>
  </div>
  <div class="lnk-sec" id="d-in" style="margin-top:10px">
    <div class="sec">Links from</div>
    <ul id="d-in-list"></ul>
  </div>
</div>
<div id="tooltip"></div>
<script>
const GRAPH = __GRAPH_JSON__;
const NODE_COLORS = __NODE_COLORS_JSON__;
const DEFAULT_NODE_COLOR = '#adb5bd';
const EDGE_COLORS = __EDGE_COLORS_JSON__;
const EDGE_DASH = {'auto-path': '4 4'};

// --- Adjacency ---
const nodeMap = {};
const outLinks = {};
const inLinks = {};
GRAPH.nodes.forEach(n => {
  nodeMap[n.id] = n;
  outLinks[n.id] = [];
  inLinks[n.id] = [];
});
GRAPH.edges.forEach(e => {
  if (outLinks[e.src]) outLinks[e.src].push({id: e.dst, kind: e.kind});
  if (inLinks[e.dst])  inLinks[e.dst].push({id: e.src, kind: e.kind});
});

// --- Edge index for tree BFS ---
const edgeOutIdx = {}; // src -> [{i, dst}]
const edgeInIdx  = {}; // dst -> [{i, src}]
GRAPH.edges.forEach((e, i) => {
  if (!edgeOutIdx[e.src]) edgeOutIdx[e.src] = [];
  edgeOutIdx[e.src].push({i, other: e.dst});
  if (!edgeInIdx[e.dst]) edgeInIdx[e.dst] = [];
  edgeInIdx[e.dst].push({i, other: e.src});
});

// --- Simulation nodes ---
const simNodes = GRAPH.nodes.map(n => ({
  id: n.id, x: 400, y: 300, vx: 0, vy: 0, pinned: false
}));
const simMap = {};
simNodes.forEach(n => { simMap[n.id] = n; });

// BFS initial layout
function initLayout() {
  const entry = GRAPH.nodes.find(n => n.kind === 'entry') || GRAPH.nodes[0];
  if (!entry) return;
  const levels = {[entry.id]: 0};
  const q = [entry.id];
  while (q.length) {
    const id = q.shift();
    const nb = [...(outLinks[id] || []).map(x => x.id),
                ...(inLinks[id]  || []).map(x => x.id)];
    for (const nid of nb) {
      if (!(nid in levels)) { levels[nid] = levels[id] + 1; q.push(nid); }
    }
  }
  let maxLv = 0;
  GRAPH.nodes.forEach(n => {
    if (!(n.id in levels)) levels[n.id] = 0;
    if (levels[n.id] > maxLv) maxLv = levels[n.id];
  });
  const byLevel = {};
  GRAPH.nodes.forEach(n => {
    const lv = levels[n.id];
    if (!byLevel[lv]) byLevel[lv] = [];
    byLevel[lv].push(n.id);
  });
  simNodes.forEach(sn => {
    const lv = levels[sn.id] || 0;
    const sibs = byLevel[lv] || [sn.id];
    const idx  = sibs.indexOf(sn.id);
    const frac = sibs.length > 1 ? idx / (sibs.length - 1) : 0.5;
    sn.x = 80 + frac * 340 + (Math.random() - 0.5) * 15;
    sn.y = 80 + (lv / Math.max(maxLv, 1)) * 300 + (Math.random() - 0.5) * 12;
  });
}
initLayout();

// --- Force simulation ---
const REPULSION = 1800, SPRING_K = 0.03, REST_LEN = 70;
const GRAVITY = 0.002, DAMPING = 0.80;
const ALPHA_DECAY = 0.0018, MIN_ALPHA = 0.001;
let alpha = 1.0, frozen = false;

function tick() {
  if (frozen || alpha <= MIN_ALPHA) return;
  alpha = Math.max(MIN_ALPHA, alpha - ALPHA_DECAY);
  const N = simNodes.length;
  for (let i = 0; i < N; i++) {
    const a = simNodes[i];
    for (let j = i + 1; j < N; j++) {
      const b = simNodes[j];
      const dx = b.x - a.x, dy = b.y - a.y;
      const d2 = Math.max(dx*dx + dy*dy, 25);
      const f = REPULSION * alpha / d2;
      a.vx -= f*dx; a.vy -= f*dy;
      b.vx += f*dx; b.vy += f*dy;
    }
  }
  GRAPH.edges.forEach(e => {
    const a = simMap[e.src], b = simMap[e.dst];
    if (!a || !b) return;
    const dx = b.x - a.x, dy = b.y - a.y;
    const d  = Math.sqrt(dx*dx + dy*dy) || 1;
    const f  = SPRING_K * (d - REST_LEN) * alpha;
    const fx = f*dx/d, fy = f*dy/d;
    if (!a.pinned) { a.vx += fx; a.vy += fy; }
    if (!b.pinned) { b.vx -= fx; b.vy -= fy; }
  });
  const cw = canvasWrap.clientWidth  || 800;
  const ch = canvasWrap.clientHeight || 600;
  simNodes.forEach(sn => {
    if (sn.pinned) return;
    sn.vx += GRAVITY * (cw/2 - sn.x) * alpha;
    sn.vy += GRAVITY * (ch/2 - sn.y) * alpha;
    sn.vx *= DAMPING; sn.vy *= DAMPING;
    sn.x += sn.vx;   sn.y += sn.vy;
  });
}

// --- UI state ---
let activeKinds = new Set(GRAPH.nodes.map(n => n.kind));
let edgeMode    = 'tree';
let searchQuery = '';
let selectedId  = null;
let highlightSet = null; // null = all visible; Set = subset to highlight

// --- Pan/zoom ---
const canvasWrap = document.getElementById('canvas-wrap');
let panX = 0, panY = 0, zoomScale = 1;
let panning = false, panSX = 0, panSY = 0;
let dragNode = null;

canvasWrap.addEventListener('mousedown', ev => {
  if (ev.target.tagName === 'circle') return;
  panning = true; panSX = ev.clientX; panSY = ev.clientY;
  canvasWrap.classList.add('grabbing');
});
window.addEventListener('mousemove', ev => {
  if (panning) {
    panX += ev.clientX - panSX; panY += ev.clientY - panSY;
    panSX = ev.clientX; panSY = ev.clientY;
  }
  if (dragNode) {
    const r = canvasWrap.getBoundingClientRect();
    dragNode.x = (ev.clientX - r.left - panX) / zoomScale;
    dragNode.y = (ev.clientY - r.top  - panY) / zoomScale;
    dragNode.vx = 0; dragNode.vy = 0;
  }
});
window.addEventListener('mouseup', () => {
  panning = false;
  canvasWrap.classList.remove('grabbing');
  if (dragNode) { dragNode.pinned = false; dragNode = null; }
});
canvasWrap.addEventListener('wheel', ev => {
  ev.preventDefault();
  const r    = canvasWrap.getBoundingClientRect();
  const mx   = ev.clientX - r.left;
  const my   = ev.clientY - r.top;
  const d    = ev.deltaY < 0 ? 1.13 : 0.885;
  const ns   = Math.min(Math.max(zoomScale * d, 0.08), 10);
  panX = mx - (mx - panX) * (ns / zoomScale);
  panY = my - (my - panY) * (ns / zoomScale);
  zoomScale = ns;
}, {passive: false});

// --- SVG elements ---
const svgEl = document.getElementById('graph');
const tg    = document.getElementById('tg');
const el    = document.getElementById('el');   // edges
const nl    = document.getElementById('nl');   // nodes
const ll    = document.getElementById('ll');   // labels
const NS    = 'http://www.w3.org/2000/svg';

const edgeEls = {};
const nodeEls = {};
const lblEls  = {};

function initElements() {
  GRAPH.edges.forEach((e, i) => {
    const line = document.createElementNS(NS, 'line');
    line.setAttribute('stroke-width', '1.2');
    line.setAttribute('marker-end', 'url(#arr)');
    el.appendChild(line);
    edgeEls[i] = line;
  });
  simNodes.forEach(sn => {
    const c = document.createElementNS(NS, 'circle');
    c.setAttribute('r', '10');
    c.setAttribute('stroke', '#30363d');
    c.setAttribute('stroke-width', '1.5');
    c.style.cursor = 'pointer';
    nl.appendChild(c);
    nodeEls[sn.id] = c;

    const t = document.createElementNS(NS, 'text');
    t.setAttribute('font-size', '11');
    t.setAttribute('fill', '#8b949e');
    t.setAttribute('pointer-events', 'none');
    t.setAttribute('dominant-baseline', 'middle');
    ll.appendChild(t);
    lblEls[sn.id] = t;

    c.addEventListener('mouseenter', ev => showTip(sn.id, ev));
    c.addEventListener('mouseleave', () => hideTip());
    c.addEventListener('click', ev => { ev.stopPropagation(); selectNode(sn.id); });
    c.addEventListener('mousedown', ev => {
      ev.stopPropagation();
      dragNode = sn; sn.pinned = true;
      alpha = Math.max(alpha, 0.3);
    });
  });
}

// --- Visible edges ---
function visibleEdgeSet() {
  if (edgeMode === 'none')    return new Set();
  if (edgeMode === 'all')     return new Set(GRAPH.edges.map((_, i) => i));
  if (edgeMode === 'curated') {
    const s = new Set();
    GRAPH.edges.forEach((e, i) => { if (e.kind === 'curated') s.add(i); });
    return s;
  }
  // tree: BFS spanning tree from entry node
  const entry = simNodes.find(sn => nodeMap[sn.id] && nodeMap[sn.id].kind === 'entry') || simNodes[0];
  if (!entry) return new Set();
  const seen = new Set([entry.id]);
  const q = [entry.id];
  const tree = new Set();
  while (q.length) {
    const id = q.shift();
    const nbOut = edgeOutIdx[id] || [];
    const nbIn  = edgeInIdx[id]  || [];
    for (const {i, other} of [...nbOut, ...nbIn]) {
      if (!seen.has(other)) { seen.add(other); tree.add(i); q.push(other); }
    }
  }
  return tree;
}

// --- Search matches ---
function searchMatches() {
  if (!searchQuery) return null;
  const q = searchQuery.toLowerCase();
  const s = new Set();
  GRAPH.nodes.forEach(n => {
    if (n.id.toLowerCase().includes(q) ||
        (n.title || '').toLowerCase().includes(q) ||
        (n.description || '').toLowerCase().includes(q)) {
      s.add(n.id);
    }
  });
  return s;
}

// --- Render ---
const NODE_RADIUS = 10;

function render() {
  tg.setAttribute('transform',
    'translate(' + panX + ',' + panY + ') scale(' + zoomScale + ')');

  const vis  = visibleEdgeSet();
  const srch = searchMatches();
  const hl   = highlightSet;

  GRAPH.edges.forEach((e, i) => {
    const line = edgeEls[i];
    if (!line) return;
    const a = simMap[e.src], b = simMap[e.dst];
    if (!a || !b) { line.style.display = 'none'; return; }

    const na = nodeMap[e.src], nb = nodeMap[e.dst];
    const edgeShown = vis.has(i)
      && activeKinds.has(na ? na.kind : '')
      && activeKinds.has(nb ? nb.kind : '')
      && (!srch || srch.has(e.src) || srch.has(e.dst));

    if (!edgeShown) { line.style.display = 'none'; return; }
    line.style.display = '';

    const dx = b.x - a.x, dy = b.y - a.y;
    const d  = Math.sqrt(dx*dx + dy*dy) || 1;
    const r  = NODE_RADIUS + 3;
    line.setAttribute('x1', a.x + dx/d * NODE_RADIUS);
    line.setAttribute('y1', a.y + dy/d * NODE_RADIUS);
    line.setAttribute('x2', b.x - dx/d * r);
    line.setAttribute('y2', b.y - dy/d * r);

    const highlighted = !hl || hl.has(e.src) || hl.has(e.dst);
    const color   = highlighted ? (EDGE_COLORS[e.kind] || '#495057') : '#2d333b';
    const opacity = highlighted ? (hl ? '0.85' : '0.50') : '0.2';
    line.setAttribute('stroke', color);
    line.setAttribute('stroke-opacity', opacity);
    const dash = EDGE_DASH[e.kind];
    if (dash) line.setAttribute('stroke-dasharray', dash);
    else line.removeAttribute('stroke-dasharray');
    line.setAttribute('marker-end', highlighted && hl ? 'url(#arr-hl)' : 'url(#arr)');
  });

  simNodes.forEach(sn => {
    const c = nodeEls[sn.id], t = lblEls[sn.id];
    if (!c || !t) return;
    const nd = nodeMap[sn.id];
    const kindOk  = activeKinds.has(nd ? nd.kind : '');
    const srchOk  = !srch || srch.has(sn.id);
    const visible = kindOk && srchOk;
    if (!visible) { c.style.display = 'none'; t.style.display = 'none'; return; }
    c.style.display = ''; t.style.display = '';

    c.setAttribute('cx', sn.x);
    c.setAttribute('cy', sn.y);

    const selected     = selectedId === sn.id;
    const highlighted  = !hl || hl.has(sn.id);
    const color = NODE_COLORS[nd ? nd.kind : ''] || DEFAULT_NODE_COLOR;
    c.setAttribute('fill', color);
    c.setAttribute('r', selected ? '13' : '10');
    c.setAttribute('opacity',      highlighted ? '1' : '0.18');
    c.setAttribute('stroke',       selected ? '#ffffff' : '#30363d');
    c.setAttribute('stroke-width', selected ? '2.5' : '1.5');

    t.textContent = shortLabel(sn.id);
    t.setAttribute('x', sn.x + 15);
    t.setAttribute('y', sn.y);
    t.setAttribute('opacity', highlighted ? '1' : '0.18');
  });
}

function shortLabel(id) {
  const p = id.split('/');
  const s = p.length > 1 ? p.slice(-2).join('/') : id;
  return s.length > 28 ? s.slice(0, 27) + '\\u2026' : s;
}

// --- Tooltip ---
const tip = document.getElementById('tooltip');
function showTip(id, ev) {
  const n = nodeMap[id];
  if (!n) return;
  tip.innerHTML =
    '<strong>' + esc(n.title || id) + '</strong><br>' +
    '<span style="color:#8b949e;font-size:11px">' + esc(id) + '</span>' +
    (n.description ? '<br><span style="color:#8b949e;font-size:11px">' +
      esc(n.description.slice(0, 120)) + '</span>' : '');
  tip.style.display = 'block';
  moveTip(ev);
}
function hideTip() { tip.style.display = 'none'; }
function moveTip(ev) {
  let x = ev.clientX + 14, y = ev.clientY - 10;
  if (x + 270 > window.innerWidth) x = ev.clientX - 280;
  tip.style.left = x + 'px'; tip.style.top = y + 'px';
}
svgEl.addEventListener('mousemove', ev => { if (tip.style.display === 'block') moveTip(ev); });

// --- Selection ---
function selectNode(id) {
  selectedId   = id;
  const out    = (outLinks[id] || []).map(x => x.id);
  const inn    = (inLinks[id]  || []).map(x => x.id);
  highlightSet = new Set([id, ...out, ...inn]);
  showDetail(id);
}
function clearSelection() {
  selectedId = null; highlightSet = null;
  document.getElementById('detail').classList.remove('open');
}
svgEl.addEventListener('click', clearSelection);
document.getElementById('d-close').addEventListener('click', clearSelection);

function showDetail(id) {
  const n = nodeMap[id];
  if (!n) return;
  document.getElementById('d-title').textContent = n.title || id;
  document.getElementById('d-id').textContent    = id;
  const badge = document.getElementById('d-kind');
  badge.textContent  = n.kind;
  badge.style.background = NODE_COLORS[n.kind] || DEFAULT_NODE_COLOR;
  document.getElementById('d-desc').textContent = n.description || '';
  document.getElementById('d-path').textContent = n.path || '';

  function linkItem(linkId, arrow) {
    const ln = nodeMap[linkId];
    const li = document.createElement('li');
    li.className  = 'lnk';
    li.dataset.id = linkId;
    li.innerHTML  =
      '<span class="arr">' + arrow + '</span>' +
      esc(ln ? (ln.title || linkId) : linkId) +
      '<br><span style="color:#8b949e;font-size:10px">' + esc(linkId) + '</span>';
    li.addEventListener('click', () => { selectNode(linkId); focusNode(linkId); });
    return li;
  }

  const outList = document.getElementById('d-out-list');
  outList.innerHTML = '';
  const outIds = (outLinks[id] || []).map(x => x.id);
  if (outIds.length) outIds.forEach(nid => outList.appendChild(linkItem(nid, '→')));
  else outList.innerHTML = '<li style="color:#8b949e;font-size:11px;padding:4px">none</li>';

  const inList = document.getElementById('d-in-list');
  inList.innerHTML = '';
  const inIds  = (inLinks[id] || []).map(x => x.id);
  if (inIds.length) inIds.forEach(nid => inList.appendChild(linkItem(nid, '←')));
  else inList.innerHTML = '<li style="color:#8b949e;font-size:11px;padding:4px">none</li>';

  document.getElementById('detail').classList.add('open');
}

function focusNode(id) {
  const sn = simMap[id];
  if (!sn) return;
  const cw = canvasWrap.clientWidth, ch = canvasWrap.clientHeight;
  panX = cw/2 - sn.x * zoomScale;
  panY = ch/2 - sn.y * zoomScale;
}

// --- Kind filter UI ---
function buildKindFilter() {
  const counts = {};
  GRAPH.nodes.forEach(n => { counts[n.kind] = (counts[n.kind] || 0) + 1; });
  const container = document.getElementById('kind-filter');
  container.innerHTML = '';
  Object.keys(counts).sort().forEach(kind => {
    const label = document.createElement('label');
    label.className = 'kind-row';
    label.innerHTML =
      '<input type="checkbox" checked data-kind="' + esc(kind) + '">' +
      '<span class="kind-dot" style="background:' + (NODE_COLORS[kind] || DEFAULT_NODE_COLOR) + '"></span>' +
      '<span class="kind-lbl">' + esc(kind) + '</span>' +
      '<span class="kind-cnt">' + counts[kind] + '</span>';
    label.querySelector('input').addEventListener('change', ev => {
      if (ev.target.checked) activeKinds.add(kind); else activeKinds.delete(kind);
    });
    container.appendChild(label);
  });
}

// --- Edge mode UI ---
function buildEdgeModeUI() {
  const modes = [
    {id:'tree',    label:'Tree (BFS)'},
    {id:'curated', label:'Curated only'},
    {id:'all',     label:'All edges'},
    {id:'none',    label:'Hide edges'},
  ];
  const container = document.getElementById('edge-mode');
  container.innerHTML = '';
  modes.forEach(m => {
    const label = document.createElement('label');
    label.className = 'edge-row';
    label.innerHTML =
      '<input type="radio" name="em" value="' + m.id + '"' +
      (m.id === edgeMode ? ' checked' : '') + '>' +
      '<span style="font-size:12px">' + m.label + '</span>';
    label.querySelector('input').addEventListener('change', () => { edgeMode = m.id; });
    container.appendChild(label);
  });
}

// --- Search ---
document.getElementById('search-box').addEventListener('input', ev => {
  searchQuery = ev.target.value.trim();
  if (!searchQuery && selectedId) {
    const out = (outLinks[selectedId] || []).map(x => x.id);
    const inn = (inLinks[selectedId]  || []).map(x => x.id);
    highlightSet = new Set([selectedId, ...out, ...inn]);
  } else if (!searchQuery) {
    highlightSet = null;
  }
});

// --- Control buttons ---
document.getElementById('btn-fit').addEventListener('click', fitView);
document.getElementById('btn-reheat').addEventListener('click', () => {
  alpha = 1.0; if (frozen) { frozen = false; document.getElementById('btn-freeze').textContent = 'Freeze'; }
});
document.getElementById('btn-freeze').addEventListener('click', ev => {
  frozen = !frozen;
  ev.target.textContent = frozen ? 'Unfreeze' : 'Freeze';
});

function fitView() {
  if (!simNodes.length) return;
  const rect = canvasWrap.getBoundingClientRect();
  const xs = simNodes.map(n => n.x), ys = simNodes.map(n => n.y);
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  const pad  = 80;
  const s = Math.min(
    (rect.width  - pad*2) / Math.max(maxX - minX, 1),
    (rect.height - pad*2) / Math.max(maxY - minY, 1),
    2.5
  );
  zoomScale = s;
  panX = rect.width/2  - (minX + maxX)/2 * s;
  panY = rect.height/2 - (minY + maxY)/2 * s;
}

// --- HTML escape helper ---
function esc(s) {
  return String(s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// --- Animation loop ---
const simStatusEl = document.getElementById('sim-status');
function loop() {
  tick();
  render();
  if (frozen) simStatusEl.textContent = 'Frozen';
  else if (alpha <= MIN_ALPHA) simStatusEl.textContent = 'Settled';
  else simStatusEl.textContent = 'Simulating (\\u03b1=' + alpha.toFixed(3) + ')';
  requestAnimationFrame(loop);
}

// --- Boot ---
buildKindFilter();
buildEdgeModeUI();
initElements();
fitView();
loop();
</script>
</body>
</html>
"""


def render_graph_html(
    store: GraphStore,
    output: Path,
    *,
    title: str = "Knowledge Graph",
    source: Path | None = None,
) -> Path:
    """Render any GraphStore as a self-contained interactive HTML file.

    No external dependencies — the output is a single file with embedded JS.
    Features: force-directed layout, zoom/pan, node click-to-inspect, search,
    kind filter, edge-mode toggle (tree / curated / all / none).
    """
    output.parent.mkdir(parents=True, exist_ok=True)

    slim_nodes = []
    for nid in sorted(store.graph.nodes):
        data = store.graph.nodes[nid]
        slim_nodes.append({
            "id": nid,
            "title": data.get("title") or nid,
            "description": data.get("description") or "",
            "kind": data.get("kind") or "unknown",
            "path": data.get("path") or "",
        })
    slim_edges = [
        {"src": s, "dst": d, "kind": data.get("kind", "curated")}
        for s, d, data in sorted(
            store.graph.edges(data=True), key=lambda e: (e[0], e[1])
        )
    ]
    graph_json = _json.dumps(
        {"nodes": slim_nodes, "edges": slim_edges}, ensure_ascii=False
    ).replace("</", "<\\/")

    node_count = store.graph.number_of_nodes()
    edge_count = store.graph.number_of_edges()
    stats = f"{node_count} nodes, {edge_count} edges"
    built_by = f"built_by={html.escape(store.built_by or 'unknown')}"

    content = _HTML_TEMPLATE
    content = content.replace("__TITLE__", html.escape(title))
    content = content.replace("__STATS__", html.escape(stats))
    content = content.replace("__BUILT_BY__", built_by)
    content = content.replace("__GRAPH_JSON__", graph_json)
    content = content.replace("__NODE_COLORS_JSON__", _json.dumps(NODE_COLORS))
    content = content.replace("__EDGE_COLORS_JSON__", _json.dumps(EDGE_COLORS))

    output.write_text(content, encoding="utf-8")
    return output


def render_materialized_graph_html(
    graph_json: Path,
    bm25_path: Path,
    output: Path,
) -> Path:
    """Render graph.json as interactive HTML after validating the BM25 index."""
    store = GraphStore.load(graph_json)
    validate_materialized_index(store, bm25_path)
    return render_graph_html(store, output, title="Materialized knowledge graph", source=graph_json)


def render_agent_capability_graph_html(
    graph_json: Path,
    output: Path,
) -> Path:
    """Render an agent-capabilities graph as interactive HTML."""
    store = GraphStore.load(graph_json)
    return render_graph_html(store, output, title="Agent capability graph", source=graph_json)


# ---------------------------------------------------------------------------
# SVG helpers (kept for backward-compat and tests)
# ---------------------------------------------------------------------------

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
    parser.add_argument("--bm25", type=Path, default=Path("dist/.graph/graph-bm25.pkl"))
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--width", type=int, default=1800)
    parser.add_argument("--height", type=int, default=1200)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--layout", choices=("auto", "top-down", "spring"), default="auto")
    parser.add_argument("--edge-mode", choices=("tree", "curated", "all", "none"), default="tree")
    args = parser.parse_args()

    if args.mode == "capability":
        graph = args.graph or Path("dist/.graph/agent-capabilities.json")
        out = args.out or Path("dist/.graph/agent-capabilities.svg")
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
        graph = args.graph or Path("dist/.graph/graph.json")
        out = args.out or Path("dist/.graph/materialized-graph.svg")
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
