"""Install-package layout validation (formerly packaging/validators/validate-install-package.py)."""

from __future__ import annotations

from pathlib import Path

from fabric_skills_settings.commands._common import apply_profile_set
from fabric_skills_settings.core.files import WriteOptions
from _validation.install_package import collect_errors

ROOT = Path(__file__).resolve().parents[1]


def test_install_package_layout_is_valid():
    errors = collect_errors(ROOT)
    assert not errors, "install package layout validation failed:\n- " + "\n- ".join(errors)


def test_profile_install_does_not_copy_runtime_tools(tmp_path):
    operations, _ = apply_profile_set(tmp_path, "claude", WriteOptions(dry_run=False))

    assert not (tmp_path / "tool").exists()
    assert not any("\\tool\\" in op or "/tool/" in op for op in operations)
