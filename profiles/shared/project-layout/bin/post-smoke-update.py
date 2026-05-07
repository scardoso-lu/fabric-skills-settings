#!/usr/bin/env python3
"""post-smoke-update.py — Record sandbox smoke test results in agent memory.

Automates the memory update section of docs/fabric-sandbox-smoke-test.md:
  - memory/platform.md  — sandbox item name and status
  - memory/project.md   — smoke test result with timestamp
  - memory/decisions.md — optional architecture notes

Usage:
  python3 bin/post-smoke-update.py
  python3 bin/post-smoke-update.py --notebook <name> --run-id <id> [--result pass|fail]
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MEMORY_DIR = ROOT / "memory"

PLATFORM_FILE = MEMORY_DIR / "platform.md"
PROJECT_FILE  = MEMORY_DIR / "project.md"
DECISIONS_FILE = MEMORY_DIR / "decisions.md"


def prompt(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    return value if value else default


def append_section(path: Path, heading: str, body: str) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(f"\n{heading}\n{body}\n")


def update_platform(notebook: str, result: str, ts: str) -> None:
    status = "✅ smoke-tested" if result == "pass" else "❌ smoke-test failed"
    entry = (
        f"| {notebook} | Notebook | sandbox | {status} | {ts} |"
    )
    content = PLATFORM_FILE.read_text(encoding="utf-8")
    if "| Item | Type |" not in content:
        append_section(
            PLATFORM_FILE,
            "## Sandbox Items",
            "| Item | Type | Workspace | Status | Last Updated |\n"
            "|---|---|---|---|---|\n"
            f"{entry}",
        )
    else:
        append_section(PLATFORM_FILE, "", entry)
    print(f"✓ Updated memory/platform.md")


def update_project(notebook: str, run_id: str, result: str, ts: str, notes: str) -> None:
    icon = "✅" if result == "pass" else "❌"
    lines = [
        f"### Smoke test — {notebook} — {ts}",
        f"- Result: {icon} {result.upper()}",
        f"- Run ID: `{run_id}`",
    ]
    if notes:
        lines.append(f"- Notes: {notes}")
    append_section(PROJECT_FILE, "", "\n".join(lines))
    print(f"✓ Updated memory/project.md")


def update_decisions(decision: str, ts: str) -> None:
    if not decision:
        return
    entry = [
        f"### {ts} — Smoke test observation",
        decision,
    ]
    append_section(DECISIONS_FILE, "", "\n".join(entry))
    print(f"✓ Updated memory/decisions.md")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--notebook", help="Notebook item name")
    parser.add_argument("--run-id",   help="Fabric job run ID")
    parser.add_argument("--result",   choices=["pass", "fail"], help="Smoke test result")
    args = parser.parse_args()

    # Verify memory directory exists
    if not MEMORY_DIR.exists():
        print(f"✗ Memory directory not found: {MEMORY_DIR}", file=sys.stderr)
        print("  Run ./setup.sh first to create the project structure.", file=sys.stderr)
        sys.exit(1)

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    print()
    print("── Smoke Test Memory Update ──────────────────────────")
    print("  Records results in memory/")
    print("  Never enter real credentials or Fabric IDs here.")
    print()

    notebook = args.notebook or prompt("Notebook name")
    run_id   = args.run_id   or prompt("Run ID (from fab output)")
    result   = args.result   or prompt("Result (pass/fail)", default="pass")

    if result not in ("pass", "fail"):
        print(f"✗ Result must be 'pass' or 'fail', got: {result!r}", file=sys.stderr)
        sys.exit(1)

    notes    = prompt("Run notes (optional, press Enter to skip)")
    decision = prompt("Architecture note for decisions.md (optional, press Enter to skip)")

    print()
    update_platform(notebook, result, ts)
    update_project(notebook, run_id, result, ts, notes)
    update_decisions(decision, ts)

    print()
    print("════════════════════════════════════════════")
    print("✓ Memory updated. Review the files if needed:")
    print("    memory/platform.md")
    print("    memory/project.md")
    if decision:
        print("    memory/decisions.md")
    print()


if __name__ == "__main__":
    main()
