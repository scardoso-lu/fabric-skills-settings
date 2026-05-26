"""Subprocess helper for MCP tool wrappers that shell out to a standalone
CLI script.

Currently used by server/tools/semantic_model/tools.py to run
semantic_model/inspect.py. (The data and validate tools build their own
subprocess invocations because they need bespoke argument/env handling.)

The fabric-server MCP speaks to clients over HTTP, not stdio — so the child
script's stdout must never leak to the server process's own streams. We run
the script with capture_output=True: its stdout is captured into a string and
returned as the MCP tool result (FastMCP serializes that back over HTTP); its
stderr is captured for error reporting. Nothing is written to the server's
stdout/stderr.

Conventions:
- Honors whatever FABRIC_PROJECT_ROOT the server process has set (Docker
  mounts the target repo there); we pass the environment through unchanged.
- The helper script writes its result to its own stdout and diagnostics to
  its own stderr; both are captured here, never inherited by the server.
- Non-zero exit codes raise RuntimeError with the captured stderr included.
- Raw stdout/stderr are never added to audit logs (handled by CallTimer).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def run_capture(
    script: Path,
    args: list[str],
    *,
    cwd: Path | None = None,
    timeout: int = 3600,
) -> subprocess.CompletedProcess[str]:
    """The single subprocess site for every MCP helper script.

    Runs ``python <script> <args>`` with both streams captured (never inherited
    by the server) and the server environment passed through. Returns the raw
    CompletedProcess; the caller decides how to treat the exit code:
    - run_script() raises on non-zero (semantic_model, data);
    - pipeline_lineage_check formats stdout/stderr/exit-code into a report
      regardless of exit code.

    Raises RuntimeError only if the script file is missing.
    """
    if not script.is_file():
        raise RuntimeError(f"helper script not found: {script}")
    # FABRIC_PROJECT_ROOT may be set by the server's deployment context
    # (Docker mounts the target repo there). Pass the environment through.
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=str(cwd) if cwd is not None else None,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=os.environ.copy(),
        check=False,
    )


def run_script(
    script: Path,
    args: list[str],
    *,
    cwd: Path | None = None,
    timeout: int = 3600,
    merge_stderr: bool = False,
) -> str:
    """Run a Fabric helper script and return its captured output.

    Returns stdout (plus stderr when ``merge_stderr`` is set). Raises
    RuntimeError if the script exits non-zero.
    """
    proc = run_capture(script, args, cwd=cwd, timeout=timeout)
    if proc.returncode != 0:
        detail = (proc.stdout + proc.stderr).strip() if merge_stderr else proc.stderr.strip()
        raise RuntimeError(f"{script.name} exited with code {proc.returncode}: {detail}")
    return proc.stdout + proc.stderr if merge_stderr else proc.stdout
