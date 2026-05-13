#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Deploy, run, and monitor Fabric notebooks via REST API (fab api).

Replaces `fab import` and `fab job run` which require an interactive Windows
console and fail in Git Bash / sandboxed environments.

Usage:
    # Deploy only
    python bin/notebook/deploy.py deploy <notebook_name> <workspace_id>

    # Deploy + run + monitor (full smoke loop)
    python bin/notebook/deploy.py run <notebook_name> <workspace_id>

    # Monitor an existing job instance (for debugging)
    python bin/notebook/deploy.py monitor <workspace_id> <item_id> <job_instance_id>
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parent.parent.parent
FAB_SANDBOX_HOME = os.environ.get("FAB_SANDBOX_HOME", "/tmp/fabric-fab-home")
_POLL_INTERVAL = 10  # seconds between status polls


def _resolve_fab() -> str:
    import shutil
    fab = shutil.which("fab")
    if fab:
        return fab
    candidate = Path(os.environ.get("FAB_BIN", "")) if os.environ.get("FAB_BIN") else None
    if candidate and candidate.exists():
        return str(candidate)
    raise SystemExit("fab executable not found. Install with: uv tool install ms-fabric-cli")


def _load_env(root: Path) -> None:
    env_file = root / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip())


def fab_api(endpoint: str, method: str = "get", body: dict | None = None, show_headers: bool = False) -> dict:
    fab_bin = _resolve_fab()
    Path(FAB_SANDBOX_HOME).mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "HOME": FAB_SANDBOX_HOME}
    cmd = [fab_bin, "api", endpoint, "-X", method, "--output_format", "json"]
    if show_headers:
        cmd.append("--show_headers")
    if body:
        cmd += ["-i", json.dumps(body)]
    result = subprocess.run(cmd, capture_output=True, text=True, env=env)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        print(result.stdout, file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        raise SystemExit("fab api returned non-JSON output")


def _first_data_text(resp: dict) -> dict:
    data = resp.get("result", {}).get("data", [])
    return (data[0].get("text") or {}) if data else {}


def _first_data_headers(resp: dict) -> dict:
    data = resp.get("result", {}).get("data", [])
    return (data[0].get("headers") or {}) if data else {}


# ---------------------------------------------------------------------------
# Operation polling (for async item creation / definition update)
# ---------------------------------------------------------------------------

def _poll_operation(operation_id: str, timeout: int = 180) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        text = _first_data_text(fab_api(f"operations/{operation_id}"))
        status = text.get("status", "Unknown")
        if status == "Succeeded":
            return
        if status == "Failed":
            err = text.get("error", {})
            raise SystemExit(f"Operation failed — {err.get('errorCode')}: {err.get('message')}")
        print(f"  operation {operation_id[:8]}… status={status}", flush=True)
        time.sleep(_POLL_INTERVAL)
    raise SystemExit(f"Operation {operation_id} timed out after {timeout}s")


# ---------------------------------------------------------------------------
# Item / notebook helpers
# ---------------------------------------------------------------------------

def get_existing_notebook_id(workspace_id: str, display_name: str) -> str | None:
    text = _first_data_text(fab_api(f"workspaces/{workspace_id}/items"))
    for item in text.get("value", []):
        if item.get("type") == "Notebook" and item.get("displayName") == display_name:
            return item["id"]
    return None


def build_definition(notebook_dir: Path) -> dict:
    parts = []
    for filename in ("notebook-content.py", ".platform"):
        fpath = notebook_dir / filename
        if not fpath.exists():
            raise SystemExit(f"Missing {filename} in {notebook_dir}")
        payload = base64.b64encode(fpath.read_bytes()).decode()
        parts.append({"path": filename, "payload": payload, "payloadType": "InlineBase64"})
    return {"parts": parts}


def _wait_for_async(resp: dict, label: str) -> None:
    """If the response is 202, extract and poll the operation."""
    operation_id = _first_data_headers(resp).get("x-ms-operation-id")
    if operation_id:
        print(f"  async {label} — operation {operation_id[:8]}…, polling…", flush=True)
        _poll_operation(operation_id)


def deploy_notebook(workspace_id: str, notebook_name: str, notebook_dir: Path) -> str:
    """Create or update a notebook. Returns the item ID."""
    definition = build_definition(notebook_dir)
    existing_id = get_existing_notebook_id(workspace_id, notebook_name)

    if existing_id:
        print(f"-- Updating '{notebook_name}' ({existing_id})")
        resp = fab_api(
            f"workspaces/{workspace_id}/items/{existing_id}/updateDefinition",
            method="post",
            body={"definition": definition},
            show_headers=True,
        )
        if resp.get("status") != "Success":
            raise SystemExit(f"Update failed: {resp}")
        _wait_for_async(resp, "update")
        print(f"-- Updated {notebook_name}")
        return existing_id

    print(f"-- Creating '{notebook_name}'")
    resp = fab_api(
        f"workspaces/{workspace_id}/items",
        method="post",
        body={"displayName": notebook_name, "type": "Notebook", "definition": definition},
        show_headers=True,
    )
    if resp.get("status") != "Success":
        raise SystemExit(f"Create failed: {resp}")
    # 201 sync: item returned in body
    item_id = _first_data_text(resp).get("id")
    if not item_id:
        # 202 async: poll operation then resolve
        _wait_for_async(resp, "create")
        item_id = get_existing_notebook_id(workspace_id, notebook_name)
    if not item_id:
        raise SystemExit(f"Created '{notebook_name}' but could not resolve item ID")
    print(f"-- Created {notebook_name} ({item_id})")
    return item_id


# ---------------------------------------------------------------------------
# Job run + monitor
# ---------------------------------------------------------------------------

def trigger_run(workspace_id: str, item_id: str) -> str:
    """Trigger a notebook run. Returns the job instance ID."""
    resp = fab_api(
        f"workspaces/{workspace_id}/items/{item_id}/jobs/instances?jobType=RunNotebook",
        method="post",
        show_headers=True,
    )
    if resp.get("status") != "Success":
        raise SystemExit(f"Job trigger failed: {resp}")
    # Location header: …/jobs/instances/{jobInstanceId}
    location = _first_data_headers(resp).get("Location", "")
    job_instance_id = location.rstrip("/").split("/")[-1] if location else ""
    if not job_instance_id:
        raise SystemExit(f"Could not parse job instance ID from Location header: {location!r}")
    print(f"-- Run triggered — job instance {job_instance_id}", flush=True)
    return job_instance_id


def monitor_run(workspace_id: str, item_id: str, job_instance_id: str, timeout: int = 1800) -> None:
    """Poll until the job instance completes. Prints a summary."""
    endpoint = f"workspaces/{workspace_id}/items/{item_id}/jobs/instances/{job_instance_id}"
    deadline = time.time() + timeout
    while time.time() < deadline:
        text = _first_data_text(fab_api(endpoint))
        status = text.get("status", "Unknown")
        print(f"  STATUS: {status}", flush=True)
        if status in ("Completed", "Succeeded"):
            print("-- Run PASSED")
            return
        if status in ("Failed", "Cancelled", "Deduped"):
            err = text.get("failureReason") or text.get("error") or {}
            msg = err.get("message", "") if isinstance(err, dict) else str(err)
            print(f"-- Run FAILED: {msg}")
            raise SystemExit(1)
        time.sleep(_POLL_INTERVAL)
    raise SystemExit(f"Job {job_instance_id} timed out after {timeout}s")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    _load_env(SCRIPT_ROOT)

    if len(sys.argv) < 2:
        raise SystemExit(__doc__)

    command = sys.argv[1]

    if command == "deploy":
        if len(sys.argv) < 4:
            raise SystemExit("Usage: deploy.py deploy <notebook_name> <workspace_id>")
        notebook_name, workspace_id = sys.argv[2], sys.argv[3]
        notebook_dir = SCRIPT_ROOT / "fabric_notebooks" / f"{notebook_name}.Notebook"
        if not notebook_dir.is_dir():
            raise SystemExit(f"Built package not found: {notebook_dir}\nRun bin/notebook/build.py first.")
        deploy_notebook(workspace_id, notebook_name, notebook_dir)

    elif command == "run":
        if len(sys.argv) < 4:
            raise SystemExit("Usage: deploy.py run <notebook_name> <workspace_id>")
        notebook_name, workspace_id = sys.argv[2], sys.argv[3]
        notebook_dir = SCRIPT_ROOT / "fabric_notebooks" / f"{notebook_name}.Notebook"
        if not notebook_dir.is_dir():
            raise SystemExit(f"Built package not found: {notebook_dir}\nRun bin/notebook/build.py first.")
        item_id = deploy_notebook(workspace_id, notebook_name, notebook_dir)
        job_instance_id = trigger_run(workspace_id, item_id)
        monitor_run(workspace_id, item_id, job_instance_id)

    elif command == "monitor":
        if len(sys.argv) < 5:
            raise SystemExit("Usage: deploy.py monitor <workspace_id> <item_id> <job_instance_id>")
        workspace_id, item_id, job_instance_id = sys.argv[2], sys.argv[3], sys.argv[4]
        monitor_run(workspace_id, item_id, job_instance_id)

    else:
        raise SystemExit(f"Unknown command: {command!r}\nUse: deploy | run | monitor")


if __name__ == "__main__":
    main()
