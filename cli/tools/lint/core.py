"""Shared types and runner for tool/lint/."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

SCAN_ROOTS = ("workspace", "tool", "server")
"""Default directories the lints walk. Notebook .py files under workspace/ are
the primary target; tool/ and mcp/ are included so internal code is held to
the same bar."""

SKIP_DIR_NAMES = frozenset(
    {".venv", ".git", "__pycache__", "node_modules", ".graph", "dist", ".pytest_cache"}
)


@dataclass(frozen=True)
class LintFinding:
    """One concrete violation. ``rule_id`` is the canonical anchor used in
    ``content/rules/*.md`` (e.g. ``SEC-01``, ``DE-09``). ``severity`` is
    ``"error"`` (fails pre-commit) or ``"warn"`` (reported, exit 0).
    """

    rule_id: str
    path: Path
    line: int
    msg: str
    severity: str = "error"

    def format(self, root: Path) -> str:
        try:
            rel = self.path.relative_to(root)
        except ValueError:
            rel = self.path
        return f"{self.severity.upper():5} {self.rule_id}  {rel}:{self.line}  {self.msg}"


def iter_py_files(root: Path) -> Iterable[Path]:
    """Yield every .py file under ``root`` skipping known noise directories.

    A lint that needs a narrower scope (e.g. only ``workspace/**/*.py``)
    should filter the result itself rather than reimplement the walk.
    """
    if not root.is_dir():
        return
    for path in root.rglob("*.py"):
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        yield path


def run_all(
    lints: list[tuple[str, Callable[[Path], list[LintFinding]]]],
    target_root: Path,
) -> tuple[list[LintFinding], int]:
    """Execute every registered lint against ``target_root``.

    Returns ``(findings, exit_code)``. ``exit_code`` is non-zero if any
    finding has severity == ``"error"``.
    """
    all_findings: list[LintFinding] = []
    for rule_id, fn in lints:
        try:
            all_findings.extend(fn(target_root))
        except Exception as exc:
            all_findings.append(
                LintFinding(
                    rule_id=rule_id,
                    path=target_root,
                    line=0,
                    msg=f"lint crashed: {type(exc).__name__}: {exc}",
                    severity="error",
                )
            )
    exit_code = 1 if any(f.severity == "error" for f in all_findings) else 0
    return all_findings, exit_code


def emit_report(findings: list[LintFinding], root: Path, stream=sys.stdout) -> None:
    """Print findings in a stable, grep-friendly order."""
    ordered = sorted(findings, key=lambda f: (f.severity, f.rule_id, str(f.path), f.line))
    errors = sum(1 for f in ordered if f.severity == "error")
    warns = sum(1 for f in ordered if f.severity == "warn")
    for f in ordered:
        print(f.format(root), file=stream)
    if not ordered:
        print("PASS: lint clean", file=stream)
    else:
        print(f"\n{errors} error(s), {warns} warning(s)", file=stream)
