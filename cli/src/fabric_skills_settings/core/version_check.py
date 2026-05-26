"""Best-effort PyPI update checks for the installed CLI."""

from __future__ import annotations

import json
import os
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PACKAGE_NAME = "fabric-skills-settings"
PYPI_JSON_URL = f"https://pypi.org/pypi/{PACKAGE_NAME}/json"
DISABLE_ENV = "FABRIC_SKILLS_SETTINGS_DISABLE_VERSION_CHECK"
CACHE_TTL_SECONDS = 24 * 60 * 60
REQUEST_TIMEOUT_SECONDS = 1.5


@dataclass(frozen=True)
class VersionCheckResult:
    current: str
    latest: str
    update_available: bool


def update_notice(current_version: str) -> str | None:
    """Return an update notice when PyPI has a newer release.

    This is intentionally silent on network, cache, and version-parse failures:
    CLI startup should never fail because PyPI is unavailable.
    """
    if os.environ.get(DISABLE_ENV):
        return None
    result = check_latest_version(current_version)
    if result is None or not result.update_available:
        return None
    return (
        f"fabric-skills-settings {result.latest} is available "
        f"(installed: {result.current}). Update with: "
        f"uv tool upgrade {PACKAGE_NAME}"
    )


def check_latest_version(current_version: str) -> VersionCheckResult | None:
    if not current_version or current_version == "0+unknown":
        return None

    latest = _cached_latest_version()
    if latest is None:
        latest = _fetch_latest_version()
        if latest is None:
            return None
        _write_cache(latest)

    return VersionCheckResult(
        current=current_version,
        latest=latest,
        update_available=_is_newer(latest, current_version),
    )


def _fetch_latest_version() -> str | None:
    request = urllib.request.Request(
        PYPI_JSON_URL,
        headers={"Accept": "application/json", "User-Agent": f"{PACKAGE_NAME}/version-check"},
    )
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, json.JSONDecodeError, TimeoutError):
        return None

    version = payload.get("info", {}).get("version")
    return version if isinstance(version, str) and version else None


def _cached_latest_version() -> str | None:
    path = _cache_path()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    checked_at = payload.get("checked_at")
    latest = payload.get("latest")
    if not isinstance(checked_at, (int, float)) or not isinstance(latest, str):
        return None
    if time.time() - checked_at > CACHE_TTL_SECONDS:
        return None
    return latest


def _write_cache(latest: str) -> None:
    path = _cache_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"checked_at": time.time(), "latest": latest}),
            encoding="utf-8",
        )
    except OSError:
        return


def _cache_path() -> Path:
    base = (
        os.environ.get("XDG_CACHE_HOME")
        or os.environ.get("LOCALAPPDATA")
        or os.environ.get("APPDATA")
    )
    if base:
        return Path(base) / PACKAGE_NAME / "version-check.json"
    return Path(tempfile.gettempdir()) / PACKAGE_NAME / "version-check.json"


def _is_newer(candidate: str, current: str) -> bool:
    try:
        from packaging.version import Version

        return Version(candidate) > Version(current)
    except Exception:
        return _version_tuple(candidate) > _version_tuple(current)


def _version_tuple(value: str) -> tuple[Any, ...]:
    cleaned = value.strip().lstrip("v").split("+", 1)[0].split("-", 1)[0]
    parts: list[Any] = []
    for part in cleaned.split("."):
        if part.isdigit():
            parts.append(int(part))
        else:
            parts.append(part)
    return tuple(parts)
