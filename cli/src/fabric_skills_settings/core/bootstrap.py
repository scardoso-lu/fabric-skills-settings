"""Invoke the target repo's `tool/setup/setup.{sh,ps1}` bootstrap script."""

from __future__ import annotations

import logging
import platform
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)


def bootstrap_target(target: Path) -> int:
    """Run the target's setup script to finish bootstrap.

    Installs ms-fabric-cli via uv, prompts for SPN credentials, verifies auth,
    and populates workspaces.json. Returns the script's exit code.
    """
    is_windows = platform.system() == "Windows"
    script_name = "setup.ps1" if is_windows else "setup.sh"
    script = target / "tool" / "setup" / script_name
    if not script.exists():
        log.warning("SKIP bootstrap: %s not found", script.relative_to(target))
        return 0

    log.info("Bootstrapping target (%s)", target)
    log.info("running %s — will prompt for Fabric credentials if missing", script.relative_to(target))

    if is_windows:
        cmd = ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script)]
    else:
        cmd = ["bash", str(script)]
    return subprocess.run(cmd, cwd=str(target)).returncode
