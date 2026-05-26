"""Allow `python -m fabric_skills_settings` to invoke the CLI."""

from __future__ import annotations

from fabric_skills_settings.cli import app

app(prog_name="fabric-agents")
