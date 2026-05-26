"""Asset path resolution.

The package ships its asset trees in two layouts:
- installed wheel: `_profiles/`, `_setup/`, `_tools/` bundled alongside this package.
- source checkout: assets live one level up at `cli/profiles`, `cli/setup`, `cli/tools`.

These helpers pick the right root regardless of how the user installed the
package.
"""

from __future__ import annotations

from pathlib import Path

_PACKAGE_DIR = Path(__file__).resolve().parent.parent
_SRC_DIR = _PACKAGE_DIR.parent
_CLI_ROOT = _SRC_DIR.parent if _SRC_DIR.name == "src" else _SRC_DIR.parent


def _bundled_or_fallback(bundled_name: str, fallback_subdir: str) -> Path:
    bundled = _PACKAGE_DIR / bundled_name
    if bundled.is_dir():
        return bundled
    return _CLI_ROOT / fallback_subdir


def profiles_root() -> Path:
    return _bundled_or_fallback("_profiles", "profiles")


def setup_root() -> Path:
    return _bundled_or_fallback("_setup", "setup")


def tools_root() -> Path:
    return _bundled_or_fallback("_tools", "tools")


def package_dir() -> Path:
    return _PACKAGE_DIR
