#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""Validate Fabric Codex source-contract YAML shape without external dependencies.

This validator intentionally checks the subset used by this wrapper's contract
template. It is local-safe: it does not read .env, data files, or Fabric.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Iterable

REQUIRED_SECTIONS = ("source", "input", "sensitive_fields", "output", "validation_rules", "access")
SOURCE_REQUIRED_KEYS = ("name", "system", "sandbox_path", "cadence")
OUTPUT_REQUIRED_KEYS = ("bronze_table", "silver_table")
ACCESS_REQUIRED_KEYS = ("owners", "consumers", "sensitivity")


def strip_comment(line: str) -> str:
    """Remove comments outside simple quoted strings."""
    in_single = False
    in_double = False
    for index, char in enumerate(line):
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        elif char == "#" and not in_single and not in_double:
            return line[:index].rstrip()
    return line.rstrip()


def cleaned_lines(path: Path) -> list[str]:
    return [line for raw in path.read_text(encoding="utf-8").splitlines() if (line := strip_comment(raw)).strip()]


def top_sections(lines: Iterable[str]) -> set[str]:
    sections: set[str] = set()
    for line in lines:
        if not line.startswith(" "):
            match = re.match(r"^([^:]+):", line)
            if match:
                sections.add(match.group(1).strip())
    return sections


def section_lines(lines: list[str], section: str) -> list[str]:
    start = None
    for index, line in enumerate(lines):
        if line == f"{section}:" or line.startswith(f"{section}: "):
            start = index + 1
            break
    if start is None:
        return []
    end = len(lines)
    for index in range(start, len(lines)):
        if lines[index] and not lines[index].startswith(" "):
            end = index
            break
    return lines[start:end]


def scalar_value(lines: list[str], section: str, key: str) -> str | None:
    pattern = re.compile(rf"^  {re.escape(key)}:\s*(.*)$")
    for line in section_lines(lines, section):
        match = pattern.match(line)
        if match:
            return match.group(1).strip().strip('"\'')
    return None


def list_value(lines: list[str], section: str, key: str) -> list[str]:
    value = scalar_value(lines, section, key)
    if value is None:
        return []
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [item.strip().strip('"\'') for item in inner.split(",")]
    return []


def subsection_lines(section: list[str], key: str) -> list[str]:
    start = None
    needle = f"  {key}:"
    for index, line in enumerate(section):
        if line == needle or line.startswith(f"{needle} "):
            start = index + 1
            break
    if start is None:
        return []
    end = len(section)
    for index in range(start, len(section)):
        if section[index].startswith("  ") and not section[index].startswith("    "):
            end = index
            break
    return section[start:end]


def named_items(block: list[str]) -> list[str]:
    names: list[str] = []
    for line in block:
        match = re.match(r"^    - name:\s*(.*)$", line)
        if match:
            value = match.group(1).strip().strip('"\'')
            if value:
                names.append(value)
    return names


def rule_fields(block: list[str]) -> list[str]:
    fields: list[str] = []
    for line in block:
        match = re.match(r"^  - field:\s*(.*)$", line)
        if match:
            value = match.group(1).strip().strip('"\'')
            fields.extend(part.strip() for part in value.split(",") if part.strip())
    return fields


def non_placeholder(value: str | None, allow_placeholders: bool) -> bool:
    if value is None:
        return False
    if allow_placeholders:
        return True
    stripped = value.strip()
    return bool(stripped and stripped not in {'""', "''", "[]"})


def validate(path: Path, allow_placeholders: bool) -> list[str]:
    lines = cleaned_lines(path)
    errors: list[str] = []
    sections = top_sections(lines)

    for section in REQUIRED_SECTIONS:
        if section not in sections:
            errors.append(f"missing top-level section: {section}")

    for key in SOURCE_REQUIRED_KEYS:
        if not non_placeholder(scalar_value(lines, "source", key), allow_placeholders):
            errors.append(f"source.{key} is required")

    schema_block = subsection_lines(section_lines(lines, "input"), "schema")
    schema_names = named_items(schema_block)
    if not schema_names and not (allow_placeholders and any("- name:" in line for line in schema_block)):
        errors.append("input.schema must declare at least one column")

    primary_keys = list_value(lines, "input", "primary_keys")
    if not allow_placeholders and not primary_keys:
        errors.append("input.primary_keys must list at least one key")
    for key in primary_keys:
        if not allow_placeholders and key not in schema_names:
            errors.append(f"primary key is not declared in input.schema: {key}")

    sensitive_names = named_items(section_lines(lines, "sensitive_fields"))
    for name in sensitive_names:
        if not allow_placeholders and name not in schema_names:
            errors.append(f"sensitive field is not declared in input.schema: {name}")

    for key in OUTPUT_REQUIRED_KEYS:
        if not non_placeholder(scalar_value(lines, "output", key), allow_placeholders):
            errors.append(f"output.{key} is required")

    fields = rule_fields(section_lines(lines, "validation_rules"))
    if not allow_placeholders and not fields:
        errors.append("validation_rules must declare at least one field rule")
    for field in fields:
        if not allow_placeholders and field and field not in schema_names and not field.startswith("_"):
            errors.append(f"validation rule field is not declared in input.schema: {field}")

    for key in ACCESS_REQUIRED_KEYS:
        if not non_placeholder(scalar_value(lines, "access", key), allow_placeholders):
            errors.append(f"access.{key} is required")

    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contracts", nargs="+", type=Path, help="Source contract YAML files to validate.")
    parser.add_argument(
        "--allow-placeholders",
        action="store_true",
        help="Allow blank/template placeholder values while still checking contract shape.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    failures = 0
    for contract in args.contracts:
        errors = validate(contract, args.allow_placeholders)
        if errors:
            failures += 1
            print(f"FAIL: {contract}")
            for error in errors:
                print(f"  - {error}")
        else:
            print(f"PASS: {contract}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
