"""fabric_agent_installer: install Microsoft Fabric agent profiles into a target repo.

Published on PyPI as `fabric-skills-settings`; the import name is `fabric_agent_installer`.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("fabric-skills-settings")
except PackageNotFoundError:
    __version__ = "0+unknown"
