"""Install-package layout validation (formerly packaging/validators/validate-install-package.py)."""

from __future__ import annotations

from pathlib import Path

from _validation.install_package import collect_errors

ROOT = Path(__file__).resolve().parents[1]


def test_install_package_layout_is_valid():
    errors = collect_errors(ROOT)
    assert not errors, "install package layout validation failed:\n- " + "\n- ".join(errors)
