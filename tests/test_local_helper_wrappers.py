"""Smoke tests for the server-side local-helper MCP wrappers.

After the client/server split, the deterministic lint scaffold and the
pre-commit aggregator moved to ``cli/tools/`` and are invoked locally via
Bash (NOT MCP). The remaining server-side wrappers are validate (pipeline
lineage check) and data (mock generator).
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mcp.server.fastmcp import FastMCP  # noqa: E402

from server.tools.data import tools as data_tools  # noqa: E402
from server.tools.validate import tools as validate_tools  # noqa: E402


def _tools(mcp: FastMCP) -> dict[str, callable]:
    return {t.name: t.fn for t in mcp._tool_manager.list_tools()}


def _fake_subprocess_ok(stdout: str = "ok", returncode: int = 0):
    class _Result:
        def __init__(self):
            self.stdout = stdout
            self.stderr = ""
            self.returncode = returncode

    captured: dict = {}

    def _fake_run(cmd, *args, **kwargs):
        captured["cmd"] = list(cmd)
        captured["cwd"] = kwargs.get("cwd")
        return _Result()

    return patch("subprocess.run", side_effect=_fake_run), captured


# ── validate ──────────────────────────────────────────────────────────────────


def test_validate_tools_registers_pipeline_lineage_check():
    mcp = FastMCP("test")
    validate_tools.register(mcp)
    assert set(_tools(mcp)) == {"pipeline_lineage_check"}


def test_pipeline_lineage_check_stages_uploaded_files_and_passes_flags():
    mcp = FastMCP("test")
    validate_tools.register(mcp)
    ctx, captured = _fake_subprocess_ok("PASS: pipeline staging paths are consistent\n")
    notebooks = {
        "workspace/orders/bronze.py": 'OUTPUT_DIR = "abfss://lake/bronze/orders"\n',
        "workspace/orders/silver.py": 'SOURCE_DIR = "abfss://lake/bronze/orders"\n',
    }
    with ctx:
        out = _tools(mcp)["pipeline_lineage_check"](
            notebooks=notebooks, topic="orders", workspace="custom_ws"
        )
    cmd = captured["cmd"]
    assert "--workspace" in cmd and "custom_ws" in cmd
    assert "--topic" in cmd and "orders" in cmd
    # subprocess ran inside a temp dir, not against any caller-supplied path
    assert "pipeline-lineage-" in str(captured["cwd"])
    assert "PASS" in out


def test_pipeline_lineage_check_rejects_unsafe_paths():
    mcp = FastMCP("test")
    validate_tools.register(mcp)
    for bad in ("/etc/passwd", "../escape.py", "workspace/../etc/passwd"):
        with pytest.raises(RuntimeError, match="unsafe upload path|invalid upload path"):
            _tools(mcp)["pipeline_lineage_check"](notebooks={bad: "x = 1"})


def test_pipeline_lineage_check_rejects_non_py_files():
    mcp = FastMCP("test")
    validate_tools.register(mcp)
    with pytest.raises(RuntimeError, match="only .py files"):
        _tools(mcp)["pipeline_lineage_check"](
            notebooks={"workspace/orders/readme.md": "# notes"}
        )


def test_pipeline_lineage_check_rejects_empty_upload():
    mcp = FastMCP("test")
    validate_tools.register(mcp)
    with pytest.raises(RuntimeError, match="non-empty mapping"):
        _tools(mcp)["pipeline_lineage_check"](notebooks={})


def test_pipeline_lineage_check_returns_stderr_on_failure():
    """When the validator exits non-zero, stderr (which carries the Python
    traceback on crashes) must be included in the returned output."""
    mcp = FastMCP("test")
    validate_tools.register(mcp)

    class _Result:
        returncode = 1
        stdout = "FAIL: pipeline lineage check failed\n  [orders] path mismatch\n"
        stderr = ""

    def _fake_run(*args, **kwargs):
        return _Result()

    with patch("server.script_runner.subprocess.run", side_effect=_fake_run):
        out = _tools(mcp)["pipeline_lineage_check"](
            notebooks={"workspace/orders/bronze.py": 'OUTPUT_DIR = "x"\n'},
            topic="orders",
        )
    assert "FAIL" in out
    assert "exit code: 1" in out


# ── data ──────────────────────────────────────────────────────────────────────


def test_data_tools_registers_data_mock_generate():
    mcp = FastMCP("test")
    data_tools.register(mcp)
    assert set(_tools(mcp)) == {"data_mock_generate"}


def test_data_mock_generate_passes_defaults(tmp_path):
    mcp = FastMCP("test")
    data_tools.register(mcp)
    ctx, captured = _fake_subprocess_ok("wrote 1000 rows\n")
    with ctx:
        _tools(mcp)["data_mock_generate"](target_dir=str(tmp_path))
    cmd = captured["cmd"]
    assert "--topic" in cmd and "orders" in cmd
    assert "--rows" in cmd and "1000" in cmd
    assert "--seed" in cmd and "42" in cmd


def test_data_mock_generate_rejects_dual_schema(tmp_path):
    mcp = FastMCP("test")
    data_tools.register(mcp)
    with pytest.raises(RuntimeError, match="either schema or schema_file"):
        _tools(mcp)["data_mock_generate"](
            target_dir=str(tmp_path), schema="[]", schema_file="x.json"
        )
