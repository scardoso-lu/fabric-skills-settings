"""FastMCP wrappers for server/tools/semantic_model/inspect.py."""

from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from ...audit import CallTimer
from ..utils.script_runner import run_script

_INSPECT = Path(__file__).resolve().parent / "inspect.py"


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def semantic_model_list() -> str:
        """List all semantic models in the configured Fabric workspace."""
        with CallTimer("semantic_model_list", {}) as t:
            out = run_script(_INSPECT, ["list"])
            t.ok()
            return out

    @mcp.tool()
    def semantic_model_show(
        model: str,
        include_hidden: bool = False,
        include_expressions: bool = False,
    ) -> str:
        """Show tables, columns, measures, and relationships for a semantic model.

        model: display name or ID.
        include_hidden: include hidden tables/columns/measures (default off).
        include_expressions: include DAX expressions (default off; they may
            carry sensitive business logic).
        Returns JSON.
        """
        args = ["show", model, "--json"]
        if include_hidden:
            args.append("--include-hidden")
        if include_expressions:
            args.append("--include-expressions")
        with CallTimer(
            "semantic_model_show",
            {
                "model": model,
                "include_hidden": str(include_hidden),
                "include_expressions": str(include_expressions),
            },
        ) as t:
            out = run_script(_INSPECT, args)
            t.ok()
            return out
