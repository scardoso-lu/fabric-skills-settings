"""Install vendor-native Fabric agent profiles into a target repository."""

from __future__ import annotations

import argparse
import datetime as dt
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

# Installed wheel: _profiles/, _setup/ are bundled alongside this module.
# Editable install or source checkout: fall back to cli/profiles and cli/setup
# at the repo root. Everything else (skills, tools, content, fabric helpers)
# lives on the MCP server and is accessed via MCP tools.
_PACKAGE_DIR = Path(__file__).parent             # cli/fabric_agent_installer
_REPO_ROOT = _PACKAGE_DIR.parent.parent           # repo root
_CLI_ROOT = _PACKAGE_DIR.parent                   # cli/

_bundled = _PACKAGE_DIR / "_profiles"
PROFILES = _bundled if _bundled.is_dir() else _CLI_ROOT / "profiles"

MANAGED_BEGIN = "<!-- BEGIN MANAGED BY fabric-skills-settings -->"
MANAGED_END = "<!-- END MANAGED BY fabric-skills-settings -->"
GITIGNORE_BEGIN = "# BEGIN MANAGED BY fabric-skills-settings"
GITIGNORE_END = "# END MANAGED BY fabric-skills-settings"
REFRESHABLE_PLACEHOLDER_FILES = {Path(".env.example")}
REFRESHABLE_SCAFFOLD_MARKERS = {
    Path("tool/setup/setup.ps1"):                         "setup.ps1 - idempotent local setup for a Fabric agent target repo",
    Path("tool/setup/setup.sh"):                          "setup.sh - idempotent local setup for a Fabric agent target repo",
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("codex", "claude", "all"), required=True)
    parser.add_argument("--target", required=True, help="Target git repository path")
    parser.add_argument("--dry-run", action="store_true", help="Print planned changes without writing")
    parser.add_argument("--check", action="store_true", help="Verify target state without writing")
    parser.add_argument("--force", action="store_true", help="Overwrite non-managed existing files")
    parser.add_argument("--backup", action="store_true", help="Back up replaced files")
    parser.add_argument("--self-test", action="store_true", help="Allow targeting the package install directory")
    parser.add_argument(
        "--no-bootstrap",
        action="store_true",
        help="Skip the post-install target bootstrap (tool/setup/setup.{ps1,sh}) "
             "that creates .venv, installs Fabric CLI helpers, prompts for credentials, "
             "and populates workspaces.json. Use this in CI or when you only want files copied.",
    )
    return parser.parse_args()


def is_git_repo(path: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
        check=False,
    )
    return result.returncode == 0


def planned_profiles(profile: str) -> list[str]:
    if profile == "all":
        return ["codex", "claude"]
    return [profile]


def collect_files(profile: str) -> list[tuple[Path, Path, bool]]:
    """Return (source, relative target, managed_marker) entries.

    Skills are NOT shipped to the target. They live on the MCP server and
    are accessed by Claude through graph_get_node('skills/<name>').
    """
    entries: list[tuple[Path, Path, bool]] = []
    if profile == "codex":
        entries.append((PROFILES / "codex" / "AGENTS.md", Path("AGENTS.md"), True))
        entries.append((PROFILES / "codex" / "config.toml", Path(".codex/config.toml"), False))
        for src in sorted((PROFILES / "codex" / "agents").glob("*.toml")):
            entries.append((src, Path(".codex/agents") / src.name, False))
    elif profile == "claude":
        entries.append((PROFILES / "claude" / "CLAUDE.md", Path("CLAUDE.md"), True))
        entries.append((PROFILES / "claude" / "settings.local.json", Path(".claude/settings.local.json"), False))
        for src in sorted((PROFILES / "claude" / "agents").glob("*.md")):
            entries.append((src, Path(".claude/agents") / src.name, True))
    else:
        raise ValueError(f"Unknown profile: {profile}")
    return entries


def collect_shared_files() -> list[tuple[Path, Path, bool]]:
    """Walk the scaffold: .mcp.json, data/sandbox/, workspace/, .env.example.

    The graph lives on the MCP server now — target repos no longer receive
    memory/graph-content/, memory/rules/, or memory/.graph/. The MCP server
    is the canonical source for all graph content.
    """
    entries: list[tuple[Path, Path, bool]] = []
    shared = PROFILES / "shared"
    scaffold = shared / "scaffold"
    if scaffold.is_dir():
        for src in sorted(scaffold.rglob("*")):
            if src.is_file() and "__pycache__" not in src.parts and src.suffix not in {".pyc", ".pyo", ".pyd"}:
                entries.append((src, src.relative_to(scaffold), False))
    entries.append((shared / ".env.example", Path(".env.example"), False))
    return entries


def collect_tool_files() -> list[tuple[Path, Path, bool]]:
    """Walk cli/setup/ + cli/tools/ and copy each file to the target's tool/.

    cli/setup/ → target/tool/setup/ (env-setup scripts).
    cli/tools/ → target/tool/ (target-side helpers invoked locally via Bash,
        NOT MCP): notebook/, pipeline/, lakehouse/, workspace/ require
        ms-fabric-cli; lint/ and precommit/ are pure-Python deterministic
        checks. Server-side tools (validate, data, semantic_model, graph)
        live in server/ and don't ship.
    """
    entries: list[tuple[Path, Path, bool]] = []

    setup_root = _resolve_setup_root()
    if setup_root.is_dir():
        for src in sorted(setup_root.rglob("*")):
            if not src.is_file() or "__pycache__" in src.parts:
                continue
            if src.suffix in {".pyc", ".pyo", ".pyd"}:
                continue
            rel_under_setup = Path("setup") / src.relative_to(setup_root)
            entries.append((src, Path("tool") / rel_under_setup, False))

    tools_root = _resolve_tools_root()
    if tools_root.is_dir():
        for src in sorted(tools_root.rglob("*")):
            if not src.is_file() or "__pycache__" in src.parts:
                continue
            if src.suffix in {".pyc", ".pyo", ".pyd"}:
                continue
            rel_under_tools = src.relative_to(tools_root)
            entries.append((src, Path("tool") / rel_under_tools, False))

    return entries


def _resolve_setup_root() -> Path:
    """cli/setup/ in the source repo (or bundled _setup/ in the wheel)."""
    bundled = _PACKAGE_DIR / "_setup"
    if bundled.is_dir():
        return bundled
    return _CLI_ROOT / "setup"


def _resolve_tools_root() -> Path:
    """cli/tools/ in the source repo (or bundled _tools/ in the wheel)."""
    bundled = _PACKAGE_DIR / "_tools"
    if bundled.is_dir():
        return bundled
    return _CLI_ROOT / "tools"


def render_content(src: Path, managed: bool) -> str:
    content = src.read_text(encoding="utf-8")
    if managed and src.suffix in {".md", ""}:
        if content.startswith("---\n"):
            close = content.find("\n---\n", 4)
            if close != -1:
                frontmatter = content[: close + 5]
                body = content[close + 5 :]
                return f"{frontmatter}{MANAGED_BEGIN}\n{body.rstrip()}\n{MANAGED_END}\n"
        return f"{MANAGED_BEGIN}\n{content.rstrip()}\n{MANAGED_END}\n"
    return content


def has_managed_marker(path: Path) -> bool:
    if not path.exists() or not path.is_file():
        return False
    text = path.read_text(encoding="utf-8", errors="ignore")
    return MANAGED_BEGIN in text and MANAGED_END in text


def strip_inline_comment(value: str) -> str:
    """Remove shell-style comments from simple KEY=value template lines."""
    quote: str | None = None
    for idx, char in enumerate(value):
        if char in {"'", '"'}:
            quote = None if quote == char else char
        elif char == "#" and quote is None:
            return value[:idx].strip()
    return value.strip()


def has_non_placeholder_env_values(path: Path) -> bool:
    """Return true if a refreshable env template appears to contain local values."""
    text = path.read_text(encoding="utf-8", errors="ignore")
    suspicious_patterns = [
        r"https?://",
        r"abfss://",
        r"jdbc:",
        r"AccountKey=",
        r"SharedAccessSignature=",
        r"eyJ[A-Za-z0-9_-]+",
    ]
    sensitive_key = re.compile(r"(SECRET|PASSWORD|TOKEN|KEY|CONNECTION_STRING)", re.IGNORECASE)

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, raw_value = stripped.split("=", 1)
        value = strip_inline_comment(raw_value).strip().strip('"').strip("'")
        if value in PLACEHOLDER_VALUES:
            continue
        if sensitive_key.search(key) and value:
            return True
        if any(re.search(pattern, value) for pattern in suspicious_patterns):
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


def backup_file(path: Path) -> Path:
    stamp = dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    backup = path.with_name(f"{path.name}.{stamp}.bak")
    shutil.copy2(path, backup)
    return backup


def write_file(src: Path, dest: Path, managed: bool, args: argparse.Namespace, rel: Path | None = None) -> str:
    content = render_content(src, managed)
    if args.check:
        if not dest.exists():
            return f"MISSING {dest}"
        current = dest.read_text(encoding="utf-8", errors="ignore")
        if current != content:
            return f"DIFF {dest}"
        return f"OK {dest}"

    action = "CREATE"
    if dest.exists():
        current = dest.read_text(encoding="utf-8", errors="ignore")
        if current == content:
            return f"UNCHANGED {dest}"
        rel_path = rel or Path()
        if (
            not args.force
            and not has_managed_marker(dest)
            and not can_refresh_unmanaged_placeholder(rel_path, dest)
            and not can_refresh_unmanaged_scaffold(rel_path, dest)
        ):
            raise SystemExit(f"Refusing to overwrite non-managed file: {dest}")
        action = "UPDATE"

    if args.dry_run:
        return f"{action} {dest}"

    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and args.backup:
        backup = backup_file(dest)
        print(f"BACKUP {dest} -> {backup}")
    dest.write_text(content, encoding="utf-8")
    if os.access(src, os.X_OK):
        dest.chmod(0o755)
    return f"{action} {dest}"


_PROFILE_IGNORES: dict[str, list[str]] = {
    "shared": [],
    "codex": ["AGENTS.md", ".agents/", ".codex/"],
    "claude": ["CLAUDE.md", ".claude/"],
}


def merge_gitignore(target: Path, profiles: list[str], args: argparse.Namespace) -> str:
    src = PROFILES / "shared" / ".gitignore.fragment"
    lines = [src.read_text(encoding="utf-8").rstrip()]
    profile_entries = [e for p in ["shared"] + profiles for e in _PROFILE_IGNORES.get(p, [])]
    if profile_entries:
        lines.append("\n# Installed agent profiles")
        lines.extend(profile_entries)
    fragment = "\n".join(lines)
    block = f"{GITIGNORE_BEGIN}\n{fragment}\n{GITIGNORE_END}\n"
    dest = target / ".gitignore"

    if args.check:
        if not dest.exists():
            return "MISSING .gitignore managed block"
        text = dest.read_text(encoding="utf-8", errors="ignore")
        return "OK .gitignore" if block in text else "DIFF .gitignore managed block"

    if dest.exists():
        text = dest.read_text(encoding="utf-8", errors="ignore")
        if block in text:
            return "UNCHANGED .gitignore"
        if GITIGNORE_BEGIN in text and GITIGNORE_END in text:
            before, rest = text.split(GITIGNORE_BEGIN, 1)
            _, after = rest.split(GITIGNORE_END, 1)
            new_text = before.rstrip() + "\n" + block + after.lstrip("\n")
            action = "UPDATE .gitignore"
        else:
            new_text = text.rstrip() + "\n\n" + block
            action = "UPDATE .gitignore"
    else:
        new_text = block
        action = "CREATE .gitignore"

    if args.dry_run:
        return action
    dest.write_text(new_text, encoding="utf-8")
    return action


def remove_obsolete_profile_files(target: Path, profiles: list[str], args: argparse.Namespace) -> list[str]:
    operations: list[str] = []
    if "claude" in profiles:
        operations.extend(_remove_obsolete_claude_settings(target, args))
    return operations


def _remove_obsolete_claude_settings(target: Path, args: argparse.Namespace) -> list[str]:
    operations: list[str] = []
    old = target / ".claude" / "settings.json"
    if not old.exists():
        return operations
    expected = render_content(PROFILES / "claude" / "settings.local.json", False)
    current = old.read_text(encoding="utf-8", errors="ignore")
    if current != expected:
        operations.append(f"KEEP custom obsolete path {old}")
        return operations
    if args.check:
        operations.append(f"OBSOLETE {old}")
        return operations
    if args.dry_run:
        operations.append(f"DELETE {old}")
        return operations
    old.unlink()
    operations.append(f"DELETE {old}")
    return operations


def bootstrap_target(target: Path) -> int:
    """Run the target's tool/setup/setup.{ps1,sh} to finish bootstrap.

    This installs ms-fabric-cli via uv, prompts the human for FABRIC_TENANT_ID /
    FABRIC_CLIENT_ID / FABRIC_CLIENT_SECRET and FABRIC_SERVER_URL, runs
    `fab api workspaces` to verify auth, and populates workspaces.json.

    Returns the bootstrap script's exit code. A non-zero exit propagates so the
    caller can see the failure without partially-bootstrapping in silence.
    """
    is_windows = platform.system() == "Windows"
    script_name = "setup.ps1" if is_windows else "setup.sh"
    script = target / "tool" / "setup" / script_name
    if not script.exists():
        print(f"\nSKIP bootstrap: {script.relative_to(target)} not found", file=sys.stderr)
        return 0

    print(f"\n── Bootstrapping target ({target}) ──")
    print(f"   running {script.relative_to(target)} — will prompt for Fabric credentials if missing")

    if is_windows:
        cmd = ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script)]
    else:
        cmd = ["bash", str(script)]
    return subprocess.run(cmd, cwd=str(target)).returncode


def main() -> int:
    args = parse_args()
    target = Path(args.target).expanduser().resolve()
    if not target.exists() or not target.is_dir():
        raise SystemExit(f"Target does not exist or is not a directory: {target}")
    if not is_git_repo(target):
        raise SystemExit(f"Target is not a git repository: {target}")
    if target == _PACKAGE_DIR and not args.self_test:
        raise SystemExit("Refusing to install into the package directory without --self-test")

    profiles = planned_profiles(args.profile)
    operations: list[str] = []
    for profile in profiles:
        for src, rel, managed in collect_files(profile):
            operations.append(write_file(src, target / rel, managed, args, rel))
    for src, rel, managed in collect_shared_files():
        dest = target / rel
        if dest.exists() and rel.parts and rel.parts[0] == "memory" and not has_managed_marker(dest):
            operations.append(f"KEEP existing {dest}")
            continue
        operations.append(write_file(src, dest, managed, args, rel))
    for src, rel, managed in collect_tool_files():
        operations.append(write_file(src, target / rel, managed, args, rel))
    operations.extend(remove_obsolete_profile_files(target, profiles, args))
    operations.append(merge_gitignore(target, profiles, args))

    for operation in operations:
        print(operation)
    if args.check and any(op.startswith(("MISSING", "DIFF", "OBSOLETE")) for op in operations):
        return 1

    # Single-step UX: after files are in place, run the target's bootstrap
    # script in the same invocation. Skip when nothing was actually written
    # (dry-run / check / explicit --no-bootstrap).
    if not args.dry_run and not args.check and not args.no_bootstrap:
        rc = bootstrap_target(target)
        if rc != 0:
            return rc
    return 0


if __name__ == "__main__":
    sys.exit(main())
