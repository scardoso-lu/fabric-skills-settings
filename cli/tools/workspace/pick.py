#!/usr/bin/env python3
"""Interactive (or env-driven) active-workspace selector.

Reads workspaces.json from the project root, shows the available workspaces,
and asks the human to pick one. Then dispatches to switch.py with the chosen
displayName so the active workspace + per-resource env keys land in .env.

This used to be an inline heredoc inside setup.{ps1,sh} but that piped stdin
away from the terminal — making the interactive prompt unreachable when the
setup script was invoked from `fabric-agents install`. Splitting it out keeps
stdin attached to the parent TTY.

Selection precedence:
  1. FABRIC_WORKSPACE_DISPLAYNAME env var (non-interactive override)
  2. Single-workspace auto-pick
  3. Interactive prompt (requires TTY)
  4. Skip gracefully if no TTY and no env override
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "workspaces.json"
SWITCH = ROOT / "tool" / "workspace" / "switch.py"


def main() -> int:
    if not REGISTRY.exists():
        print(f"  workspaces.json not found at {REGISTRY}. Run python tool/workspace/init.py first.", file=sys.stderr)
        return 1

    try:
        reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"  Could not parse workspaces.json: {exc}", file=sys.stderr)
        return 1

    workspaces = reg.get("workspaces", [])
    active = reg.get("active")

    if active:
        print(f"  Active workspace already set: {active}")
        return 0

    if not workspaces:
        print("  No accessible workspaces. Verify the service principal has Contributor on at least one Fabric workspace.", file=sys.stderr)
        return 1

    print(f"  Found {len(workspaces)} workspace(s):")
    for idx, ws in enumerate(workspaces, 1):
        print(f"    {idx}. {ws.get('displayName', '<unnamed>')}")

    override = os.environ.get("FABRIC_WORKSPACE_DISPLAYNAME", "").strip()
    if override:
        print(f"\n  FABRIC_WORKSPACE_DISPLAYNAME={override!r}; using that.")
        selection = override
    elif len(workspaces) == 1:
        selection = workspaces[0].get("displayName", "")
        print(f"\n  Only one workspace; auto-selecting {selection!r}.")
    elif not sys.stdin.isatty():
        print("\n  stdin is not a TTY; skipping interactive prompt.")
        print("  Run later:  python tool/workspace/switch.py <displayName>")
        return 0
    else:
        raw = input("\n  Pick the active workspace (number or displayName): ").strip()
        if not raw:
            print("  No selection; skipping.")
            return 0
        if raw.isdigit():
            i = int(raw) - 1
            if not (0 <= i < len(workspaces)):
                print(f"  Out of range: {raw}", file=sys.stderr)
                return 1
            selection = workspaces[i].get("displayName", "")
        else:
            selection = raw

    rc = subprocess.run([sys.executable, str(SWITCH), selection]).returncode
    return rc


if __name__ == "__main__":
    sys.exit(main())
