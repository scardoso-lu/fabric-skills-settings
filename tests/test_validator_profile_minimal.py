"""Regression coverage for the hard-minimal profile contract in agent_guidance.

The contract enforces:
- profile <= 50 lines
- must reference graph_get_entry
- must contain the anti-drift anchor sentence
- must NOT contain operational section names (anti-bypass)

These build a synthetic source repo under tmp_path and call the importable
validator directly (no subprocess). A baseline repo satisfies every unrelated
check so only the profile defect under test surfaces.
"""
from __future__ import annotations

from pathlib import Path

from _validation.agent_guidance import collect_errors


def _make_baseline_source_repo(root: Path) -> None:
    """Minimum tree so the validator only fails on the profile under test."""
    (root / "README.md").write_text("fabric-agents profiles/codex profiles/claude\n")
    (root / "AGENTS.md").write_text("fabric-agents profiles/codex profiles/claude\n")
    (root / "CLAUDE.md").write_text("fabric-agents profiles/codex profiles/claude\n")

    for skill in [
        "rtk", "fabric-ingest", "fabric-transform", "fabric-model", "fabric-validate",
        "fabric-notebook-loop", "fabric-ops", "fabric-pipeline", "semantic-model",
        "mock-data", "prd", "grill-me", "git-commit", "caveman",
    ]:
        (root / "server" / "skills" / skill).mkdir(parents=True, exist_ok=True)
        (root / "server" / "skills" / skill / "SKILL.md").write_text(f"# {skill}\n")

    (root / "cli" / "profiles" / "claude" / "agents").mkdir(parents=True, exist_ok=True)
    (root / "cli" / "profiles" / "codex" / "agents").mkdir(parents=True, exist_ok=True)
    for agent in ["orchestrator", "developer", "tester", "operator"]:
        (root / "cli" / "profiles" / "claude" / "agents" / f"{agent}.md").write_text(
            f"# {agent}\nfabric-transform fabric-model fabric-validate tester\n"
        )
        (root / "cli" / "profiles" / "codex" / "agents" / f"{agent}.toml").write_text(
            f"name = '{agent}'\n# fabric-transform fabric-model fabric-validate tester\n"
        )

    (root / "cli" / "profiles" / "codex" / "config.toml").write_text("")
    (root / "cli" / "profiles" / "claude" / "settings.local.json").write_text("{}")
    content_rules = root / "server" / "content" / "rules"
    content_rules.mkdir(parents=True, exist_ok=True)
    (content_rules / "data-engineering.md").write_text("# DE\nfabric-transform fabric-validate\n")
    (content_rules / "fabric-platform.md").write_text("# FP\nfabric-model\n")
    (content_rules / "security.md").write_text("# SEC\n")

    gc = root / "server" / "content"
    (gc / "indexes").mkdir(parents=True, exist_ok=True)
    (gc / "session").mkdir(parents=True, exist_ok=True)
    (gc / "indexes" / "skills-index.md").write_text(
        "# skills\n" + "\n".join(
            f"- `{s}`" for s in [
                "rtk", "fabric-ingest", "fabric-transform", "fabric-model", "fabric-validate",
                "fabric-notebook-loop", "fabric-ops", "fabric-pipeline", "semantic-model",
                "mock-data", "prd", "grill-me", "git-commit", "caveman",
            ]
        ) + "\n"
    )
    (gc / "session" / "operating-rules.md").write_text(
        "# rules\nrules/security rules/data-engineering rules/fabric-platform\n"
    )
    (gc / "entry.md").write_text(
        "# entry\n"
        "Mandatory setup gate\n"
        "tool\\setup\\setup.ps1\n"
        "tool/setup/setup.sh\n"
        "FABRIC_WORKSPACE_ID\n"
        "docker compose up\n"
        "graph_get_entry\n"
        "fab --version\n"
        "fab api workspaces\n"
        "fabric-cli workspace init\n"
        "fabric-cli workspace switch\n"
        "fabric-cli notebook deploy\n"
        "Do **not** read `.env` contents\n"
        "Setup incomplete\n"
        "before accepting any Fabric work\n"
        "network lakehouse notebook\n"
    )


def _hard_minimal_profile_body() -> str:
    return (
        "# Profile\n"
        "\n"
        "You know NOTHING about this project except how to call the graph tool.\n"
        "\n"
        "Call graph_get_entry first.\n"
    )


def test_validator_passes_with_hard_minimal_profile(tmp_path):
    _make_baseline_source_repo(tmp_path)
    body = _hard_minimal_profile_body()
    (tmp_path / "cli" / "profiles" / "claude" / "CLAUDE.md").write_text(body)
    (tmp_path / "cli" / "profiles" / "codex" / "AGENTS.md").write_text(body)
    assert collect_errors(tmp_path) == []


def test_validator_rejects_bloated_profile_over_50_lines(tmp_path):
    _make_baseline_source_repo(tmp_path)
    fat_body = _hard_minimal_profile_body() + "\n".join(f"line {i}" for i in range(60)) + "\n"
    (tmp_path / "cli" / "profiles" / "claude" / "CLAUDE.md").write_text(fat_body)
    (tmp_path / "cli" / "profiles" / "codex" / "AGENTS.md").write_text(fat_body)
    errors = collect_errors(tmp_path)
    assert any("hard-minimal" in e for e in errors), errors


def test_validator_rejects_profile_without_anchor(tmp_path):
    _make_baseline_source_repo(tmp_path)
    bad = "# Profile\n\nCall graph_get_entry first.\n"
    (tmp_path / "cli" / "profiles" / "claude" / "CLAUDE.md").write_text(bad)
    (tmp_path / "cli" / "profiles" / "codex" / "AGENTS.md").write_text(bad)
    errors = collect_errors(tmp_path)
    assert any("anti-drift anchor" in e for e in errors), errors


def test_validator_rejects_profile_with_operational_section_heading(tmp_path):
    _make_baseline_source_repo(tmp_path)
    bad = _hard_minimal_profile_body() + "\n## Pipeline Structure\n\nstuff here\n"
    (tmp_path / "cli" / "profiles" / "claude" / "CLAUDE.md").write_text(bad)
    (tmp_path / "cli" / "profiles" / "codex" / "AGENTS.md").write_text(bad)
    errors = collect_errors(tmp_path)
    assert any("operational section heading" in e for e in errors), errors
