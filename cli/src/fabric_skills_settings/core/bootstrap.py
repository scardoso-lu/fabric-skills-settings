"""Invoke the package-owned target bootstrap through `fabric-vibe setup`."""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

log = logging.getLogger(__name__)


def bootstrap_target(target: Path) -> int:
    """Run the package bootstrap from the target repo root."""
    log.info("Bootstrapping target (%s)", target)
    log.info("running fabric-vibe setup - will prompt for Fabric credentials if missing")
    cmd = [
        sys.executable,
        "-c",
        "from fabric_skills_settings.runtime_cli import app; app(prog_name='fabric-vibe')",
        "setup",
    ]
    return subprocess.run(cmd, cwd=str(target)).returncode
