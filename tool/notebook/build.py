#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Build simple Fabric .Notebook folders from local # %% Python sources.

Dependency declaration
---------------------
Add one or more of these sentinels near the top of a workspace source file
(order determines which is "default"):

    # FABRIC_LAKEHOUSE: DATALAKE           ← first = default_lakehouse
    # FABRIC_LAKEHOUSE: BRONZE_LAKEHOUSE   ← additional known_lakehouses
    # FABRIC_WAREHOUSE: DATA_WAREHOUSE

Each name is resolved from .env using the pattern:

    FABRIC_LAKEHOUSE_{NAME}  = <lakehouse UUID>
    FABRIC_WAREHOUSE_{NAME}  = <warehouse UUID>
    FABRIC_WORKSPACE_ID      = <workspace UUID>  (shared by all items)

NAME is the sentinel value uppercased with spaces and hyphens replaced by
underscores, e.g.  "Data Lake" → FABRIC_LAKEHOUSE_DATA_LAKE.

Backward compat: notebooks with no FABRIC_LAKEHOUSE / FABRIC_WAREHOUSE
sentinels fall back to the legacy FABRIC_LAKEHOUSE_ID / FABRIC_LAKEHOUSE_NAME /
FABRIC_WAREHOUSE_ID env vars.

Kernel selection
----------------
Add ``# FABRIC_KERNEL: python`` as the very first line of a workspace source
file to use the Fabric Python (jupyter/python3.12) kernel instead of the
default Synapse PySpark kernel.

Valid combinations (enforced by Fabric):
  PySpark kernel : 0-N lakehouses, no warehouse
  Python kernel  : 0-N lakehouses, 0-1 warehouse
"""

from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path

# ---------------------------------------------------------------------------
# Namespace UUID — fixed; changing it makes Fabric treat re-imports as new items
# ---------------------------------------------------------------------------
_LOGICAL_ID_NAMESPACE = uuid.UUID("b1f4e6d2-8c3a-4f7e-9b2d-1a5c0e8f3d6a")

_PYTHON_KERNEL_SENTINEL = "# FABRIC_KERNEL: python"

# ---------------------------------------------------------------------------
# Project root + .env loading
# ---------------------------------------------------------------------------

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


_SCRIPT_ROOT = Path(__file__).resolve().parent.parent.parent
_load_env(_SCRIPT_ROOT)

_project_root_raw = os.environ.get("FABRIC_PROJECT_ROOT")
_PROJECT_ROOT = Path(_project_root_raw).expanduser() if _project_root_raw else _SCRIPT_ROOT
_PROJECT_ROOT = _PROJECT_ROOT.resolve()
if not _PROJECT_ROOT.is_dir():
    raise SystemExit(f"Fabric project root does not exist: {_PROJECT_ROOT}")

NOTEBOOK_SOURCE_DIR = _PROJECT_ROOT / "workspace"
OUTPUT_DIR = _PROJECT_ROOT / "fabric_notebooks"
CELL_SEP = "# CELL ********************"
PARAMS_CELL_SEP = "# PARAMETERS CELL ********************"
PROLOGUE = "# Fabric notebook source"

# ---------------------------------------------------------------------------
# Env-var helpers
# ---------------------------------------------------------------------------

def _env_name(display_name: str) -> str:
    """Convert a display name to the env-var suffix: 'Data Lake' → 'DATA_LAKE'."""
    return display_name.upper().replace(" ", "_").replace("-", "_")


def _workspace_id() -> str:
    return os.environ.get("FABRIC_WORKSPACE_ID", "").strip()


def _resolve_lakehouse(display_name: str) -> dict | None:
    """Look up a lakehouse by display name. Returns {id, name, workspace_id} or None."""
    lh_id = os.environ.get(f"FABRIC_LAKEHOUSE_{_env_name(display_name)}", "").strip()
    # Backward compat: match against legacy FABRIC_LAKEHOUSE_NAME
    if not lh_id:
        if os.environ.get("FABRIC_LAKEHOUSE_NAME", "").strip().upper() == display_name.upper():
            lh_id = os.environ.get("FABRIC_LAKEHOUSE_ID", "").strip()
    if not lh_id:
        return None
    return {"id": lh_id, "name": display_name, "workspace_id": _workspace_id()}


def _resolve_warehouse(display_name: str) -> dict | None:
    """Look up a warehouse by display name. Returns {id, name} or None."""
    wh_id = os.environ.get(f"FABRIC_WAREHOUSE_{_env_name(display_name)}", "").strip()
    # Backward compat: use legacy FABRIC_WAREHOUSE_ID for any single warehouse reference
    if not wh_id:
        wh_id = os.environ.get("FABRIC_WAREHOUSE_ID", "").strip()
    if not wh_id:
        return None
    return {"id": wh_id, "name": display_name}


def _legacy_lakehouses() -> list[dict]:
    """Fallback when no FABRIC_LAKEHOUSE sentinels are present in the source."""
    lh_id = os.environ.get("FABRIC_LAKEHOUSE_ID", "").strip()
    lh_name = os.environ.get("FABRIC_LAKEHOUSE_NAME", "").strip()
    if lh_id:
        return [{"id": lh_id, "name": lh_name or lh_id, "workspace_id": _workspace_id()}]
    return []


def _legacy_warehouses() -> list[dict]:
    """Fallback when no FABRIC_WAREHOUSE sentinels are present in the source."""
    wh_id = os.environ.get("FABRIC_WAREHOUSE_ID", "").strip()
    if wh_id:
        name = os.environ.get("FABRIC_WAREHOUSE_NAME", "Warehouse").strip()
        return [{"id": wh_id, "name": name}]
    return []

# ---------------------------------------------------------------------------
# Sentinel parsing
# ---------------------------------------------------------------------------

def _parse_sentinels(source: str) -> tuple[bool, list[str], list[str]]:
    """Return (python_kernel, lakehouse_names, warehouse_names) from source sentinels."""
    python_kernel = source.lstrip().startswith(_PYTHON_KERNEL_SENTINEL)
    lakehouses = re.findall(r"^# FABRIC_LAKEHOUSE:\s*(.+?)$", source, re.MULTILINE)
    warehouses = re.findall(r"^# FABRIC_WAREHOUSE:\s*(.+?)$", source, re.MULTILINE)
    return python_kernel, [n.strip() for n in lakehouses], [n.strip() for n in warehouses]

# ---------------------------------------------------------------------------
# Metadata serialization
# ---------------------------------------------------------------------------

def _meta_block(content: dict) -> str:
    """Serialize a dict as a Fabric # META comment block (standard JSON + prefix)."""
    return (
        "# METADATA ********************\n\n"
        + "\n".join("# META " + line for line in json.dumps(content, indent=2).splitlines())
    )


def _cell_meta(python_kernel: bool) -> str:
    lang_group = "jupyter_python" if python_kernel else "synapse_pyspark"
    return _meta_block({"language": "python", "language_group": lang_group})


def _notebook_meta(
    python_kernel: bool,
    lakehouses: list[dict],   # [{id, name, workspace_id}]
    warehouses: list[dict],   # [{id, name}] — ignored for PySpark kernel
) -> str:
    """Build the notebook-level METADATA block.

    PySpark kernel: only lakehouses (warehouses silently ignored by Fabric).
    Python kernel : lakehouses + warehouses both supported.
    No deps + PySpark: returns '' (Fabric infers the kernel from the item type).
    No deps + Python : still emits kernel_info so Fabric knows the kernel.
    """
    if not python_kernel and not lakehouses:
        return ""

    kernel_info: dict = (
        {"name": "jupyter", "jupyter_kernel_name": "python3.12"}
        if python_kernel
        else {"name": "synapse_pyspark"}
    )

    deps: dict = {}

    if lakehouses:
        default = lakehouses[0]
        deps["lakehouse"] = {
            "default_lakehouse": default["id"],
            "default_lakehouse_name": default["name"],
            "default_lakehouse_workspace_id": default["workspace_id"],
            "known_lakehouses": [{"id": lh["id"]} for lh in lakehouses],
        }

    if warehouses and python_kernel:
        default = warehouses[0]
        deps["warehouse"] = {
            "default_warehouse": default["id"],
            "known_warehouses": [
                {"id": wh["id"], "type": "Datawarehouse"} for wh in warehouses
            ],
        }

    content: dict = {"kernel_info": kernel_info}
    if deps:
        content["dependencies"] = deps

    return _meta_block(content)

# ---------------------------------------------------------------------------
# Notebook rendering
# ---------------------------------------------------------------------------

def split_cells(source: str) -> list[tuple[bool, str]]:
    """Split source into (is_parameters_cell, content) tuples.

    Cells marked with # %% [parameters] become the Fabric parameters cell.
    build.py emits # PARAMETERS CELL ******************** as their separator —
    the only mechanism Fabric recognises for pipeline parameter injection.
    """
    segments = re.split(r"^(# %%[^\n]*)$", source, flags=re.MULTILINE)
    result: list[tuple[bool, str]] = []
    i = 0
    while i < len(segments):
        seg = segments[i]
        if re.match(r"# %%", seg):
            is_params = bool(re.match(r"# %%\s*\[parameters\]", seg))
            if i + 1 < len(segments):
                content = segments[i + 1].strip()
                if content:
                    result.append((is_params, content))
                i += 2
            else:
                i += 1
        else:
            i += 1
    return result


def render_notebook(source_path: Path) -> str:
    source = source_path.read_text(encoding="utf-8")
    python_kernel, lh_names, wh_names = _parse_sentinels(source)

    if lh_names or wh_names:
        # Explicit sentinels: resolve each named artifact from .env
        lakehouses = [lh for lh in (_resolve_lakehouse(n) for n in lh_names) if lh]
        warehouses = [wh for wh in (_resolve_warehouse(n) for n in wh_names) if wh]
    else:
        # No sentinels: fall back to legacy single-item env vars
        lakehouses = _legacy_lakehouses()
        warehouses = _legacy_warehouses() if python_kernel else []

    cell_meta = _cell_meta(python_kernel)
    cells = [
        f"{PARAMS_CELL_SEP if is_params else CELL_SEP}\n\n{body}\n\n{cell_meta}"
        for is_params, body in split_cells(source)
    ]
    nb_meta = _notebook_meta(python_kernel, lakehouses, warehouses)
    header = PROLOGUE + ("\n\n" + nb_meta if nb_meta else "")
    return header + "\n\n" + "\n\n".join(cells) + "\n"

# ---------------------------------------------------------------------------
# Platform file + build orchestration
# ---------------------------------------------------------------------------

def _deterministic_logical_id(display_name: str) -> str:
    return str(uuid.uuid5(_LOGICAL_ID_NAMESPACE, display_name))


def render_platform(display_name: str) -> str:
    payload = {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "Notebook", "displayName": display_name},
        "config": {"version": "2.0", "logicalId": _deterministic_logical_id(display_name)},
    }
    return json.dumps(payload, indent=2) + "\n"


def build_one(source_path: Path) -> Path:
    display_name = source_path.stem
    topic_rel = source_path.parent.relative_to(NOTEBOOK_SOURCE_DIR)
    notebook_dir = OUTPUT_DIR / topic_rel / f"{display_name}.Notebook"
    notebook_dir.mkdir(parents=True, exist_ok=True)
    (notebook_dir / "notebook-content.py").write_text(
        render_notebook(source_path), encoding="utf-8"
    )
    (notebook_dir / ".platform").write_text(
        render_platform(display_name), encoding="utf-8"
    )
    return notebook_dir


def main() -> None:
    if not NOTEBOOK_SOURCE_DIR.exists():
        raise SystemExit(f"No workspace/ directory found under project root {_PROJECT_ROOT}.")

    sources = sorted(
        p for p in NOTEBOOK_SOURCE_DIR.rglob("*.py")
        if "__pycache__" not in p.parts
        and not any(part.endswith(".Notebook") for part in p.parts)
    )
    if not sources:
        raise SystemExit(
            f"No .py notebooks found under {NOTEBOOK_SOURCE_DIR}/. "
            "Create workspace/<topic>/<name>.py first."
        )

    for source in sources:
        print(f"wrote {build_one(source)}")


if __name__ == "__main__":
    main()
