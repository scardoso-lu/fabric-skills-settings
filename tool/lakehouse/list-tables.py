#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""List Microsoft Fabric Lakehouse tables and column schemas.

Reads FABRIC_WORKSPACE_ID (required) and FABRIC_LAKEHOUSE_ID (optional) from .env.
Queries the Fabric REST API for tables and fetches column names/types from each
table's Delta transaction log via the OneLake DFS endpoint.

Usage (from target repo root):
    python tool/lakehouse/list-tables.py
    python tool/lakehouse/list-tables.py --lakehouse <name-or-id>
    python tool/lakehouse/list-tables.py --table <table-name>
    python tool/lakehouse/list-tables.py --json
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[2]
FAB_SANDBOX_HOME = os.environ.get("FAB_SANDBOX_HOME") or str(Path(tempfile.gettempdir()) / "fabric-fab-home")
ONELAKE_DFS = "https://onelake.dfs.fabric.microsoft.com"


def _user_home() -> Path:
    if os.name == "nt":
        home = Path.home()
    else:
        import pwd
        home = Path(pwd.getpwuid(os.getuid()).pw_dir)
    if not home.exists():
        raise SystemExit(f"Could not resolve current user's home directory: {home}")
    return home


def _load_env(root: Path) -> None:
    env_file = root / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        val = val.split("#")[0].strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), val)


def _resolve_fab_command() -> tuple[list[str], bool]:
    wrapper = SCRIPT_ROOT / "tool" / "setup" / "fab-sandbox.ps1"
    if os.name == "nt" and wrapper.exists():
        ps = os.environ.get("POWERSHELL_BIN") or "powershell.exe"
        return [ps, "-ExecutionPolicy", "Bypass", "-File", str(wrapper)], True
    candidate = _user_home() / ".local" / "bin" / "fab"
    if candidate.exists():
        return [str(candidate)], False
    raise SystemExit("fab not found. Install with: uv tool install ms-fabric-cli")


def _fab_env(uses_wrapper: bool) -> dict[str, str]:
    env = {**os.environ}
    sandbox = str(Path(FAB_SANDBOX_HOME).resolve())
    Path(sandbox).mkdir(parents=True, exist_ok=True)
    if not uses_wrapper:
        env["HOME"] = sandbox
    return env


def _fab_api(endpoint: str) -> dict:
    fab_cmd, uses_wrapper = _resolve_fab_command()
    result = subprocess.run(
        [*fab_cmd, "api", "get", endpoint],
        capture_output=True, text=True, env=_fab_env(uses_wrapper),
    )
    if result.returncode != 0:
        raise SystemExit(f"fab api get {endpoint!r} failed:\n{result.stderr.strip()}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"fab api returned non-JSON for {endpoint!r}: {exc}") from exc


def _fab_auth_token() -> str | None:
    """Return an OAuth bearer token from the fab credential cache, or None."""
    try:
        fab_cmd, uses_wrapper = _resolve_fab_command()
        result = subprocess.run(
            [*fab_cmd, "auth", "token"],
            capture_output=True, text=True, env=_fab_env(uses_wrapper),
        )
        if result.returncode != 0:
            return None
        raw = result.stdout.strip()
        if raw.startswith("{"):
            data = json.loads(raw)
            return data.get("accessToken") or data.get("access_token") or data.get("token")
        return raw or None
    except Exception:
        return None


def _paginate(endpoint: str) -> list[dict]:
    """Fetch all pages from a Fabric REST API list endpoint."""
    items: list[dict] = []
    continuation: str | None = None
    while True:
        url = endpoint + (f"?continuationToken={continuation}" if continuation else "")
        page = _fab_api(url)
        items.extend(page.get("data") or page.get("value") or [])
        continuation = page.get("continuationToken")
        if not continuation:
            break
    return items


def _type_str(t: object) -> str:
    if isinstance(t, str):
        return t
    if isinstance(t, dict):
        kind = t.get("type", "")
        if kind == "array":
            return f"array<{_type_str(t.get('elementType', '?'))}>"
        if kind == "map":
            return f"map<{_type_str(t.get('keyType', '?'))},{_type_str(t.get('valueType', '?'))}>"
        if kind == "struct":
            inner = ", ".join(
                f"{f['name']}:{_type_str(f['type'])}" for f in t.get("fields", [])
            )
            return f"struct<{inner}>"
    return str(t)


def _parse_schema_string(schema_str: str) -> list[dict]:
    try:
        schema = json.loads(schema_str)
        return [
            {
                "name": f["name"],
                "type": _type_str(f["type"]),
                "nullable": f.get("nullable", True),
            }
            for f in schema.get("fields", [])
        ]
    except (json.JSONDecodeError, KeyError, TypeError):
        return []


def _fetch_schema(
    workspace_id: str, lakehouse_id: str, table_name: str, token: str
) -> list[dict]:
    """Fetch column metadata from the table's Delta log via OneLake DFS."""
    url = (
        f"{ONELAKE_DFS}/{workspace_id}/{lakehouse_id}"
        f"/Tables/{table_name}/_delta_log/00000000000000000000.json"
    )
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            text = resp.read().decode("utf-8")
    except (urllib.error.HTTPError, urllib.error.URLError, OSError):
        return []
    # Delta log is NDJSON — one JSON action object per line
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            action = json.loads(line)
        except json.JSONDecodeError:
            continue
        metadata = action.get("metaData")
        if not metadata:
            continue
        cols = _parse_schema_string(metadata.get("schemaString", ""))
        if cols:
            return cols
    return []


def _resolve_lakehouses(workspace_id: str, name_or_id: str | None) -> list[dict]:
    all_lh = _paginate(f"/v1/workspaces/{workspace_id}/lakehouses")
    if not name_or_id:
        return all_lh
    noi = name_or_id.lower()
    matches = [
        lh for lh in all_lh
        if lh.get("id", "").lower() == noi or lh.get("displayName", "").lower() == noi
    ]
    if not matches:
        raise SystemExit(
            f"No lakehouse found matching {name_or_id!r} in workspace {workspace_id}"
        )
    return matches


def _print_results(
    lakehouses: list[dict],
    tables_by_lh: dict[str, list[dict]],
    schemas: dict[str, dict[str, list[dict]]],
    schema_available: bool,
) -> None:
    if not schema_available:
        print(
            "Note: column schema unavailable (fab auth token not accessible).\n"
            "      Run DESCRIBE TABLE EXTENDED <table> in the SQL Analytics Endpoint.\n"
        )
    for lh in lakehouses:
        lh_id = lh["id"]
        lh_name = lh.get("displayName", lh_id)
        tables = tables_by_lh.get(lh_id, [])
        print(f"Lakehouse: {lh_name}  ({lh_id})")
        if not tables:
            print("  (no tables)\n")
            continue
        for tbl in tables:
            name = tbl.get("name", "?")
            ttype = tbl.get("type", "")
            fmt = tbl.get("format", "")
            print(f"  {name}  [{ttype} · {fmt}]")
            cols = schemas.get(lh_id, {}).get(name, [])
            for col in cols:
                nullable = "" if col["nullable"] else "  NOT NULL"
                print(f"    {col['name']:<40}  {col['type']}{nullable}")
            if not cols and schema_available:
                print(
                    "    (schema not read — table may use a checkpoint log;"
                    " re-run after the next Delta write)"
                )
        print()


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--workspace", help="Workspace ID (overrides FABRIC_WORKSPACE_ID in .env)")
    ap.add_argument(
        "--lakehouse",
        help="Lakehouse display name or ID (default: FABRIC_LAKEHOUSE_ID from .env, then all)",
    )
    ap.add_argument("--table", help="Filter to one table name")
    ap.add_argument("--json", action="store_true", dest="as_json", help="Output raw JSON")
    args = ap.parse_args()

    _load_env(SCRIPT_ROOT)

    workspace_id = (args.workspace or os.environ.get("FABRIC_WORKSPACE_ID", "")).strip()
    if not workspace_id:
        raise SystemExit(
            "FABRIC_WORKSPACE_ID is not set. Add it to .env or pass --workspace."
        )

    lakehouse_filter = (
        args.lakehouse or os.environ.get("FABRIC_LAKEHOUSE_ID", "").strip() or None
    )

    token = _fab_auth_token()
    lakehouses = _resolve_lakehouses(workspace_id, lakehouse_filter)

    tables_by_lh: dict[str, list[dict]] = {}
    schemas: dict[str, dict[str, list[dict]]] = {}

    for lh in lakehouses:
        lh_id = lh["id"]
        tables = _paginate(f"/v1/workspaces/{workspace_id}/lakehouses/{lh_id}/tables")
        if args.table:
            tables = [t for t in tables if t.get("name", "").lower() == args.table.lower()]
        tables_by_lh[lh_id] = tables

        if token:
            schemas[lh_id] = {
                t["name"]: _fetch_schema(workspace_id, lh_id, t["name"], token)
                for t in tables
                if t.get("name")
            }

    if args.as_json:
        output = [
            {
                "lakehouse": lh.get("displayName", lh["id"]),
                "id": lh["id"],
                "tables": [
                    {
                        **t,
                        "columns": schemas.get(lh["id"], {}).get(t.get("name", ""), []),
                    }
                    for t in tables_by_lh.get(lh["id"], [])
                ],
            }
            for lh in lakehouses
        ]
        print(json.dumps(output, indent=2))
        return 0

    _print_results(lakehouses, tables_by_lh, schemas, schema_available=bool(token))
    return 0


if __name__ == "__main__":
    sys.exit(main())
