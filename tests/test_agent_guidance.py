"""Agent-guidance validation (formerly packaging/validators/validate-agent-guidance.py)."""

from __future__ import annotations

from pathlib import Path

from _validation.agent_guidance import collect_errors

ROOT = Path(__file__).resolve().parents[1]


def test_agent_guidance_is_valid():
    errors = collect_errors(ROOT)
    assert not errors, "agent guidance validation failed:\n- " + "\n- ".join(errors)
