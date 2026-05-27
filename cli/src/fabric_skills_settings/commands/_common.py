"""Shared helpers for the install/check/refresh subcommands."""

from __future__ import annotations

import subprocess
from pathlib import Path

from ..core.files import WriteOptions, render_content, write_file
from ..core.gitignore import merge_gitignore
from ..core.markers import can_refresh_unmanaged_scaffold, has_managed_marker
from ..core.paths import package_dir, profiles_root
from ..core.profiles import (
    collect_profile_files,
    collect_shared_files,
    planned_profiles,
)


def resolve_target(target: str | None, allow_package_dir: bool = False) -> Path:
    path = Path(target).expanduser().resolve() if target else Path.cwd()
    if not path.exists() or not path.is_dir():
        raise SystemExit(f"Target does not exist or is not a directory: {path}")
    if not _is_git_repo(path):
        raise SystemExit(f"Target is not a git repository: {path}")
    if path == package_dir() and not allow_package_dir:
        raise SystemExit("Refusing to install into the package directory without --self-test")
    return path


def _is_git_repo(path: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def apply_profile_set(
    target: Path,
    profile: str,
    options: WriteOptions,
) -> tuple[list[str], list[str]]:
    """Run the full install/check operation set, return (operations, profiles)."""
    profiles = planned_profiles(profile)
    operations: list[str] = []

    for prof in profiles:
        for src, rel, managed in collect_profile_files(prof):
            operations.append(write_file(src, target / rel, managed, options, rel))

    for src, rel, managed in collect_shared_files():
        dest = target / rel
        if dest.exists() and rel.parts and rel.parts[0] == "memory" and not has_managed_marker(dest):
            operations.append(f"KEEP existing {dest}")
            continue
        operations.append(write_file(src, dest, managed, options, rel))

    operations.extend(_remove_obsolete_profile_files(target, profiles, options))
    operations.extend(_remove_obsolete_tool_files(target, options))
    operations.append(merge_gitignore(target, profiles, options))

    return operations, profiles


def _remove_obsolete_profile_files(target: Path, profiles: list[str], options: WriteOptions) -> list[str]:
    operations: list[str] = []
    if "claude" in profiles:
        operations.extend(_remove_obsolete_claude_settings(target, options))
    return operations


def _remove_obsolete_claude_settings(target: Path, options: WriteOptions) -> list[str]:
    operations: list[str] = []
    old = target / ".claude" / "settings.json"
    if not old.exists():
        return operations
    expected = render_content(profiles_root() / "claude" / "settings.local.json", False)
    current = old.read_text(encoding="utf-8", errors="ignore")
    if current != expected:
        operations.append(f"KEEP custom obsolete path {old}")
        return operations
    if options.check:
        operations.append(f"OBSOLETE {old}")
        return operations
    if options.dry_run:
        operations.append(f"DELETE {old}")
        return operations
    old.unlink()
    operations.append(f"DELETE {old}")
    return operations


def _remove_obsolete_tool_files(target: Path, options: WriteOptions) -> list[str]:
    """Remove old package-owned target helpers; fabric-vibe now runs bundled tools."""
    operations: list[str] = []
    for rel in (Path("tool/setup/setup.ps1"), Path("tool/setup/setup.sh")):
        old = target / rel
        if not old.exists():
            continue
        if not has_managed_marker(old) and not can_refresh_unmanaged_scaffold(rel, old):
            operations.append(f"KEEP custom obsolete path {old}")
            continue
        if options.check:
            operations.append(f"OBSOLETE {old}")
            continue
        if options.dry_run:
            operations.append(f"DELETE {old}")
            continue
        old.unlink()
        operations.append(f"DELETE {old}")
    return operations
