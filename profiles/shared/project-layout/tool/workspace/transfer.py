#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Transfer Fabric notebooks and pipelines between workspaces.

Reads target workspace resource IDs from workspaces.json (populated by
tool/workspace/init.py). Matches lakehouses and warehouses by displayName.
If a name is not found in the target workspace, prompts the user for the ID
before continuing — never aborts silently.

Does not change the active workspace or modify .env.

Usage:
    python tool/workspace/transfer.py --notebook <name>  --to <displayName>
    python tool/workspace/transfer.py --topic    <topic> --to <displayName>
    python tool/workspace/transfer.py --pipeline <topic> --to <displayName>
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "workspaces.json"
ENV_FILE = ROOT / ".env"


def _load_registry() -> dict:
    if not REGISTRY.exists():
        raise SystemExit(
            "workspaces.json not found.\n"
            "Run: python tool/workspace/init.py"
        )
    try:
        return json.loads(REGISTRY.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"workspaces.json is malformed: {exc}") from exc


def _find_workspace(registry: dict, name: str) -> dict:
    for ws in registry.get("workspaces", []):
        if ws.get("displayName", "").lower() == name.lower():
            return ws
    names = [ws.get("displayName", "") for ws in registry.get("workspaces", [])]
    raise SystemExit(
        f"Target workspace not found: {name!r}\n"
        f"Available: {', '.join(names) or '(none)'}\n"
        "Run: python tool/workspace/init.py  (to refresh the registry)"
    )


def _load_env_credentials(env_file: Path) -> dict[str, str]:
    """Load credentials from .env, stopping at the auto-generated sentinel."""
    creds: dict[str, str] = {}
    if not env_file.exists():
        return creds
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if "do not edit below" in line:
            break
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
        creds[key] = val
    return creds


def _env_name(display_name: str) -> str:
    return display_name.upper().replace(" ", "_").replace("-", "_")


def _resolve_resource(items: list[dict], display_name: str, item_type: str) -> str:
    """Find a resource ID by displayName. Prompts the user if not found."""
    for item in items:
        if item.get("displayName", "").lower() == display_name.lower():
            return item.get("id", "")
    available = [i.get("displayName", "") for i in items]
    print(f'\n{item_type} "{display_name}" not found in target workspace.')
    print(f"Available {item_type}s: {', '.join(available) or '(none)'}")
    answer = input(
        f"Enter the {item_type} ID for this workspace (or press Enter to abort): "
    ).strip()
    if not answer:
        raise SystemExit("Aborted.")
    return answer


def _build_target_env(ws: dict, base_creds: dict[str, str]) -> dict[str, str]:
    """Build the full process environment for the target workspace."""
    env = {**os.environ}
    for key, val in base_creds.items():
        env[key] = val

    env["FABRIC_WORKSPACE_ID"] = ws.get("id", "")

    for lh in ws.get("items", {}).get("Lakehouse", []):
        lh_name = lh.get("displayName", "")
        lh_id = lh.get("id", "")
        env[f"FABRIC_LAKEHOUSE_{_env_name(lh_name)}"] = lh_id

    for wh in ws.get("items", {}).get("Warehouse", []):
        wh_name = wh.get("displayName", "")
        wh_id = wh.get("id", "")
        conn_str = (wh.get("properties") or {}).get("connectionString", "")
        env[f"FABRIC_WAREHOUSE_{_env_name(wh_name)}"] = wh_id
        if conn_str:
            env["FABRIC_WAREHOUSE_HOST"] = conn_str

    return env


def _run(cmd: list[str], env: dict[str, str]) -> None:
    result = subprocess.run(cmd, env=env, cwd=ROOT)
    if result.returncode != 0:
        raise SystemExit(f"Command failed (exit {result.returncode}): {' '.join(cmd)}")


def _parse_notebook_sentinels(source_path: Path) -> tuple[list[str], list[str]]:
    """Return (lakehouse_names, warehouse_names) declared in notebook sentinels."""
    lakehouses: list[str] = []
    warehouses: list[str] = []
    if not source_path.exists():
        return lakehouses, warehouses
    for line in source_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("# FABRIC_LAKEHOUSE:"):
            name = line.split(":", 1)[1].strip()
            if name:
                lakehouses.append(name)
        elif line.startswith("# FABRIC_WAREHOUSE:"):
            name = line.split(":", 1)[1].strip()
            if name:
                warehouses.append(name)
    return lakehouses, warehouses


def transfer_notebook(notebook_name: str, target_ws: dict, base_creds: dict[str, str]) -> None:
    target_name = target_ws.get("displayName", "")
    target_id = target_ws.get("id", "")

    matches = sorted((ROOT / "workspace").glob(f"**/{notebook_name}.py"))
    if not matches:
        raise SystemExit(
            f"Notebook source not found: {notebook_name}.py under workspace/\n"
            "The notebook must be checked out locally before transferring."
        )
    source_path = matches[0]
    lh_names, wh_names = _parse_notebook_sentinels(source_path)

    target_env = _build_target_env(target_ws, base_creds)

    # Resolve each sentinel against target workspace items, prompting on mismatch.
    # Override the env var using the sentinel name (not target displayName) so build.py
    # finds the correct ID regardless of minor naming differences between workspaces.
    for lh_name in lh_names:
        lh_id = _resolve_resource(
            target_ws.get("items", {}).get("Lakehouse", []), lh_name, "Lakehouse"
        )
        target_env[f"FABRIC_LAKEHOUSE_{_env_name(lh_name)}"] = lh_id

    for wh_name in wh_names:
        wh_id = _resolve_resource(
            target_ws.get("items", {}).get("Warehouse", []), wh_name, "Warehouse"
        )
        target_env[f"FABRIC_WAREHOUSE_{_env_name(wh_name)}"] = wh_id

    print(f"Building {notebook_name} for {target_name}...")
    _run([sys.executable, str(ROOT / "tool" / "notebook" / "build.py")], target_env)

    print(f"Deploying {notebook_name} to {target_name} ({target_id})...")
    _run(
        [sys.executable, str(ROOT / "tool" / "notebook" / "deploy.py"),
         "deploy", notebook_name, target_id],
        target_env,
    )

    print(f"Transferred {notebook_name} → {target_name}")


def transfer_topic(topic: str, target_ws: dict, base_creds: dict[str, str]) -> None:
    target_name = target_ws.get("displayName", "")
    topic_dir = ROOT / "workspace" / topic
    if not topic_dir.is_dir():
        raise SystemExit(f"Topic directory not found: workspace/{topic}/")
    notebooks = sorted(p.stem for p in topic_dir.glob("*.py"))
    if not notebooks:
        raise SystemExit(f"No .py notebook sources found in workspace/{topic}/")
    print(f"Transferring topic {topic!r}: {len(notebooks)} notebook(s) → {target_name}")
    for nb in notebooks:
        transfer_notebook(nb, target_ws, base_creds)


def transfer_pipeline(topic: str, target_ws: dict, base_creds: dict[str, str]) -> None:
    target_name = target_ws.get("displayName", "")
    target_id = target_ws.get("id", "")
    target_env = _build_target_env(target_ws, base_creds)

    print(f"Transferring pipeline for topic {topic!r} to {target_name}...")
    _run(
        [sys.executable, str(ROOT / "tool" / "pipeline" / "manage.py"),
         "--workspace", target_id, "create", "--topic", topic],
        target_env,
    )
    print(f"Transferred pipeline_{topic} → {target_name}")


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--notebook", metavar="NAME", help="Single notebook stem to transfer")
    group.add_argument("--topic", metavar="TOPIC", help="Transfer all notebooks for a topic")
    group.add_argument("--pipeline", metavar="TOPIC", help="Transfer a pipeline for a topic")
    ap.add_argument("--to", required=True, metavar="WORKSPACE", help="Target workspace displayName")
    args = ap.parse_args()

    registry = _load_registry()
    target_ws = _find_workspace(registry, args.to)
    base_creds = _load_env_credentials(ENV_FILE)

    if args.notebook:
        transfer_notebook(args.notebook, target_ws, base_creds)
    elif args.topic:
        transfer_topic(args.topic, target_ws, base_creds)
    elif args.pipeline:
        transfer_pipeline(args.pipeline, target_ws, base_creds)


if __name__ == "__main__":
    main()
