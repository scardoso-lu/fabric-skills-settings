#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Discover all Fabric workspaces and their resources via the Fabric API.

Runs once per session, immediately after authentication. Queries the Fabric
REST API for every accessible workspace and its Lakehouses (with properties),
Warehouses (with connectionString), Notebooks, and DataPipelines. Writes the
full API response to workspaces.json at the project root.

Preserves the active workspace selection from any previous run.

Usage:
    python tool/workspace/init.py
    python tool/workspace/init.py --quiet
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "workspaces.json"

_PS_CANDIDATES = [
    Path(r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"),
    Path(r"C:\Program Files\PowerShell\7\pwsh.exe"),
]


def _load_env(root: Path) -> None:
    env_file = root / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and val[0] in ('"', "'") and val[-1] == val[0]:
            val = val[1:-1]
        else:
            val = val.split("#")[0].strip()
        os.environ.setdefault(key, val)


_load_env(ROOT)


def _fab_sandbox_dir() -> Path:
    if os.name == "nt":
        localappdata = os.environ.get("LOCALAPPDATA", "")
        base = Path(localappdata) if localappdata else Path.home()
    else:
        base = Path.home() / ".cache"
    return base / "fabric-fab-home"


def _user_home() -> Path:
    if os.name == "nt":
        return Path.home()
    import pwd
    return Path(pwd.getpwuid(os.getuid()).pw_dir)


def _resolve_fab_command() -> tuple[list[str], bool]:
    wrapper = ROOT / "tool" / "setup" / "fab-sandbox.ps1"
    if os.name == "nt" and wrapper.exists():
        ps = next((str(p) for p in _PS_CANDIDATES if p.exists()), None)
        if ps is None:
            raise SystemExit(
                "PowerShell not found at expected system paths."
            )
        return [ps, "-ExecutionPolicy", "Bypass", "-File", str(wrapper)], True
    candidate = _user_home() / ".local" / "bin" / "fab"
    if candidate.exists():
        return [str(candidate)], False
    raise SystemExit("fab executable not found. Install with: uv tool install ms-fabric-cli")


def _fab_api(endpoint: str) -> dict:
    fab_cmd, uses_wrapper = _resolve_fab_command()
    sandbox_home = _fab_sandbox_dir()
    sandbox_home.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        sandbox_home.chmod(0o700)
    env = {**os.environ}
    if uses_wrapper:
        env.pop("HOME", None)
    else:
        env["HOME"] = str(sandbox_home)
    cmd = [*fab_cmd, "api", endpoint, "-X", "get", "--output_format", "json"]
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        raise SystemExit(
            f"fab api {endpoint!r} returned non-JSON output.\n"
            f"stdout: {result.stdout!r}\n"
            f"stderr: {result.stderr!r}"
        )


def _value_list(resp: dict) -> list[dict]:
    """Extract the item list from a fab api JSON response."""
    data = resp.get("result", {}).get("data", [])
    if not data:
        return []
    text = data[0].get("text") or {}
    return text.get("value", [])


def _discover_workspace_items(ws_id: str, log: object) -> dict[str, list[dict]]:
    items: dict[str, list[dict]] = {}

    # Lakehouses via specialized endpoint (includes OneLake properties)
    try:
        items["Lakehouse"] = _value_list(_fab_api(f"workspaces/{ws_id}/lakehouses"))
    except SystemExit as exc:
        log(f"    Warning: could not fetch lakehouses — {exc}")
        items["Lakehouse"] = []

    # Warehouses via specialized endpoint (includes connectionString)
    try:
        items["Warehouse"] = _value_list(_fab_api(f"workspaces/{ws_id}/warehouses"))
    except SystemExit as exc:
        log(f"    Warning: could not fetch warehouses — {exc}")
        items["Warehouse"] = []

    # Notebooks and DataPipelines via generic items endpoint
    try:
        all_items = _value_list(_fab_api(f"workspaces/{ws_id}/items"))
        items["Notebook"] = [i for i in all_items if i.get("type") == "Notebook"]
        items["DataPipeline"] = [i for i in all_items if i.get("type") == "DataPipeline"]
    except SystemExit as exc:
        log(f"    Warning: could not fetch items — {exc}")
        items["Notebook"] = []
        items["DataPipeline"] = []

    return items


def main(quiet: bool = False) -> None:
    def log(msg: str) -> None:
        if not quiet:
            print(msg, flush=True)

    log("Discovering Fabric workspaces via API...")

    existing_active: str | None = None
    if REGISTRY.exists():
        try:
            existing_active = json.loads(REGISTRY.read_text(encoding="utf-8")).get("active")
        except Exception:
            pass

    workspaces_resp = _fab_api("workspaces")
    workspaces_raw = _value_list(workspaces_resp)
    if not workspaces_raw:
        log("No workspaces returned. Verify authentication: bash tool/setup/fab-sandbox api workspaces --output_format json")
        raise SystemExit(1)

    log(f"Found {len(workspaces_raw)} workspace(s)")
    workspaces: list[dict] = []

    for ws in workspaces_raw:
        ws_id = ws.get("id", "")
        ws_name = ws.get("displayName", ws_id)
        log(f"  Scanning: {ws_name}")

        item_map = _discover_workspace_items(ws_id, log)
        entry = {**ws, "items": item_map}
        workspaces.append(entry)

        lh = len(item_map["Lakehouse"])
        wh = len(item_map["Warehouse"])
        nb = len(item_map["Notebook"])
        pl = len(item_map["DataPipeline"])
        log(f"    Lakehouses: {lh}  Warehouses: {wh}  Notebooks: {nb}  DataPipelines: {pl}")

    registry = {
        "active": existing_active,
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
        "workspaces": workspaces,
    }
    REGISTRY.write_text(json.dumps(registry, indent=2), encoding="utf-8")
    log(f"\nWritten: {REGISTRY.relative_to(ROOT)}")

    if existing_active:
        log(f"Active workspace preserved: {existing_active}")
    else:
        log("No active workspace set. Run: python tool/workspace/switch.py <displayName>")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--quiet", action="store_true", help="Suppress progress output")
    args = ap.parse_args()
    main(quiet=args.quiet)
