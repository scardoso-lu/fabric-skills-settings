#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Verify staging-path consistency across notebooks in the same pipeline topic.

Parses workspace/<topic>/*.py source files and reports any staging-directory
constant that differs between notebooks within the same topic. Also checks
old-style OUTPUT_DIR / SOURCE_DIR directed pairs between download_sources.py
and bronze notebooks.

A staging-path mismatch produces a silent empty read in Fabric — no error,
just missing data. Run this before every build or deploy.

Usage (from target repo root):
    python bin/validate-pipeline-lineage.py
    python bin/validate-pipeline-lineage.py --topic lux_energy_price
"""
from __future__ import annotations

import ast
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Constants that must be identical across all notebooks in the same topic pipeline
SHARED_CONSTANT_NAMES = {"FABRIC_STAGING_DIR", "LOCAL_STAGING_DIR"}

# Old-style directed pairs: upstream constant → downstream constant
DIRECTED_PAIRS = [
    ("DEFAULT_OUTPUT_DIR_FABRIC", "DEFAULT_SOURCE_DIR_FABRIC"),
    ("DEFAULT_OUTPUT_DIR_LOCAL",  "DEFAULT_SOURCE_DIR_LOCAL"),
    ("OUTPUT_DIR",                "SOURCE_DIR"),
]
DIRECTED_NAMES = {name for pair in DIRECTED_PAIRS for name in pair}

ALL_TRACKED = SHARED_CONSTANT_NAMES | DIRECTED_NAMES


def extract_string_constants(path: Path) -> dict[str, str]:
    """Return module-level string constant assignments for tracked names."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return {}
    out: dict[str, str] = {}
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            if not (isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ALL_TRACKED:
                    out[target.id] = node.value.value
        elif isinstance(node, ast.AnnAssign):
            if not isinstance(node.target, ast.Name):
                continue
            if node.target.id not in ALL_TRACKED:
                continue
            if node.value and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                out[node.target.id] = node.value.value
    return out


def validate_topic(topic: Path, errors: list[str]) -> None:
    notebooks = sorted(topic.glob("*.py"))
    if not notebooks:
        return

    consts: dict[Path, dict[str, str]] = {nb: extract_string_constants(nb) for nb in notebooks}

    # Shared-constant check: every notebook that declares the constant must agree
    for cname in sorted(SHARED_CONSTANT_NAMES):
        values = {nb: c[cname] for nb, c in consts.items() if cname in c}
        if len(set(values.values())) > 1:
            errors.append(f"[{topic.name}] {cname} is inconsistent:")
            for nb, val in sorted(values.items(), key=lambda kv: kv[0].name):
                errors.append(f"    {nb.name}: {val!r}")

    # Directed-pair check: download_sources OUTPUT must match bronze SOURCE
    downloaders = [nb for nb in notebooks if nb.stem == "download_sources"]
    bronzes = [nb for nb in notebooks if nb.stem.startswith("bronze_") and not nb.stem.startswith("dq_")]

    for up_name, dn_name in DIRECTED_PAIRS:
        for dl in downloaders:
            up_val = consts.get(dl, {}).get(up_name)
            if up_val is None:
                continue
            for br in bronzes:
                dn_val = consts.get(br, {}).get(dn_name)
                if dn_val is None:
                    continue
                if up_val != dn_val:
                    errors.append(
                        f"[{topic.name}] pipeline path mismatch: "
                        f"{dl.name}:{up_name}={up_val!r} "
                        f"!= {br.name}:{dn_name}={dn_val!r}"
                    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--topic", help="check only this topic subdirectory")
    ap.add_argument("--workspace", default="workspace", help="workspace root relative to repo (default: workspace/)")
    args = ap.parse_args()

    workspace = ROOT / args.workspace
    if not workspace.exists():
        print(f"SKIP: {workspace} not found — no workspace/ directory to check")
        return 0

    errors: list[str] = []
    topics = (
        [workspace / args.topic]
        if args.topic
        else sorted(d for d in workspace.iterdir() if d.is_dir())
    )
    for topic in topics:
        validate_topic(topic, errors)

    if errors:
        print("FAIL: pipeline lineage check failed")
        for err in errors:
            print(f"  {err}")
        return 1

    checked = len(topics)
    print(f"PASS: pipeline staging paths are consistent ({checked} topic(s) checked)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
