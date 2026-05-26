"""Importable validation logic for the source package.

These modules hold the repo-invariant checks that used to live as standalone
scripts under packaging/validators/. They are imported by the pytest modules
tests/test_install_package.py and tests/test_agent_guidance.py (and reused by
tests/test_validator_profile_minimal.py against synthetic fixtures).

Each module exposes `collect_errors(root: Path) -> list[str]` — an empty list
means the tree at `root` is valid.
"""
