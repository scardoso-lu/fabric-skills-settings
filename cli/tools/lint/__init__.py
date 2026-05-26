"""Deterministic lints for notebook source files.

Each lint module exposes one ``run(target_root: Path) -> list[LintFinding]``
function. ``tool/lint/__main__.py`` collects findings from every registered
lint and reports them in a stable, machine-grep-able format. Used by
``tool/pre-commit-check.{ps1,sh}`` to fail before deploy on rule violations
that would otherwise rely on the agent remembering the .md rule.

Add a new lint by:
  1. Writing a module under ``tool/lint/<id>_<short_name>.py`` that exports
     ``run(target_root)`` returning a list of :class:`LintFinding`.
  2. Registering it in ``LINTS`` below.
  3. Shrinking the corresponding rule in ``content/rules/*.md`` to a
     one-line "Enforced by: tool/lint/<id>_<short_name>.py".
"""

from __future__ import annotations

from .core import LintFinding, run_all
from .sec_no_hardcoded_secrets import run as _sec_no_hardcoded_secrets
from .de_faker_seed import run as _de_faker_seed

# Registered lints, in stable execution order.
# Each entry is (rule_id, callable).
LINTS = [
    ("SEC-01", _sec_no_hardcoded_secrets),
    ("DE-09", _de_faker_seed),
]

__all__ = ["LINTS", "LintFinding", "run_all"]
