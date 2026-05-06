#!/usr/bin/env python3
"""Build simple Fabric .Notebook folders from local # %% Python sources.

This utility is intentionally minimal and sandbox-oriented. Review and adapt
Fabric metadata before using it in a real workspace.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from pathlib import Path

# Namespace UUID for deterministic logical IDs. Fixed — do not change once
# notebooks are deployed, or Fabric will treat re-imports as new items.
_LOGICAL_ID_NAMESPACE = uuid.UUID("b1f4e6d2-8c3a-4f7e-9b2d-1a5c0e8f3d6a")


NOTEBOOK_SOURCE_DIR = Path("src/notebooks")
OUTPUT_DIR = Path("fabric_notebooks")
CELL_SEP = "# CELL ********************"
META_BLOCK = """# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }"""


def split_cells(source: str) -> list[str]:
    parts = re.split(r"^# %%.*$", source, flags=re.MULTILINE)
    return [part.strip() for part in parts if part.strip()]


def render_notebook(source_path: Path) -> str:
    cells = []
    for body in split_cells(source_path.read_text(encoding="utf-8")):
        cells.append(f"{CELL_SEP}\n\n{body}\n\n{META_BLOCK}")
    return "\n\n".join(cells) + "\n"


def _deterministic_logical_id(display_name: str) -> str:
    """Derive a stable UUID from the notebook name so re-imports update rather than duplicate."""
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
    notebook_dir = OUTPUT_DIR / f"{display_name}.Notebook"
    notebook_dir.mkdir(parents=True, exist_ok=True)
    (notebook_dir / "notebook-content.py").write_text(
        render_notebook(source_path),
        encoding="utf-8",
    )
    (notebook_dir / ".platform").write_text(
        render_platform(display_name),
        encoding="utf-8",
    )
    return notebook_dir


def main() -> None:
    if not NOTEBOOK_SOURCE_DIR.exists():
        raise SystemExit("No src/notebooks/ directory found.")

    sources = sorted(NOTEBOOK_SOURCE_DIR.glob("*.py"))
    if not sources:
        raise SystemExit("No .py notebooks found under src/notebooks/.")

    for source in sources:
        print(f"wrote {build_one(source)}")


if __name__ == "__main__":
    main()

