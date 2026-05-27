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

ROOT = Path.cwd()
REGISTRY = ROOT / "workspaces.json"

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


def _resolve_fab_command() -> list[str]:
    """Locate `fab` via PATH — handles fab.exe on Windows, fab on Unix."""
    import shutil
    found = shutil.which("fab")
    if found:
        return [found]
    raise SystemExit("fab executable not found. Install with: uv tool install ms-fabric-cli")


def _fab_api(endpoint: str) -> dict:
    fab_cmd = _resolve_fab_command()
    cmd = [*fab_cmd, "api", endpoint, "-X", "get", "--output_format", "json"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        raise SystemExit(
            f"fab api {endpoint!r} returned non-JSON output.\n"
            f"stdout: {result.stdout!r}\n"
            f"stderr: {result.stderr!r}"
        )


def _fetch_all_pages(endpoint: str) -> list[dict]:
    """Fetch every page from a Fabric API list endpoint, following continuationToken."""
    all_items: list[dict] = []
    # Strip any existing query string so continuation params don't accumulate.
    base_endpoint = endpoint.split("?")[0]
    next_endpoint: str | None = endpoint
    while next_endpoint is not None:
        resp = _fab_api(next_endpoint)
        data = resp.get("result", {}).get("data", [])
        if not data:
            break
        text = data[0].get("text") or {}
        all_items.extend(text.get("value", []))
        token = text.get("continuationToken")
        next_endpoint = f"{base_endpoint}?continuationToken={token}" if token else None
    return all_items


def _discover_workspace_items(ws_id: str, log: object) -> dict[str, list[dict]]:
    items: dict[str, list[dict]] = {}

    # Lakehouses via specialized endpoint (includes OneLake properties)
    try:
        items["Lakehouse"] = _fetch_all_pages(f"workspaces/{ws_id}/lakehouses")
    except SystemExit as exc:
        log(f"    Warning: could not fetch lakehouses — {exc}")
        items["Lakehouse"] = []

    # Warehouses via specialized endpoint (includes connectionString)
    try:
        items["Warehouse"] = _fetch_all_pages(f"workspaces/{ws_id}/warehouses")
    except SystemExit as exc:
        log(f"    Warning: could not fetch warehouses — {exc}")
        items["Warehouse"] = []

    # Notebooks and DataPipelines via generic items endpoint
    try:
        all_items = _fetch_all_pages(f"workspaces/{ws_id}/items")
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

    workspaces_raw = _fetch_all_pages("workspaces")
    if not workspaces_raw:
        log("No workspaces returned. Verify authentication: fab api workspaces --output_format json")
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
