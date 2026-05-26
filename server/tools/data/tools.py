"""FastMCP wrapper for server/tools/data/mock-data-generator.py.

Deterministic synthetic CSV generation for sandbox/dev workloads.
"""

from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from ...audit import CallTimer
from ..utils.script_runner import run_script

_SCRIPT = Path(__file__).resolve().parent / "mock-data-generator.py"


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def data_mock_generate(
        target_dir: str,
        topic: str = "orders",
        rows: int = 1000,
        seed: int = 42,
        engine: str = "stdlib",
        schema: str = "",
        schema_file: str = "",
        output: str = "",
    ) -> str:
        """Generate a deterministic synthetic CSV for a topic.

        target_dir: project root (output defaults to data/sandbox/<topic>.csv under it).
        engine: one of stdlib, faker, mimesis, sklearn.
        schema: inline JSON array of {name,type} column defs (mutually exclusive with schema_file).
        schema_file: path (project-relative) to a JSON schema file.
        output: explicit CSV output path (project-relative).
        """
        with CallTimer(
            "data_mock_generate",
            {"target_dir": target_dir, "topic": topic, "rows": str(rows),
             "seed": str(seed), "engine": engine, "schema": schema,
             "schema_file": schema_file, "output": output},
        ) as t:
            root = Path(target_dir).resolve()
            if not root.is_dir():
                raise RuntimeError(f"target_dir does not exist: {root}")
            if schema and schema_file:
                raise RuntimeError("pass either schema or schema_file, not both")
            args = [
                "--topic", topic,
                "--rows", str(rows),
                "--seed", str(seed),
                "--engine", engine,
            ]
            if schema:
                args += ["--schema", schema]
            if schema_file:
                args += ["--schema-file", schema_file]
            if output:
                args += ["--output", output]
            out = run_script(_SCRIPT, args, cwd=root, merge_stderr=True)
            t.ok()
            return out
