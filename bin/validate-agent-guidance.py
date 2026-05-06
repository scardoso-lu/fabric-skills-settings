#!/usr/bin/env python3
"""Check that runtime guidance references core skills and canonical docs.

This is a lightweight drift check for AGENTS.md, CLAUDE.md, README.md, and
Claude sub-agent/command files. It is intentionally local-only and does not call
Fabric, MCP, or external services.
"""

from __future__ import annotations

import argparse
from pathlib import Path

ROOT_DOCS = [Path("AGENTS.md"), Path("CLAUDE.md"), Path("README.md")]
CANONICAL_DOCS = [
    Path("docs/agent-guidance-map.md"),
    Path("docs/fabric-sandbox-smoke-test.md"),
    Path("docs/fabric-mcp-readonly-discovery.md"),
]


def validate() -> list[str]:
    errors: list[str] = []
    skill_files = sorted(Path("skills/core").glob("*/SKILL.md"))
    if not skill_files:
        errors.append("no core skill files found under skills/core")

    for doc in ROOT_DOCS:
        if not doc.exists():
            errors.append(f"missing runtime doc: {doc}")
            continue
        text = doc.read_text(encoding="utf-8")
        for skill in skill_files:
            skill_name = skill.parent.name
            if str(skill) not in text and skill_name not in text:
                errors.append(f"{doc} does not reference core skill {skill_name}")

    for doc in CANONICAL_DOCS:
        if not doc.exists():
            errors.append(f"missing canonical guidance doc: {doc}")

    for agent in ["orchestrator", "developer", "tester", "operator"]:
        path = Path(".claude/agents") / f"{agent}.md"
        if not path.exists():
            errors.append(f"missing Claude sub-agent spec: {path}")

    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quiet", action="store_true", help="Only print failures.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    errors = validate()
    if errors:
        print("FAIL: agent guidance drift check")
        for error in errors:
            print(f"  - {error}")
        return 1
    if not args.quiet:
        print("PASS: agent guidance references are aligned")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
