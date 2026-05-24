#!/usr/bin/env python3
"""Build the secondary agent-capability graph artifact."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tool"))
sys.path.insert(0, str(ROOT / "build"))

from graph_build.agent_capabilities import build_agent_capability_graph  # noqa: E402
from graph.builder import build  # noqa: E402
from graph_build.visualize import render_graph_svg  # noqa: E402


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
        help="output path (default: <target>/memory/.graph/agent-capabilities.json)",
    )
    parser.add_argument(
        "--svg",
        type=Path,
        default=None,
        help="SVG output path (default: <target>/memory/.graph/agent-capabilities.svg)",
    )
    parser.add_argument("--no-svg", action="store_true", help="skip SVG rendering")
    parser.add_argument(
        "--dry-run",
        "--validate",
        dest="validate",
        action="store_true",
        help="validate and print stats without writing (alias: --validate)",
    )
    parser.add_argument("--stats", action="store_true", help="print node-kind counts")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    root = args.target.resolve()
    knowledge_result = build(root)
    for line in knowledge_result.errors:
        print(f"ERROR: {line}", file=sys.stderr)
    if knowledge_result.errors:
        return 2

    result = build_agent_capability_graph(knowledge_result.store, root)
    for line in result.warnings:
        print(f"WARN:  {line}", file=sys.stderr)

    if args.validate:
        print(
            f"validated: {result.store.graph.number_of_nodes()} nodes, "
            f"{result.store.graph.number_of_edges()} edges"
        )
        if args.stats:
            for k, v in sorted(result.store.kinds().items()):
                print(f"  {k:14s} {v}")
        return 0

    out_path = args.out or (root / "memory" / ".graph" / "agent-capabilities.json")
    result.store.save(out_path, built_by="bin/build-agent-capability-graph.py")
    print(f"wrote: {_pretty_path(out_path, root)} ({result.store.graph.number_of_nodes()} nodes, {result.store.graph.number_of_edges()} edges)")

    if not args.no_svg:
        svg_path = args.svg or (out_path.parent / "agent-capabilities.svg")
        render_graph_svg(
            result.store,
            svg_path,
            title="Agent capability graph",
            source=out_path,
            edge_mode="all",
            central_node="capabilities/orchestrator",
        )
        print(f"wrote: {_pretty_path(svg_path, root)}")

    if args.stats:
        for k, v in sorted(result.store.kinds().items()):
            print(f"  {k:14s} {v}")
    return 0


def _pretty_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    sys.exit(main())
