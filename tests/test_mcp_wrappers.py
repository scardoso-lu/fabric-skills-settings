"""Smoke tests for the remaining MCP wrappers.

Most Fabric-helper tools (notebook/pipeline/lakehouse/workspace) moved to
cli/tools/ and are invoked directly by Claude via Bash — no MCP wrapping.
Only semantic_model remains server-side here because it uses the sempy.fabric
Python library, not the ms-fabric-cli binary.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mcp.server.fastmcp import FastMCP  # noqa: E402

from server.tools.semantic_model import tools as semantic_model_tools  # noqa: E402


def _fake_subprocess_ok(stdout: str = "ok"):
    class _Result:
        returncode = 0
        stderr = ""

        def __init__(self, out):
            self.stdout = out

    captured: dict = {}

    def _fake_run(cmd, *args, **kwargs):
        captured["cmd"] = list(cmd)
        captured["env"] = kwargs.get("env")
        return _Result(stdout)

    return patch("server.tools.utils.script_runner.subprocess.run", side_effect=_fake_run), captured


def _tools(mcp: FastMCP) -> dict[str, callable]:
    return {t.name: t.fn for t in mcp._tool_manager.list_tools()}


def test_semantic_model_tools_register_expected_surface():
    mcp = FastMCP("test")
    semantic_model_tools.register(mcp)
    assert set(_tools(mcp)) == {"semantic_model_list", "semantic_model_show"}


def test_semantic_model_show_defaults_hide_sensitive():
    mcp = FastMCP("test")
    semantic_model_tools.register(mcp)
    ctx, captured = _fake_subprocess_ok("{}")
    with ctx:
        _tools(mcp)["semantic_model_show"]("Sales Model")
    cmd = captured["cmd"]
    assert cmd[-3:] == ["show", "Sales Model", "--json"]
    assert "--include-hidden" not in cmd
    assert "--include-expressions" not in cmd


def test_semantic_model_show_opt_in_to_sensitive_fields():
    mcp = FastMCP("test")
    semantic_model_tools.register(mcp)
    ctx, captured = _fake_subprocess_ok("{}")
    with ctx:
        _tools(mcp)["semantic_model_show"](
            "Sales Model", include_hidden=True, include_expressions=True
        )
    cmd = captured["cmd"]
    assert "--include-hidden" in cmd
    assert "--include-expressions" in cmd
