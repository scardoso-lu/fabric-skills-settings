"""DE-09: Faker / Mimesis must be seeded for deterministic test data.

This is the **AST-based lint template**. New AST lints should copy this
shape:
  - subclass ``ast.NodeVisitor``
  - collect findings in a list on the visitor
  - the module-level ``run(target_root)`` parses each .py file, runs the
    visitor, and returns the collected findings.

Rule:
  Any file that imports ``faker.Faker`` or instantiates ``Faker()`` /
  ``Generic()`` (mimesis) must also call ``Faker.seed(...)``,
  ``faker.Faker.seed(...)``, ``<instance>.seed_instance(...)``, or
  ``mimesis.random.Random.seed(...)`` somewhere in the module.

  Without a seed, generated test data drifts between runs and ``Faker`` with
  seed(42) is the project convention.
"""

from __future__ import annotations

import ast
from pathlib import Path

from .core import LintFinding, SCAN_ROOTS, iter_py_files


_FAKER_IMPORTS = {"faker", "Faker"}
_FAKER_CLASS_NAMES = {"Faker", "Generic"}  # mimesis.Generic also needs a seed
_SEED_METHOD_NAMES = {"seed", "seed_instance", "seed_locale"}


class _Visitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.uses_faker = False
        self.calls_seed = False
        self.first_faker_line = 0

    # `import faker` or `import faker as f`
    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name.split(".")[0] in _FAKER_IMPORTS or alias.name == "mimesis":
                self.uses_faker = True
                if not self.first_faker_line:
                    self.first_faker_line = node.lineno
        self.generic_visit(node)

    # `from faker import Faker` / `from mimesis import Generic`
    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        mod = (node.module or "").split(".")[0]
        if mod in {"faker", "mimesis"}:
            self.uses_faker = True
            if not self.first_faker_line:
                self.first_faker_line = node.lineno
        self.generic_visit(node)

    # `Faker.seed(42)`, `faker.Faker.seed(42)`, `fake.seed_instance(42)`
    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in _SEED_METHOD_NAMES:
            self.calls_seed = True
        self.generic_visit(node)


def run(target_root: Path) -> list[LintFinding]:
    findings: list[LintFinding] = []
    for scan_root in SCAN_ROOTS:
        root = target_root / scan_root
        for py in iter_py_files(root):
            try:
                source = py.read_text(encoding="utf-8", errors="ignore")
                tree = ast.parse(source, filename=str(py))
            except (OSError, SyntaxError):
                continue
            v = _Visitor()
            v.visit(tree)
            if v.uses_faker and not v.calls_seed:
                findings.append(
                    LintFinding(
                        rule_id="DE-09",
                        path=py,
                        line=v.first_faker_line or 1,
                        msg="Faker/Mimesis imported but no seed() / seed_instance() call found — "
                            "add Faker.seed(42) for deterministic synthetic data",
                    )
                )
    return findings
