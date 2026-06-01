"""FastMCP wrapper for server/tools/data/mock-data-generator.py.

Deterministic synthetic data generation — writes rows into a PostgreSQL
table named ``sandbox_<topic>`` (dropped and recreated on each run).
Requires DATABASE_URL to be set in the server environment.
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
        topic: str = "orders",
        rows: int = 1000,
        seed: int = 42,
        engine: str = "stdlib",
        schema: str = "",
        schema_file: str = "",
        dsn: str = "",
    ) -> str:
        """Generate deterministic synthetic data for a topic and load into PostgreSQL.

        Writes rows into sandbox_<topic> table in the PostgreSQL database.
        Uses DATABASE_URL from the server environment unless dsn is provided.
        engine: one of stdlib, faker, mimesis, sklearn.
        schema: inline JSON array of {name,type} column defs (mutually exclusive with schema_file).
        schema_file: path (project-relative) to a JSON schema file.
        """
        with CallTimer(
            "data_mock_generate",
            {"topic": topic, "rows": str(rows), "seed": str(seed),
             "engine": engine, "schema": schema, "schema_file": schema_file},
        ) as t:
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
            if dsn:
                args += ["--dsn", dsn]
            out = run_script(_SCRIPT, args, merge_stderr=True)
            t.ok()
            return out
