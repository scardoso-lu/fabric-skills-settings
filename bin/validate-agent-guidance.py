#!/usr/bin/env python3
"""Check that runtime guidance references core skills and canonical docs.

Also structurally diffs the hard-limits and routing sections between
CLAUDE.md and AGENTS.md so semantic drift is caught before it silently
diverges across the two runtimes.

This is intentionally local-only and does not call Fabric, MCP, or external
services.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT_DOCS = [Path("AGENTS.md"), Path("CLAUDE.md"), Path("README.md")]
CANONICAL_DOCS = [
    Path("docs/agent-guidance-map.md"),
    Path("docs/fabric-sandbox-smoke-test.md"),
    Path("docs/fabric-mcp-readonly-discovery.md"),
]

ROLES = ["orchestrator", "developer", "tester", "operator"]


def _extract_role_section(text: str, role: str) -> str:
    """Extract the text block for a named role from a runtime doc."""
    # Match from ### role or **role** heading until the next ### or ---
    pattern = re.compile(
        rf"(?:^###\s+{role}\b|^\*\*{role}\*\*)(.*?)(?=^###\s|\Z)",
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    m = pattern.search(text)
    return m.group(1) if m else ""


def _extract_hard_limits(role_section: str) -> frozenset[str]:
    """Return normalised hard-limit bullet items from a role section.

    Handles both inline (**Hard limits**: ...) and heading (## Hard Limits) formats.
    """
    # Match either **Hard limits**: block OR ## Hard Limits heading
    hl_pattern = re.compile(
        r"(?:\*\*Hard limits?\*\*[:\s]+|^#{1,3}\s+Hard Limits?\s*\n)(.*?)(?=\n\n\*\*|\n\n---|\n\n##|\Z)",
        re.DOTALL | re.IGNORECASE | re.MULTILINE,
    )
    items: set[str] = set()
    for m in hl_pattern.finditer(role_section):
        for line in m.group(1).splitlines():
            stripped = line.strip().lstrip("-*•").strip()
            if stripped and not stripped.startswith("|") and not stripped.startswith("#"):
                items.add(stripped.lower())
    return frozenset(items)


def _extract_routing_table(text: str) -> frozenset[tuple[str, str]]:
    """Extract (request_pattern, route_to) from routing table blocks.

    Handles both **Routing**: (AGENTS.md inline) and ## Routing Rules (sub-agent) formats.
    """
    routing_block_pattern = re.compile(
        r"(?:\*\*Routing\*\*[:\s]*\n|^#{1,3}\s+Routing.*?\n)(.*?)(?=\n\n\*\*|\n\n---|\n\n##|\Z)",
        re.DOTALL | re.IGNORECASE | re.MULTILINE,
    )
    rows: set[tuple[str, str]] = set()
    for block_m in routing_block_pattern.finditer(text):
        block = block_m.group(1)
        for line in block.splitlines():
            row_m = re.match(r"\|\s*(?!Request Type|Request|---|–)(.+?)\s*\|\s*(.+?)\s*\|", line)
            if row_m:
                req = row_m.group(1).strip().lower()
                route = row_m.group(2).strip().lower()
                if req and route:
                    rows.add((req, route))
    return frozenset(rows)


def _diff_sets(label: str, a: frozenset, b: frozenset, a_name: str, b_name: str) -> list[str]:
    errors: list[str] = []
    for item in sorted(a - b):
        errors.append(f"{label}: '{item}' found in {a_name} but not {b_name}")
    for item in sorted(b - a):
        errors.append(f"{label}: '{item}' found in {b_name} but not {a_name}")
    return errors


def validate() -> list[str]:
    errors: list[str] = []
    skill_files = sorted(Path("skills/core").glob("*/SKILL.md"))
    if not skill_files:
        errors.append("no core skill files found under skills/core")

    # ── Skill reference check ─────────────────────────────────────────────
    for doc in ROOT_DOCS:
        if not doc.exists():
            errors.append(f"missing runtime doc: {doc}")
            continue
        text = doc.read_text(encoding="utf-8")
        for skill in skill_files:
            skill_name = skill.parent.name
            if str(skill) not in text and skill_name not in text:
                errors.append(f"{doc} does not reference core skill {skill_name}")

    # ── Canonical doc presence ─────────────────────────────────────────────
    for doc in CANONICAL_DOCS:
        if not doc.exists():
            errors.append(f"missing canonical guidance doc: {doc}")

    # ── Sub-agent spec presence ────────────────────────────────────────────
    for agent in ROLES:
        path = Path(".claude/agents") / f"{agent}.md"
        if not path.exists():
            errors.append(f"missing Claude sub-agent spec: {path}")

    # ── Structural diff: Claude runtime vs AGENTS.md ──────────────────────
    # CLAUDE.md delegates role details to .claude/agents/*.md sub-agent files.
    # Build a combined text that includes both for comparison with AGENTS.md.
    claude_path = Path("CLAUDE.md")
    agents_path = Path("AGENTS.md")

    if not (claude_path.exists() and agents_path.exists()):
        return errors

    claude_text = claude_path.read_text(encoding="utf-8")
    agents_text = agents_path.read_text(encoding="utf-8")

    # Combine CLAUDE.md with all sub-agent files so routing/limits from sub-agents are included
    claude_combined = claude_text
    for role in ROLES:
        sub_agent = Path(".claude/agents") / f"{role}.md"
        if sub_agent.exists():
            claude_combined += "\n\n" + sub_agent.read_text(encoding="utf-8")

    # Compare orchestrator routing tables (sub-agent file has the routing table for Claude)
    claude_routing = _extract_routing_table(claude_combined)
    agents_routing = _extract_routing_table(agents_text)
    errors.extend(
        _diff_sets("orchestrator routing drift", claude_routing, agents_routing, "CLAUDE.md+sub-agents", "AGENTS.md")
    )

    # Compare per-role hard limits
    for role in ROLES:
        # For Claude: check sub-agent file first, fall back to main CLAUDE.md section
        sub_agent = Path(".claude/agents") / f"{role}.md"
        claude_role_text = sub_agent.read_text(encoding="utf-8") if sub_agent.exists() else ""
        if not claude_role_text:
            claude_role_text = _extract_role_section(claude_text, role)

        agents_section = _extract_role_section(agents_text, role)

        # Only compare if both sides have a section with content
        if not claude_role_text or not agents_section:
            continue

        claude_limits = _extract_hard_limits(claude_role_text)
        agents_limits = _extract_hard_limits(agents_section)
        errors.extend(
            _diff_sets(
                f"{role} hard-limits drift",
                claude_limits,
                agents_limits,
                f".claude/agents/{role}.md",
                "AGENTS.md",
            )
        )

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
