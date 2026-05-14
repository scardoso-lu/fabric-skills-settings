#!/usr/bin/env python3
"""Minimal MCP server that exposes selected Microsoft Fabric CLI commands.

The server loads project-root .env values into its own process environment,
then invokes the local Fabric CLI.
It does not store or emit credentials.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT / ".env"
FAB_SANDBOX_HOME = os.environ.get("FAB_SANDBOX_HOME", "/tmp/fabric-fab-home")


def user_home() -> Path:
    if os.name == "nt":
        home = Path.home()
    else:
        import pwd
        home = Path(pwd.getpwuid(os.getuid()).pw_dir)
    if not home.exists():
        raise RuntimeError(f"Could not resolve current user's home directory: {home}")
    return home


def load_env() -> None:
    if not ENV_FILE.exists():
        return
    for raw_line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.split("#", 1)[0].strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value


def fab_command() -> list[str]:
    home = user_home()
    candidates = [home / ".local" / "bin" / "fab.exe", home / ".local" / "bin" / "fab"]
    for candidate in candidates:
        if candidate.exists():
            return [str(candidate)]
    raise RuntimeError(f"fab executable not found in {home / '.local' / 'bin'}")


def response(request_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def error_response(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def text_content(text: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}]}


def run_fab(args: list[str]) -> str:
    Path(FAB_SANDBOX_HOME).mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "HOME": FAB_SANDBOX_HOME}
    completed = subprocess.run(
        fab_command() + args,
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    output = completed.stdout.strip()
    if completed.stderr.strip():
        output = f"{output}\n{completed.stderr.strip()}".strip()
    if completed.returncode != 0:
        raise RuntimeError(output or f"fab exited with status {completed.returncode}")
    return output


def workspace_id() -> str:
    value = os.environ.get("FABRIC_WORKSPACE_ID", "").strip()
    if not value:
        raise RuntimeError("FABRIC_WORKSPACE_ID is not set. Add it to .env.")
    return value


def _parse_items(raw: str) -> list[dict]:
    try:
        data = json.loads(raw)
        entries = data.get("result", {}).get("data", [])
        return entries[0].get("text", {}).get("value", []) if entries else []
    except Exception:
        return []


def handle_tool_call(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name == "fabric_list":
        item_type = str(arguments.get("type", "")).strip()
        ws = workspace_id()
        raw = run_fab(["api", f"workspaces/{ws}/items", "--output_format", "json"])
        items = _parse_items(raw)
        if item_type:
            items = [i for i in items if i.get("type", "").lower() == item_type.lower()]
        return text_content(json.dumps(items, indent=2))

    if name == "fabric_get":
        item = str(arguments.get("item", "")).strip()
        if not item:
            raise RuntimeError("fabric_get requires an 'item' argument (display name or item ID).")
        ws = workspace_id()
        raw = run_fab(["api", f"workspaces/{ws}/items", "--output_format", "json"])
        items = _parse_items(raw)
        found = [i for i in items if i.get("id") == item or i.get("displayName") == item]
        if found:
            return text_content(json.dumps(found[0], indent=2))
        return text_content(f"Item '{item}' not found in workspace {ws}")

    if name == "fabric_api_get":
        path = str(arguments.get("path", "")).strip()
        # Accept both /v1/workspaces/... and workspaces/... forms
        path = path.lstrip("/")
        if path.startswith("v1/"):
            path = path[3:]
        raw = run_fab(["api", path, "--output_format", "json"])
        return text_content(raw)

    raise RuntimeError(f"Unknown tool: {name}")


TOOLS = [
    {
        "name": "fabric_list",
        "description": "List items in the configured Fabric workspace. Optionally filter by type (e.g. Notebook, Lakehouse).",
        "inputSchema": {
            "type": "object",
            "properties": {"type": {"type": "string", "description": "Optional Fabric item type filter (e.g. Notebook, Lakehouse, DataPipeline)."}},
            "additionalProperties": False,
        },
    },
    {
        "name": "fabric_get",
        "description": "Get details for a single item in the configured Fabric workspace by display name or item ID.",
        "inputSchema": {
            "type": "object",
            "properties": {"item": {"type": "string", "description": "Display name or item ID (UUID) of the Fabric item."}},
            "required": ["item"],
            "additionalProperties": False,
        },
    },
    {
        "name": "fabric_api_get",
        "description": "Make an authenticated GET request to the Fabric REST API. Accepts paths like 'workspaces', 'workspaces/{id}/items', or '/v1/workspaces/{id}/items'.",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Fabric REST API path, e.g. workspaces/{id}/items"}},
            "required": ["path"],
            "additionalProperties": False,
        },
    },
]


def handle(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    request_id = message.get("id")

    if method == "initialize":
        return response(
            request_id,
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "fabric-cli-wrapper", "version": "0.2.0"},
            },
        )
    if method == "notifications/initialized":
        return None
    if method == "tools/list":
        return response(request_id, {"tools": TOOLS})
    if method == "tools/call":
        params = message.get("params", {})
        try:
            result = handle_tool_call(params.get("name", ""), params.get("arguments", {}) or {})
            return response(request_id, result)
        except Exception as exc:
            return error_response(request_id, -32000, str(exc))

    if request_id is None:
        return None
    return error_response(request_id, -32601, f"Unsupported method: {method}")


def main() -> int:
    load_env()
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            outgoing = handle(json.loads(line))
        except Exception as exc:
            outgoing = error_response(None, -32700, str(exc))
        if outgoing is not None:
            print(json.dumps(outgoing), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
