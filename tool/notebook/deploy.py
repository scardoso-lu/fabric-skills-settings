#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Deploy, run, and monitor Fabric notebooks via REST API (fab api).

Replaces `fab import` and `fab job run` which require an interactive Windows
console and fail in Git Bash / sandboxed environments.

Usage:
    # Deploy only (build artifact → Fabric, no run)
    python tool/notebook/deploy.py deploy <notebook_name> <workspace_id>

    # Execute already-deployed notebook (trigger + monitor, no build/deploy)
    python tool/notebook/deploy.py exec <notebook_name> <workspace_id>

    # Deploy + run + monitor + fetch (one-shot full cycle for initial development)
    python tool/notebook/deploy.py run <notebook_name> <workspace_id>

    # Fetch notebook definition from Fabric → workspace/<topic>/<name>.Notebook/ (git-tracked)
    python tool/notebook/deploy.py fetch <notebook_name> <workspace_id>

    # Monitor an existing job instance (for debugging)
    python tool/notebook/deploy.py monitor <workspace_id> <item_id> <job_instance_id>
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parent.parent.parent
FAB_SANDBOX_HOME = os.environ.get("FAB_SANDBOX_HOME") or str(Path(tempfile.gettempdir()) / "fabric-fab-home")
_POLL_INTERVAL = 10  # seconds between status polls


def _user_home() -> Path:
    if os.name == "nt":
        home = Path.home()
    else:
        import pwd
        home = Path(pwd.getpwuid(os.getuid()).pw_dir)
    if not home.exists():
        raise SystemExit(f"Could not resolve current user's home directory: {home}")
    return home


def _resolve_fab_command() -> tuple[list[str], bool]:
    """Return (command_prefix, uses_wrapper). Prefers fab-sandbox.ps1 on Windows."""
    wrapper = SCRIPT_ROOT / "tool" / "setup" / "fab-sandbox.ps1"
    if os.name == "nt" and wrapper.exists():
        powershell = os.environ.get("POWERSHELL_BIN") or "powershell.exe"
        return [powershell, "-ExecutionPolicy", "Bypass", "-File", str(wrapper)], True
    candidate = _user_home() / ".local" / "bin" / "fab"
    if candidate.exists():
        return [str(candidate)], False
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
        val = val.split("#")[0].strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), val)


def fab_api(endpoint: str, method: str = "get", body: dict | None = None, show_headers: bool = False) -> dict:
    fab_cmd, uses_wrapper = _resolve_fab_command()
    sandbox_home = Path(FAB_SANDBOX_HOME).resolve()
    sandbox_home.mkdir(parents=True, exist_ok=True)
    env = {**os.environ}
    if uses_wrapper:
        # fab-sandbox.ps1 handles credential isolation itself — don't override HOME
        env.pop("HOME", None)
    else:
        env["HOME"] = str(sandbox_home)
        env["USERPROFILE"] = str(sandbox_home)
        if os.name == "nt":
            env["HOMEDRIVE"] = sandbox_home.drive
            env["HOMEPATH"] = str(sandbox_home).removeprefix(sandbox_home.drive)
    cmd = [*fab_cmd, "api", endpoint, "-X", method, "--output_format", "json"]
    if show_headers:
        cmd.append("--show_headers")
    if body:
        body_str = json.dumps(body)
        if uses_wrapper:
            # PS5.1 strips one level of quote escaping when splatting @args to a native exe
            body_str = body_str.replace('"', '\\"')
        cmd += ["-i", body_str]
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

def _find_notebook_dir(notebook_name: str) -> Path:
    """Find the built .Notebook directory under fabric_notebooks/ (build intermediates)."""
    matches = sorted((SCRIPT_ROOT / "fabric_notebooks").glob(f"**/{notebook_name}.Notebook"))
    if not matches:
        raise SystemExit(
            f"Built package not found: {notebook_name}.Notebook under fabric_notebooks/\n"
            "Run bin/notebook/build.py first."
        )
    return matches[0]


def _topic_from_notebook_dir(notebook_dir: Path) -> str | None:
    """Return the topic subfolder name if the notebook is under a topic dir, else None."""
    rel = notebook_dir.relative_to(SCRIPT_ROOT / "fabric_notebooks")
    return rel.parts[0] if len(rel.parts) > 1 else None


def _workspace_notebook_dir(notebook_name: str) -> Path:
    """Derive the workspace .Notebook path, falling back to existing bundle location."""
    # Prefer .py (present during authoring); fall back to existing .Notebook/
    # (present after .py is deleted on first successful fetch).
    for pattern in (f"**/{notebook_name}.py", f"**/{notebook_name}.Notebook"):
        matches = sorted((SCRIPT_ROOT / "workspace").glob(pattern))
        if matches:
            return matches[0].parent / f"{notebook_name}.Notebook"
    return SCRIPT_ROOT / "workspace" / f"{notebook_name}.Notebook"


def get_existing_notebook_id(workspace_id: str, display_name: str) -> str | None:
    text = _first_data_text(fab_api(f"workspaces/{workspace_id}/items"))
    for item in text.get("value", []):
        if item.get("type") == "Notebook" and item.get("displayName") == display_name:
            return item["id"]
    return None


def get_or_create_folder(workspace_id: str, folder_name: str) -> str:
    """Return the Fabric workspace folder ID for folder_name, creating it if needed."""
    text = _first_data_text(fab_api(f"workspaces/{workspace_id}/folders"))
    for folder in text.get("value", []):
        if folder.get("displayName") == folder_name:
            return folder["id"]
    print(f"-- Creating workspace folder '{folder_name}'", flush=True)
    resp = fab_api(
        f"workspaces/{workspace_id}/folders",
        method="post",
        body={"displayName": folder_name},
    )
    folder_id = _first_data_text(resp).get("id")
    if not folder_id:
        raise SystemExit(f"Folder creation failed: {resp}")
    return folder_id


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


def deploy_notebook(workspace_id: str, notebook_name: str, notebook_dir: Path, folder_id: str | None = None) -> str:
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

    print(f"-- Creating '{notebook_name}'" + (f" in folder '{folder_id}'" if folder_id else ""))
    body: dict = {"displayName": notebook_name, "type": "Notebook", "definition": definition}
    if folder_id:
        body["folderId"] = folder_id
    resp = fab_api(
        f"workspaces/{workspace_id}/items",
        method="post",
        body=body,
        show_headers=True,
    )
    if resp.get("status") != "Success":
        raise SystemExit(f"Create failed: {resp}")
    item_id = _first_data_text(resp).get("id")
    if not item_id:
        _wait_for_async(resp, "create")
        item_id = get_existing_notebook_id(workspace_id, notebook_name)
    if not item_id:
        raise SystemExit(f"Created '{notebook_name}' but could not resolve item ID")
    print(f"-- Created {notebook_name} ({item_id})")
    return item_id


# ---------------------------------------------------------------------------
# Fetch notebook definition from Fabric
# ---------------------------------------------------------------------------

def fetch_definition(workspace_id: str, item_id: str) -> list[dict]:
    """Return definition parts list from getDefinition (sync or async)."""
    resp = fab_api(
        f"workspaces/{workspace_id}/items/{item_id}/getDefinition",
        method="post",
        show_headers=True,
    )
    text = _first_data_text(resp)
    if "definition" in text:
        return text["definition"].get("parts", [])
    # 202 async: poll then fetch result
    operation_id = _first_data_headers(resp).get("x-ms-operation-id")
    if not operation_id:
        raise SystemExit(f"getDefinition returned no definition and no operation ID: {resp}")
    _poll_operation(operation_id)
    result_text = _first_data_text(fab_api(f"operations/{operation_id}/result"))
    return result_text.get("definition", {}).get("parts", [])


def fetch_notebook(workspace_id: str, notebook_name: str) -> None:
    """Fetch notebook definition from Fabric → workspace/<topic>/<name>.Notebook/ (git-tracked)."""
    item_id = get_existing_notebook_id(workspace_id, notebook_name)
    if not item_id:
        raise SystemExit(f"Notebook '{notebook_name}' not found in workspace {workspace_id}")
    print(f"-- Fetching '{notebook_name}' from Fabric…", flush=True)
    parts = fetch_definition(workspace_id, item_id)
    notebook_dir = _workspace_notebook_dir(notebook_name)
    notebook_dir.mkdir(parents=True, exist_ok=True)
    for part in parts:
        path = part.get("path", "")
        payload = part.get("payload", "")
        if not path or not payload:
            continue
        dest = notebook_dir / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(base64.b64decode(payload))
    print(f"-- Fetched {len(parts)} part(s) to {notebook_dir}")


# ---------------------------------------------------------------------------
# Job run + monitor
# ---------------------------------------------------------------------------

def trigger_run(workspace_id: str, item_id: str) -> str:
    """Trigger a notebook run. Returns the job instance ID."""
    resp = fab_api(
        f"workspaces/{workspace_id}/items/{item_id}/jobs/instances?jobType=RunNotebook",
        method="post",
        body={
            "executionData": {
                "parameters": {
                    "_inlineInstallationEnabled": {"value": True, "type": "bool"}
                }
            }
        },
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
        notebook_dir = _find_notebook_dir(notebook_name)
        topic = _topic_from_notebook_dir(notebook_dir)
        folder_id = get_or_create_folder(workspace_id, topic) if topic else None
        deploy_notebook(workspace_id, notebook_name, notebook_dir, folder_id=folder_id)

    elif command == "run":
        if len(sys.argv) < 4:
            raise SystemExit("Usage: deploy.py run <notebook_name> <workspace_id>")
        notebook_name, workspace_id = sys.argv[2], sys.argv[3]
        notebook_dir = _find_notebook_dir(notebook_name)
        topic = _topic_from_notebook_dir(notebook_dir)
        folder_id = get_or_create_folder(workspace_id, topic) if topic else None
        item_id = deploy_notebook(workspace_id, notebook_name, notebook_dir, folder_id=folder_id)
        job_instance_id = trigger_run(workspace_id, item_id)
        monitor_run(workspace_id, item_id, job_instance_id)
        fetch_notebook(workspace_id, notebook_name)

    elif command == "exec":
        if len(sys.argv) < 4:
            raise SystemExit("Usage: deploy.py exec <notebook_name> <workspace_id>")
        notebook_name, workspace_id = sys.argv[2], sys.argv[3]
        item_id = get_existing_notebook_id(workspace_id, notebook_name)
        if not item_id:
            raise SystemExit(
                f"Notebook '{notebook_name}' not found in workspace {workspace_id}.\n"
                "Deploy it first: python tool/notebook/deploy.py deploy <name> <workspace_id>"
            )
        job_instance_id = trigger_run(workspace_id, item_id)
        monitor_run(workspace_id, item_id, job_instance_id)

    elif command == "fetch":
        if len(sys.argv) < 4:
            raise SystemExit("Usage: deploy.py fetch <notebook_name> <workspace_id>")
        notebook_name, workspace_id = sys.argv[2], sys.argv[3]
        fetch_notebook(workspace_id, notebook_name)

    elif command == "monitor":
        if len(sys.argv) < 5:
            raise SystemExit("Usage: deploy.py monitor <workspace_id> <item_id> <job_instance_id>")
        workspace_id, item_id, job_instance_id = sys.argv[2], sys.argv[3], sys.argv[4]
        monitor_run(workspace_id, item_id, job_instance_id)

    else:
        raise SystemExit(f"Unknown command: {command!r}\nUse: deploy | exec | run | fetch | monitor")


if __name__ == "__main__":
    main()
