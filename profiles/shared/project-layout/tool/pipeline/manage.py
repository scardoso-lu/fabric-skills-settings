#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Create, deploy, and test a Fabric Data Pipeline that chains topic notebooks.

Auto-discovers all notebooks in the workspace matching a topic name and builds a
Data Factory pipeline in dependency order:
  download_ → bronze_ → dq_bronze_ → silver_ → dq_silver_ → gold_ → dq_gold_

Each activity depends on its predecessor with Succeeded — failures do not cascade.

Reads FABRIC_WORKSPACE_ID from .env.

Usage (from target repo root):
    # Auto-discover, create/update, run, and monitor to completion
    python tool/pipeline/manage.py test --topic lux_energy_price

    # Create or update only (no run)
    python tool/pipeline/manage.py create --topic lux_energy_price

    # Explicit ordered list (overrides auto-discover)
    python tool/pipeline/manage.py create --topic lux_energy_price \\
        --notebooks download_lux_energy_price,bronze_lux_energy_price

    # Trigger an already-deployed pipeline
    python tool/pipeline/manage.py run --pipeline pipeline_lux_energy_price

    # Check a running pipeline instance
    python tool/pipeline/manage.py status \\
        --pipeline pipeline_lux_energy_price --instance <job-instance-id>

    # List all data pipelines in the workspace
    python tool/pipeline/manage.py list

Pipeline parameters
-------------------
If workspace/<topic>/pipeline_params.json exists, its "parameters" dict is used as the
pipeline-level parameter schema (names + default values). CI/CD substitutes env-specific
values in this file before running manage.py for test/prod environments.

Use --params KEY=VALUE,... to override individual parameters at invocation time (e.g. to
supply a WAREHOUSE_HOST for a manual dev run without committing it to pipeline_params.json).

Example:
    python tool/pipeline/manage.py test --topic jaffle_shop \\
        --params WAREHOUSE_HOST=<dev-tds-endpoint>
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

SCRIPT_ROOT = Path(__file__).resolve().parents[2]
FAB_SANDBOX_HOME = os.environ.get("FAB_SANDBOX_HOME") or str(Path(tempfile.gettempdir()) / "fabric-fab-home")
_POLL_INTERVAL = 10

# Namespace UUID for deterministic logical IDs — must match build.py so IDs are consistent.
_LOGICAL_ID_NAMESPACE = uuid.UUID("b1f4e6d2-8c3a-4f7e-9b2d-1a5c0e8f3d6a")

_NOTEBOOK_ORDER: list[str] = [
    "download_",
    "bronze_",
    "dq_bronze_",
    "silver_",
    "dq_silver_",
    "gold_",
    "dq_gold_",
]


# ---------------------------------------------------------------------------
# Shared infrastructure (mirrors deploy.py patterns)
# ---------------------------------------------------------------------------

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
        env["USERPROFILE"] = sandbox
        if os.name == "nt":
            env["HOMEDRIVE"] = Path(sandbox).drive
            env["HOMEPATH"] = sandbox.removeprefix(Path(sandbox).drive)
    return env


def fab_api(
    endpoint: str,
    method: str = "get",
    body: dict | None = None,
    show_headers: bool = False,
) -> dict:
    fab_cmd, uses_wrapper = _resolve_fab_command()
    cmd = [*fab_cmd, "api", endpoint, "-X", method, "--output_format", "json"]
    if show_headers:
        cmd.append("--show_headers")
    if body is not None:
        body_str = json.dumps(body)
        if uses_wrapper:
            body_str = body_str.replace('"', '\\"')
        cmd += ["-i", body_str]
    result = subprocess.run(cmd, capture_output=True, text=True, env=_fab_env(uses_wrapper))
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


def _poll_operation(operation_id: str, timeout: int = 300) -> None:
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


def _wait_for_async(resp: dict, label: str) -> None:
    operation_id = _first_data_headers(resp).get("x-ms-operation-id")
    if operation_id:
        print(f"  async {label} — polling {operation_id[:8]}…", flush=True)
        _poll_operation(operation_id)


# ---------------------------------------------------------------------------
# Workspace item helpers
# ---------------------------------------------------------------------------

def _list_workspace_items(workspace_id: str) -> list[dict]:
    items: list[dict] = []
    continuation: str | None = None
    while True:
        endpoint = f"workspaces/{workspace_id}/items"
        if continuation:
            endpoint += f"?continuationToken={continuation}"
        text = _first_data_text(fab_api(endpoint))
        items.extend(text.get("value", []))
        continuation = text.get("continuationToken")
        if not continuation:
            break
    return items


def _find_item(workspace_id: str, display_name: str, item_type: str) -> dict | None:
    for item in _list_workspace_items(workspace_id):
        if item.get("type") == item_type and item.get("displayName") == display_name:
            return item
    return None


# ---------------------------------------------------------------------------
# Notebook discovery and ordering
# ---------------------------------------------------------------------------

def _order_weight(name: str) -> int:
    for i, prefix in enumerate(_NOTEBOOK_ORDER):
        if name.lower().startswith(prefix):
            return i
    return len(_NOTEBOOK_ORDER)


def _discover_notebooks(workspace_id: str, topic: str) -> list[dict]:
    notebooks = [
        item for item in _list_workspace_items(workspace_id)
        if item.get("type") == "Notebook"
        and topic.lower() in item.get("displayName", "").lower()
    ]
    return sorted(notebooks, key=lambda n: (_order_weight(n["displayName"]), n["displayName"]))


def _resolve_notebooks(
    workspace_id: str, topic: str, explicit: list[str] | None
) -> list[dict]:
    if explicit:
        result: list[dict] = []
        for name in explicit:
            item = _find_item(workspace_id, name, "Notebook")
            if not item:
                raise SystemExit(f"Notebook '{name}' not found in workspace {workspace_id}")
            result.append(item)
        return result

    found = _discover_notebooks(workspace_id, topic)
    if not found:
        raise SystemExit(
            f"No notebooks found for topic '{topic}' in workspace {workspace_id}.\n"
            "Verify the topic string matches your notebook naming convention,\n"
            "or use --notebooks to specify an explicit ordered list."
        )
    return found


# ---------------------------------------------------------------------------
# Pipeline definition builder
# ---------------------------------------------------------------------------

def _read_topic_params(topic: str) -> dict[str, str]:
    """Read pipeline_params.json for the topic if it exists. Returns parameter name→defaultValue map."""
    params_file = SCRIPT_ROOT / "workspace" / topic / "pipeline_params.json"
    if not params_file.exists():
        return {}
    data = json.loads(params_file.read_text(encoding="utf-8"))
    return {k: str(v) for k, v in data.get("parameters", {}).items()}


def _parse_params(raw: str | None) -> dict[str, str]:
    """Parse 'KEY=VALUE,KEY2=VALUE2' into a dict."""
    if not raw:
        return {}
    result: dict[str, str] = {}
    for item in raw.split(","):
        if "=" in item:
            k, _, v = item.partition("=")
            result[k.strip()] = v.strip()
    return result


def _build_pipeline_content(
    pipeline_name: str,
    workspace_id: str,
    notebooks: list[dict],
    params: dict[str, str] | None = None,
) -> str:
    # Embed values directly in every activity — no pipeline-level parameter indirection.
    # CI/CD substitutes values in pipeline_params.json per environment before running
    # manage.py create, so the deployed pipeline carries the correct env-specific values.
    activity_params: dict = (
        {k: {"value": v, "type": "string"} for k, v in params.items()} if params else {}
    )

    activities: list[dict] = []
    prev: str | None = None
    for nb in notebooks:
        activity_name = f"run_{nb['displayName']}"
        type_props: dict = {"notebookId": nb["id"], "workspaceId": workspace_id}
        if activity_params:
            type_props["parameters"] = activity_params
        activities.append({
            "name": activity_name,
            "type": "TridentNotebook",
            "dependsOn": (
                [{"activity": prev, "dependencyConditions": ["Succeeded"]}] if prev else []
            ),
            "policy": {
                "timeout": "0.12:00:00",
                "retry": 0,
                "retryIntervalInSeconds": 30,
                "secureOutput": False,
                "secureInput": False,
            },
            "typeProperties": type_props,
        })
        prev = activity_name

    return json.dumps({
        "name": pipeline_name,
        "objectId": "",
        "properties": {
            "activities": activities,
            "annotations": [],
        },
    }, indent=2)


def _build_platform_file(pipeline_name: str) -> str:
    logical_id = str(uuid.uuid5(_LOGICAL_ID_NAMESPACE, pipeline_name))
    return json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "DataPipeline", "displayName": pipeline_name},
        "config": {"version": "2.0", "logicalId": logical_id},
    }, indent=2)


def _build_definition(
    pipeline_name: str,
    workspace_id: str,
    notebooks: list[dict],
    params: dict[str, str] | None = None,
) -> dict:
    def _b64(text: str) -> str:
        return base64.b64encode(text.encode()).decode()

    return {
        "parts": [
            {
                "path": "pipeline-content.json",
                "payload": _b64(
                    _build_pipeline_content(pipeline_name, workspace_id, notebooks, params)
                ),
                "payloadType": "InlineBase64",
            },
            {
                "path": ".platform",
                "payload": _b64(_build_platform_file(pipeline_name)),
                "payloadType": "InlineBase64",
            },
        ]
    }


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_create(
    workspace_id: str,
    topic: str,
    explicit_notebooks: list[str] | None,
    params: dict[str, str] | None = None,
) -> str:
    """Create or update the Data Pipeline for the topic. Returns the item ID."""
    pipeline_name = f"pipeline_{topic}"
    notebooks = _resolve_notebooks(workspace_id, topic, explicit_notebooks)

    print(f"Pipeline : {pipeline_name}")
    print(f"Activities ({len(notebooks)}):")
    for i, nb in enumerate(notebooks):
        print(f"  {i + 1}. {nb['displayName']}  ({nb['id']})")
    if params:
        print(f"Parameters ({len(params)}): {', '.join(f'{k}={v!r}' for k, v in params.items())}")

    definition = _build_definition(pipeline_name, workspace_id, notebooks, params)
    existing = _find_item(workspace_id, pipeline_name, "DataPipeline")

    if existing:
        print(f"\n-- Updating '{pipeline_name}' ({existing['id']})", flush=True)
        resp = fab_api(
            f"workspaces/{workspace_id}/items/{existing['id']}/updateDefinition",
            method="post",
            body={"definition": definition},
            show_headers=True,
        )
        _wait_for_async(resp, "update")
        print(f"-- Updated  {pipeline_name}")
        return existing["id"]

    print(f"\n-- Creating '{pipeline_name}'", flush=True)
    resp = fab_api(
        f"workspaces/{workspace_id}/items",
        method="post",
        body={
            "displayName": pipeline_name,
            "type": "DataPipeline",
            "definition": definition,
        },
        show_headers=True,
    )
    _wait_for_async(resp, "create")
    item = _find_item(workspace_id, pipeline_name, "DataPipeline")
    if not item:
        raise SystemExit(f"Created '{pipeline_name}' but could not resolve its item ID")
    print(f"-- Created  {pipeline_name}  ({item['id']})")
    return item["id"]


def cmd_run(workspace_id: str, pipeline_name: str) -> tuple[str, str]:
    """Trigger a pipeline run. Returns (pipeline_item_id, job_instance_id)."""
    item = _find_item(workspace_id, pipeline_name, "DataPipeline")
    if not item:
        raise SystemExit(f"Pipeline '{pipeline_name}' not found in workspace {workspace_id}")
    pipeline_id = item["id"]

    print(f"-- Triggering '{pipeline_name}'  ({pipeline_id})…", flush=True)
    resp = fab_api(
        f"workspaces/{workspace_id}/items/{pipeline_id}/jobs/instances?jobType=Pipeline",
        method="post",
        body={},
        show_headers=True,
    )
    if resp.get("status") != "Success":
        raise SystemExit(f"Pipeline trigger failed: {resp}")
    location = _first_data_headers(resp).get("Location", "")
    job_instance_id = location.rstrip("/").split("/")[-1] if location else ""
    if not job_instance_id:
        raise SystemExit(f"Could not parse job instance ID from Location: {location!r}")
    print(f"-- Run triggered — job instance {job_instance_id}", flush=True)
    return pipeline_id, job_instance_id


def cmd_status(
    workspace_id: str, pipeline_id: str, job_instance_id: str, timeout: int = 3600
) -> str:
    """Poll until the pipeline run finishes. Returns the final STATUS string."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        text = _first_data_text(
            fab_api(
                f"workspaces/{workspace_id}/items/{pipeline_id}"
                f"/jobs/instances/{job_instance_id}"
            )
        )
        status = text.get("status", "Unknown")
        if status in ("Completed", "Failed", "Cancelled", "Deduped"):
            failure = text.get("failureReason") or {}
            reason = failure.get("message", "")
            suffix = f"  — {reason}" if reason else ""
            print(f"STATUS: {status}{suffix}")
            return status
        print(f"  STATUS: {status} — polling…", flush=True)
        time.sleep(_POLL_INTERVAL)
    raise SystemExit(f"Pipeline run timed out after {timeout}s")


def cmd_list(workspace_id: str) -> None:
    items = [
        i for i in _list_workspace_items(workspace_id)
        if i.get("type") == "DataPipeline"
    ]
    if not items:
        print("No data pipelines found.")
        return
    print(f"Data pipelines in workspace {workspace_id}:")
    for item in sorted(items, key=lambda i: i.get("displayName", "")):
        print(f"  {item.get('displayName', ''):50}  {item['id']}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--workspace", help="Workspace ID (overrides FABRIC_WORKSPACE_ID in .env)")
    sub = ap.add_subparsers(dest="command", required=True)

    p_create = sub.add_parser("create", help="Create or update a pipeline for a topic")
    p_create.add_argument("--topic", required=True, help="Topic name (e.g. lux_energy_price)")
    p_create.add_argument(
        "--notebooks",
        help="Comma-separated ordered notebook display names (overrides auto-discover)",
    )
    p_create.add_argument(
        "--params",
        help="Pipeline parameters as KEY=VALUE pairs (comma-separated). "
             "Merged with workspace/<topic>/pipeline_params.json; CLI values take precedence.",
    )

    p_run = sub.add_parser("run", help="Trigger a pipeline run")
    p_run.add_argument(
        "--pipeline", required=True, help="Pipeline display name (e.g. pipeline_lux_energy_price)"
    )

    p_status = sub.add_parser("status", help="Poll an existing pipeline run to completion")
    p_status.add_argument("--pipeline", required=True, help="Pipeline display name")
    p_status.add_argument("--instance", required=True, help="Job instance ID")
    p_status.add_argument("--timeout", type=int, default=3600, help="Timeout in seconds (default 3600)")

    p_test = sub.add_parser(
        "test", help="Create (if needed), run, and monitor a pipeline to completion"
    )
    p_test.add_argument("--topic", required=True, help="Topic name")
    p_test.add_argument(
        "--notebooks",
        help="Comma-separated ordered notebook display names (overrides auto-discover)",
    )
    p_test.add_argument(
        "--params",
        help="Pipeline parameters as KEY=VALUE pairs (comma-separated). "
             "Merged with workspace/<topic>/pipeline_params.json; CLI values take precedence.",
    )
    p_test.add_argument("--timeout", type=int, default=3600, help="Timeout in seconds (default 3600)")

    sub.add_parser("list", help="List all data pipelines in the workspace")

    args = ap.parse_args()
    _load_env(SCRIPT_ROOT)

    workspace_id = (args.workspace or os.environ.get("FABRIC_WORKSPACE_ID", "")).strip()
    if not workspace_id:
        raise SystemExit("FABRIC_WORKSPACE_ID is not set. Add it to .env or pass --workspace.")

    if args.command == "list":
        cmd_list(workspace_id)

    elif args.command == "create":
        explicit = [n.strip() for n in args.notebooks.split(",")] if args.notebooks else None
        params = {**_read_topic_params(args.topic), **_parse_params(getattr(args, "params", None))}
        cmd_create(workspace_id, args.topic, explicit, params or None)

    elif args.command == "run":
        pipeline_id, job_id = cmd_run(workspace_id, args.pipeline)
        print(
            f"\nMonitor with:\n"
            f"  python tool/pipeline/manage.py status"
            f" --pipeline {args.pipeline} --instance {job_id}"
        )

    elif args.command == "status":
        item = _find_item(workspace_id, args.pipeline, "DataPipeline")
        if not item:
            raise SystemExit(f"Pipeline '{args.pipeline}' not found")
        final = cmd_status(workspace_id, item["id"], args.instance, timeout=args.timeout)
        if final != "Completed":
            return 1

    elif args.command == "test":
        explicit = [n.strip() for n in args.notebooks.split(",")] if args.notebooks else None
        params = {**_read_topic_params(args.topic), **_parse_params(getattr(args, "params", None))}
        pipeline_id = cmd_create(workspace_id, args.topic, explicit, params or None)
        pipeline_name = f"pipeline_{args.topic}"
        _, job_id = cmd_run(workspace_id, pipeline_name)
        final = cmd_status(workspace_id, pipeline_id, job_id, timeout=args.timeout)
        if final != "Completed":
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
