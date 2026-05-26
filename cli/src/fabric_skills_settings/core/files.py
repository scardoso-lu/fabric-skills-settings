"""Rendering managed file content and applying writes to the target tree."""

from __future__ import annotations

import datetime as dt
import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from .markers import (
    MANAGED_BEGIN,
    MANAGED_END,
    can_refresh_unmanaged_placeholder,
    can_refresh_unmanaged_scaffold,
    has_managed_marker,
)

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class WriteOptions:
    dry_run: bool = False
    check: bool = False
    force: bool = False
    backup: bool = False


def render_content(src: Path, managed: bool) -> str:
    """Wrap markdown files with managed markers when `managed=True`."""
    content = src.read_text(encoding="utf-8")
    if managed and src.suffix in {".md", ""}:
        if content.startswith("---\n"):
            close = content.find("\n---\n", 4)
            if close != -1:
                frontmatter = content[: close + 5]
                body = content[close + 5:]
                return f"{frontmatter}{MANAGED_BEGIN}\n{body.rstrip()}\n{MANAGED_END}\n"
        return f"{MANAGED_BEGIN}\n{content.rstrip()}\n{MANAGED_END}\n"
    return content


def _backup_file(path: Path) -> Path:
    stamp = dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    backup = path.with_name(f"{path.name}.{stamp}.bak")
    shutil.copy2(path, backup)
    return backup


def write_file(
    src: Path,
    dest: Path,
    managed: bool,
    options: WriteOptions,
    rel: Path | None = None,
) -> str:
    """Write `src` to `dest` and return a status line.

    The status verbs mirror the original installer: CREATE / UPDATE /
    UNCHANGED / OK / DIFF / MISSING — kept stable because tests and the
    `--check` exit code key off them.
    """
    content = render_content(src, managed)
    if options.check:
        if not dest.exists():
            return f"MISSING {dest}"
        current = dest.read_text(encoding="utf-8", errors="ignore")
        return f"OK {dest}" if current == content else f"DIFF {dest}"

    action = "CREATE"
    if dest.exists():
        current = dest.read_text(encoding="utf-8", errors="ignore")
        if current == content:
            return f"UNCHANGED {dest}"
        rel_path = rel or Path()
        if (
            not options.force
            and not has_managed_marker(dest)
            and not can_refresh_unmanaged_placeholder(rel_path, dest)
            and not can_refresh_unmanaged_scaffold(rel_path, dest)
        ):
            raise SystemExit(f"Refusing to overwrite non-managed file: {dest}")
        action = "UPDATE"

    if options.dry_run:
        return f"{action} {dest}"

    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and options.backup:
        backup = _backup_file(dest)
        log.info("BACKUP %s -> %s", dest, backup)
    dest.write_text(content, encoding="utf-8")
    if os.access(src, os.X_OK):
        dest.chmod(0o755)
    return f"{action} {dest}"
