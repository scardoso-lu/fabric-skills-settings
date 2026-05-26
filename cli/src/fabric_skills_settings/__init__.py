"""fabric_skills_settings — Microsoft Fabric agent profile installer.

Published on PyPI as `fabric-skills-settings`. Provides the `fabric-agents`
console script (with `install`, `check`, and `refresh` subcommands) and the
`fabric-cli` target-side proxy.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("fabric-skills-settings")
except PackageNotFoundError:
    __version__ = "0+unknown"

__all__ = ["__version__"]
