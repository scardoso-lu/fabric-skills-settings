#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["networkx>=3.2", "rank_bm25>=0.2.2"]
# ///
"""Build the knowledge graph artifact for a repo (source package or installed target)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "server" / "builders"))

from graph.builder import build  # noqa: E402
from graph.search import build_bm25_index, save_index  # noqa: E402
from graph_build.visualize import render_graph_html  # noqa: E402


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        "--root",
        dest="target",
        type=Path,
        default=Path.cwd(),
        help="repo to index (default: current directory). --root is accepted as an alias.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="graph.json output path (default: <target>/dist/.graph/graph.json)",
    )
    parser.add_argument(
        "--bm25",
        type=Path,
        default=None,
        help="BM25 index output (default: <target>/dist/.graph/graph-bm25.json)",
    )
    parser.add_argument(
        "--html",
        type=Path,
        default=None,
        help="HTML output path (default: <target>/dist/.graph/materialized-graph.html)",
    )
    parser.add_argument("--no-html", action="store_true", help="skip HTML rendering")
    parser.add_argument(
        "--dry-run",
        "--validate",
        dest="validate",
        action="store_true",
        help="run validation without writing artifacts (alias: --validate)",
    )
    parser.add_argument("--strict", action="store_true", help="treat orphan warnings as errors")
    parser.add_argument("--stats", action="store_true", help="print node-kind counts and exit")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    root = args.target.resolve()
    graph_dir = root / "dist" / ".graph"
    out_path = args.out or (graph_dir / "graph.json")
    bm25_path = args.bm25 or (graph_dir / "graph-bm25.json")

    result = build(root)
    store = result.store

    for line in result.errors:
        print(f"ERROR: {line}", file=sys.stderr)
    for line in result.warnings:
        print(f"WARN:  {line}", file=sys.stderr)

    if result.errors:
        return 2
    if args.strict and result.warnings:
        return 2

    if args.validate and not (args.out or args.bm25):
        print(f"validated: {sum(store.kinds().values())} nodes, {store.graph.number_of_edges()} edges")
        if args.stats:
            for k, v in sorted(store.kinds().items()):
                print(f"  {k:14s} {v}")
        return 0

    store.save(out_path, built_by="bin/build-graph.py")
    bodies = _load_bodies(root, store)
    save_index(bm25_path, build_bm25_index(store, bodies))

    print(f"wrote: {_pretty_path(out_path, root)} ({sum(store.kinds().values())} nodes, {store.graph.number_of_edges()} edges)")
    print(f"wrote: {_pretty_path(bm25_path, root)}")

    if not args.no_html:
        html_path = args.html or (graph_dir / "materialized-graph.html")
        render_graph_html(store, html_path, title="Materialized knowledge graph", source=out_path)
        print(f"wrote: {_pretty_path(html_path, root)}")

    if args.stats:
        for k, v in sorted(store.kinds().items()):
            print(f"  {k:14s} {v}")
    return 0


def _pretty_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _load_bodies(root: Path, store) -> dict[str, str]:
    """Re-read each node's file body for BM25 indexing (bodies are not stored in graph.json)."""
    from graph.schema import parse_frontmatter

    out: dict[str, str] = {}
    for node_id in store.graph.nodes:
        rel = store.graph.nodes[node_id]["path"]
        try:
            text = (root / rel).read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        _, body = parse_frontmatter(text)
        out[node_id] = body
    return out


if __name__ == "__main__":
    sys.exit(main())
