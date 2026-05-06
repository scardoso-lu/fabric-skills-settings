#!/usr/bin/env python3
"""Structurally diff hard-limits and routing sections between the two runtimes.

Checks performed:
  1. All core skill files are referenced in runtime docs.
  2. All canonical guidance docs exist on disk.
  3. All Claude sub-agent spec files exist.
  4. Hard-limits sections exist on BOTH sides for every role; content matches.
  5. Routing tables have identical request-type → agent mappings with no
     mis-routes (same request type, different destination).
  6. Both routing tables have the same number of rows.

Structural diff means:
  - A Hard Limits block absent from one side is always an error (no silent skip).
  - A routing row with the same request type but a different destination is
    reported as a conflict, not just a missing row.
  - Item count mismatches are flagged even when set membership is identical.
  - --verbose shows a unified diff of the normalised item lists.

Run after any change to CLAUDE.md, AGENTS.md, or .claude/agents/*.md.
"""

from __future__ import annotations

import argparse
import difflib
import re
from pathlib import Path

ROOT_DOCS = [Path("AGENTS.md"), Path("CLAUDE.md"), Path("README.md")]
CANONICAL_DOCS = [
    Path("docs/agent-guidance-map.md"),
    Path("docs/fabric-sandbox-smoke-test.md"),
    Path("docs/fabric-mcp-readonly-discovery.md"),
]

ROLES = ["orchestrator", "developer", "tester", "operator"]

# ---------------------------------------------------------------------------
# Section extraction
# ---------------------------------------------------------------------------

def _extract_role_section(text: str, role: str) -> str:
    """Extract the text block for a named role (### heading or **bold** inline)."""
    pattern = re.compile(
        rf"(?:^###\s+{role}\b|^\*\*{role}\*\*)(.*?)(?=^###\s|\Z)",
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    m = pattern.search(text)
    return m.group(1) if m else ""


def _extract_hard_limits_block(role_section: str) -> str | None:
    """Return the raw text of the Hard Limits block, or None if absent.

    Returns None (not empty string) so callers can distinguish 'section missing'
    from 'section present but empty'.
    """
    pattern = re.compile(
        r"(?:\*\*Hard limits?\*\*[:\s]+|^#{1,3}\s+Hard Limits?\s*\n)"
        r"(.*?)"
        r"(?=\n\n\*\*|\n\n---|\n\n##|\Z)",
        re.DOTALL | re.IGNORECASE | re.MULTILINE,
    )
    m = pattern.search(role_section)
    return m.group(1) if m else None


def _parse_limit_items(block: str) -> list[str]:
    """Parse and normalise hard-limit bullet items from a raw block."""
    items = []
    for line in block.splitlines():
        s = _normalise_limit(line)
        if s:
            items.append(s)
    return items


def _normalise_limit(raw: str) -> str:
    """Strip bullet markers, normalize whitespace, lowercase, drop trailing period."""
    s = raw.strip().lstrip("-*•·").strip()
    if not s or s.startswith("|") or s.startswith("#"):
        return ""
    # Normalise internal whitespace
    s = re.sub(r"\s+", " ", s)
    # Strip trailing period so "Never write code." == "Never write code"
    s = s.rstrip(".")
    # Lowercase for case-insensitive comparison
    return s.lower()


# ---------------------------------------------------------------------------
# Routing table extraction
# ---------------------------------------------------------------------------

def _extract_routing_rows(text: str) -> list[tuple[str, str]]:
    """Return ordered (request_type, route_to) pairs from routing table blocks.

    Deduplicates on request_type (first occurrence wins) so the result is a
    stable ordered list suitable for dict-based structural comparison.
    """
    block_pattern = re.compile(
        r"(?:\*\*Routing\*\*[:\s]*\n|^#{1,3}\s+Routing.*?\n)"
        r"(.*?)"
        r"(?=\n\n\*\*|\n\n---|\n\n##|\Z)",
        re.DOTALL | re.IGNORECASE | re.MULTILINE,
    )
    rows: list[tuple[str, str]] = []
    seen: set[str] = set()
    for block_m in block_pattern.finditer(text):
        for line in block_m.group(1).splitlines():
            # Skip separator rows (|---|---| etc.) and header rows
            if re.match(r"\|\s*-+", line):
                continue
            line_lower = line.lower()
            if "request type" in line_lower or "request " in line_lower[:20]:
                continue
            row_m = re.match(r"\|\s*(.+?)\s*\|\s*(.+?)\s*\|", line)
            if row_m:
                req = row_m.group(1).strip().lower()
                route = row_m.group(2).strip().lower()
                if req and route and req not in seen:
                    rows.append((req, route))
                    seen.add(req)
    return rows


# ---------------------------------------------------------------------------
# Diff helpers
# ---------------------------------------------------------------------------

def _diff_hard_limits(
    role: str,
    a_items: list[str],
    b_items: list[str],
    a_name: str,
    b_name: str,
    verbose: bool,
) -> list[str]:
    """Structural diff of hard-limit item lists.

    Reports:
      - Items present in one side but absent from the other.
      - Count mismatches even when set membership is identical (catches duplicates).
      - Optional unified diff (--verbose).
    """
    errors: list[str] = []
    a_set = set(a_items)
    b_set = set(b_items)

    for item in sorted(a_set - b_set):
        errors.append(
            f"  [{role}] hard-limits — in {a_name} but missing from {b_name}:\n"
            f"      '{item}'"
        )
    for item in sorted(b_set - a_set):
        errors.append(
            f"  [{role}] hard-limits — in {b_name} but missing from {a_name}:\n"
            f"      '{item}'"
        )

    # Count mismatch with identical sets → likely a duplicate on one side
    if not errors and len(a_items) != len(b_items):
        errors.append(
            f"  [{role}] hard-limits — same content but different item count "
            f"({a_name}: {len(a_items)}, {b_name}: {len(b_items)}); "
            f"check for duplicate bullets"
        )

    if verbose and errors:
        diff_lines = list(
            difflib.unified_diff(
                a_items, b_items,
                fromfile=a_name, tofile=b_name,
                lineterm="",
            )
        )
        if diff_lines:
            errors.append(
                f"  [{role}] hard-limits unified diff:\n"
                + "\n".join(f"    {ln}" for ln in diff_lines)
            )

    return errors


def _diff_routing(
    a_rows: list[tuple[str, str]],
    b_rows: list[tuple[str, str]],
    a_name: str,
    b_name: str,
) -> list[str]:
    """Structural diff of routing tables.

    Three distinct error classes:
      1. Request type present in one table but absent from the other.
      2. Same request type but different routing destination (mis-route).
      3. Row count mismatch after deduplication.
    """
    errors: list[str] = []
    a_map = dict(a_rows)
    b_map = dict(b_rows)

    # 1. Request types present on only one side
    for req in sorted(set(a_map) - set(b_map)):
        errors.append(
            f"  [routing] '{req}' → '{a_map[req]}' exists in {a_name} "
            f"but is absent from {b_name}"
        )
    for req in sorted(set(b_map) - set(a_map)):
        errors.append(
            f"  [routing] '{req}' → '{b_map[req]}' exists in {b_name} "
            f"but is absent from {a_name}"
        )

    # 2. Same request type, conflicting routing destination (mis-route)
    for req in sorted(set(a_map) & set(b_map)):
        if a_map[req] != b_map[req]:
            errors.append(
                f"  [routing] MIS-ROUTE on '{req}': "
                f"{a_name} → '{a_map[req]}' vs {b_name} → '{b_map[req]}'"
            )

    # 3. Row count mismatch (catches tables that look identical but have extras)
    if len(a_rows) != len(b_rows) and not errors:
        errors.append(
            f"  [routing] row count mismatch: {a_name}={len(a_rows)}, "
            f"{b_name}={len(b_rows)} — check for duplicate or stray rows"
        )

    return errors


# ---------------------------------------------------------------------------
# Main validation
# ---------------------------------------------------------------------------

def validate(verbose: bool = False) -> list[str]:
    errors: list[str] = []
    skill_files = sorted(Path("skills").glob("fabric-*.md"))
    if not skill_files:
        errors.append("no core skill files found under skills/ (expected fabric-*.md)")

    # ── 1. Skill reference check ───────────────────────────────────────────
    for doc in ROOT_DOCS:
        if not doc.exists():
            errors.append(f"missing runtime doc: {doc}")
            continue
        text = doc.read_text(encoding="utf-8")
        for skill in skill_files:
            skill_name = skill.stem  # e.g. "fabric-ingest" from skills/fabric-ingest.md
            if str(skill) not in text and skill_name not in text:
                errors.append(f"{doc}: missing reference to core skill '{skill_name}'")

    # ── 2. Canonical doc presence ──────────────────────────────────────────
    for doc in CANONICAL_DOCS:
        if not doc.exists():
            errors.append(f"missing canonical guidance doc: {doc}")

    # ── 3. Sub-agent spec presence ─────────────────────────────────────────
    for agent in ROLES:
        path = Path(".claude/agents") / f"{agent}.md"
        if not path.exists():
            errors.append(f"missing Claude sub-agent spec: {path}")

    # ── Load runtime texts ─────────────────────────────────────────────────
    claude_path = Path("CLAUDE.md")
    agents_path = Path("AGENTS.md")
    if not (claude_path.exists() and agents_path.exists()):
        return errors

    claude_text = claude_path.read_text(encoding="utf-8")
    agents_text = agents_path.read_text(encoding="utf-8")

    # Combine CLAUDE.md with sub-agent files (routing and limits live there)
    claude_combined = claude_text
    for role in ROLES:
        sub_agent = Path(".claude/agents") / f"{role}.md"
        if sub_agent.exists():
            claude_combined += "\n\n" + sub_agent.read_text(encoding="utf-8")

    # ── 4. Routing table structural diff ──────────────────────────────────
    claude_routing = _extract_routing_rows(claude_combined)
    agents_routing = _extract_routing_rows(agents_text)

    if not claude_routing and not agents_routing:
        errors.append(
            "routing: no routing tables found in either runtime — "
            "check heading format (expected '**Routing**' or '## Routing Rules')"
        )
    else:
        if not claude_routing:
            errors.append("routing: no routing table found in CLAUDE.md + sub-agents")
        if not agents_routing:
            errors.append("routing: no routing table found in AGENTS.md")
        if claude_routing and agents_routing:
            errors.extend(
                _diff_routing(claude_routing, agents_routing, "CLAUDE+sub-agents", "AGENTS.md")
            )

    # ── 5. Per-role hard-limits structural diff ────────────────────────────
    for role in ROLES:
        sub_agent_path = Path(".claude/agents") / f"{role}.md"
        claude_role_text = (
            sub_agent_path.read_text(encoding="utf-8")
            if sub_agent_path.exists()
            else _extract_role_section(claude_text, role)
        )
        agents_section = _extract_role_section(agents_text, role)

        # Both sides absent — nothing to compare, already caught in check 3
        if not claude_role_text and not agents_section:
            continue

        # One side missing its role section
        if not claude_role_text:
            errors.append(
                f"[{role}] role section missing from CLAUDE.md / sub-agent files"
            )
            continue
        if not agents_section:
            errors.append(f"[{role}] role section missing from AGENTS.md")
            continue

        # Extract Hard Limits blocks — None means the section is absent
        claude_hl = _extract_hard_limits_block(claude_role_text)
        agents_hl = _extract_hard_limits_block(agents_section)

        if claude_hl is None and agents_hl is None:
            errors.append(
                f"[{role}] hard-limits section absent from BOTH runtimes — "
                f"add a 'Hard Limits' section to .claude/agents/{role}.md and AGENTS.md"
            )
            continue

        if claude_hl is None:
            errors.append(
                f"[{role}] hard-limits section present in AGENTS.md "
                f"but absent from .claude/agents/{role}.md"
            )
            continue

        if agents_hl is None:
            errors.append(
                f"[{role}] hard-limits section present in .claude/agents/{role}.md "
                f"but absent from AGENTS.md"
            )
            continue

        # Parse normalised items from each block
        claude_items = _parse_limit_items(claude_hl)
        agents_items = _parse_limit_items(agents_hl)

        if not claude_items:
            errors.append(
                f"[{role}] hard-limits block found in .claude/agents/{role}.md "
                f"but no bullet items parsed — check list formatting"
            )
        if not agents_items:
            errors.append(
                f"[{role}] hard-limits block found in AGENTS.md "
                f"but no bullet items parsed — check list formatting"
            )

        if claude_items and agents_items:
            errors.extend(
                _diff_hard_limits(
                    role,
                    claude_items,
                    agents_items,
                    f".claude/agents/{role}.md",
                    "AGENTS.md",
                    verbose=verbose,
                )
            )

    return errors


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--quiet", action="store_true", help="Only print failures.")
    parser.add_argument(
        "--verbose", action="store_true",
        help="Show a unified diff of diverging hard-limits sections.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    errors = validate(verbose=args.verbose)
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
