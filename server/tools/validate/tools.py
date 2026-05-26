"""FastMCP wrapper for server/tools/validate/pipeline-lineage.py.

Verifies staging-path consistency across notebooks in the same pipeline topic.

Design: the client uploads the notebook contents (workspace/<topic>/*.py) as
{relative_path: file_content}. The server stages them in a tmpdir and runs the
validator against that — no filesystem access to the client's project is
required, which matches the Docker / remote-server deployment model. Full
stdout + stderr (including any Python traceback) is returned to the caller.
"""

from __future__ import annotations

import shutil
import tempfile
import traceback
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from ...audit import CallTimer
from ...script_runner import run_capture

_SCRIPT = Path(__file__).resolve().parent / "pipeline-lineage.py"


def _validate_upload_path(rel_path: str) -> Path:
    """Reject absolute paths and any segment containing '..' so an uploaded
    file can't escape the temp dir. Cross-platform: catches both POSIX
    `/etc/passwd` and Windows `C:\\Windows\\…` styles regardless of the
    server's OS."""
    if not rel_path or rel_path.strip() != rel_path:
        raise RuntimeError(f"invalid upload path (empty or whitespace): {rel_path!r}")
    normalized = rel_path.replace("\\", "/")
    if normalized.startswith("/") or (len(normalized) >= 2 and normalized[1] == ":"):
        raise RuntimeError(f"unsafe upload path (absolute): {rel_path!r}")
    p = Path(normalized)
    if p.is_absolute() or any(part in {"", "..", "."} for part in p.parts):
        raise RuntimeError(f"unsafe upload path: {rel_path!r}")
    return p


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def pipeline_lineage_check(
        notebooks: dict[str, str],
        topic: str = "",
        workspace: str = "workspace",
    ) -> str:
        """Validate staging-path consistency across uploaded notebooks.

        notebooks: a mapping of {relative_path: file_content}. Each path must
            be relative to the project root and resolve under ``<workspace>/``
            (e.g. ``"workspace/orders/bronze_orders.py"``). Absolute paths and
            ``..`` segments are rejected. Upload only the .py source files for
            the topic(s) you want validated.
        topic: limit the check to one topic subdir (e.g. ``"orders"``).
            Default: check every topic present in the uploaded tree.
        workspace: workspace directory name within the staged tree
            (default ``"workspace"``).

        Returns the validator's full stdout + stderr. On failure the output
        includes the FAIL lines and any Python traceback so the caller can fix
        the offending notebook(s).
        """
        with CallTimer(
            "pipeline_lineage_check",
            {"file_count": str(len(notebooks)), "topic": topic, "workspace": workspace},
        ) as t:
            if not isinstance(notebooks, dict) or not notebooks:
                raise RuntimeError(
                    "notebooks must be a non-empty mapping of {relative_path: file_content}"
                )

            tmp_root = Path(tempfile.mkdtemp(prefix="pipeline-lineage-"))
            try:
                # Stage uploaded files into the tmp dir.
                for rel_path, content in notebooks.items():
                    safe = _validate_upload_path(rel_path)
                    if safe.suffix != ".py":
                        raise RuntimeError(
                            f"only .py files are accepted; got: {str(safe)!r}"
                        )
                    if not isinstance(content, str):
                        raise RuntimeError(
                            f"file content for {rel_path!r} must be a string, got {type(content).__name__}"
                        )
                    dest = tmp_root / safe
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_text(content, encoding="utf-8")

                args = ["--workspace", workspace]
                if topic:
                    args += ["--topic", topic]

                try:
                    proc = run_capture(_SCRIPT, args, cwd=tmp_root)
                except Exception as exc:
                    # subprocess itself blew up (shouldn't normally happen) —
                    # return the traceback so the caller can see the cause.
                    t.ok()
                    return (
                        "ERROR: pipeline-lineage validator failed to start\n"
                        + "".join(traceback.format_exception(exc))
                    )

                t.ok()
                out_parts: list[str] = []
                if proc.stdout:
                    out_parts.append(proc.stdout)
                if proc.stderr:
                    # stderr carries the Python traceback when the validator
                    # crashes on bad input — never swallow it.
                    out_parts.append("--- stderr ---\n" + proc.stderr)
                if proc.returncode != 0:
                    out_parts.append(f"(pipeline-lineage exit code: {proc.returncode})")
                return "\n".join(out_parts)
            finally:
                shutil.rmtree(tmp_root, ignore_errors=True)
