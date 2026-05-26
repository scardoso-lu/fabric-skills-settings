"""Managed-block markers and `.env.example` placeholder detection."""

from __future__ import annotations

import re
from pathlib import Path

MANAGED_BEGIN = "<!-- BEGIN MANAGED BY fabric-skills-settings -->"
MANAGED_END = "<!-- END MANAGED BY fabric-skills-settings -->"
GITIGNORE_BEGIN = "# BEGIN MANAGED BY fabric-skills-settings"
GITIGNORE_END = "# END MANAGED BY fabric-skills-settings"

REFRESHABLE_PLACEHOLDER_FILES = {Path(".env.example")}
REFRESHABLE_SCAFFOLD_MARKERS: dict[Path, str] = {
    Path("tool/setup/setup.ps1"): "setup.ps1 - idempotent local setup for a Fabric agent target repo",
    Path("tool/setup/setup.sh"):  "setup.sh - idempotent local setup for a Fabric agent target repo",
}

PLACEHOLDER_VALUES = {
    "",
    "sandbox",
    "dev",
    "prod",
    "file",
    "<workspace-uuid>",
    "<lakehouse-uuid>",
    "<server>.<tenant>.fabric.microsoft.com",
    "<warehouse-or-sql-endpoint-db-name>",
}

_SUSPICIOUS_PATTERNS = (
    r"https?://",
    r"abfss://",
    r"jdbc:",
    r"AccountKey=",
    r"SharedAccessSignature=",
    r"eyJ[A-Za-z0-9_-]+",
)
_SENSITIVE_KEY = re.compile(r"(SECRET|PASSWORD|TOKEN|KEY|CONNECTION_STRING)", re.IGNORECASE)


def _strip_inline_comment(value: str) -> str:
    quote: str | None = None
    for idx, char in enumerate(value):
        if char in {"'", '"'}:
            quote = None if quote == char else char
        elif char == "#" and quote is None:
            return value[:idx].strip()
    return value.strip()


def has_managed_marker(path: Path) -> bool:
    if not path.exists() or not path.is_file():
        return False
    text = path.read_text(encoding="utf-8", errors="ignore")
    return MANAGED_BEGIN in text and MANAGED_END in text


def has_non_placeholder_env_values(path: Path) -> bool:
    """Return True if a refreshable env template appears to contain real values."""
    text = path.read_text(encoding="utf-8", errors="ignore")
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, raw_value = stripped.split("=", 1)
        value = _strip_inline_comment(raw_value).strip().strip('"').strip("'")
        if value in PLACEHOLDER_VALUES:
            continue
        if _SENSITIVE_KEY.search(key) and value:
            return True
        if any(re.search(pattern, value) for pattern in _SUSPICIOUS_PATTERNS):
            return True
        if value:
            return True
    return False


def can_refresh_unmanaged_placeholder(rel: Path, dest: Path) -> bool:
    if rel not in REFRESHABLE_PLACEHOLDER_FILES or not dest.exists():
        return False
    return not has_non_placeholder_env_values(dest)


def can_refresh_unmanaged_scaffold(rel: Path, dest: Path) -> bool:
    marker = REFRESHABLE_SCAFFOLD_MARKERS.get(rel)
    if marker is None or not dest.exists():
        return False
    text = dest.read_text(encoding="utf-8", errors="ignore")
    return marker in text
