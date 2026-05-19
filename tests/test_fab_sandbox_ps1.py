"""Regression tests for the Windows Fabric CLI sandbox wrapper."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WRAPPER_PATHS = [
    ROOT / "tool" / "setup" / "fab-sandbox.ps1",
    ROOT / "profiles" / "shared" / "project-layout" / "tool" / "setup" / "fab-sandbox.ps1",
]


def test_fab_sandbox_ps1_allows_native_stderr_without_throwing():
    """fab can write informational messages to stderr while still exiting 0."""
    for path in WRAPPER_PATHS:
        text = path.read_text(encoding="utf-8")

        assert "$savedErrorActionPreference = $ErrorActionPreference" in text
        assert '$ErrorActionPreference = "Continue"' in text
        assert "& $fab @args" in text
        assert "$exitCode = $LASTEXITCODE" in text
        assert "$ErrorActionPreference = $savedErrorActionPreference" in text
