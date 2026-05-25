"""Phase P4: regression coverage for the rewritten validate-agent-guidance.py.

The hard-minimal profile contract enforces:
- profile <= 50 lines
- must reference graph_get_entry
- must contain the anti-drift anchor sentence
- must NOT contain operational section names (anti-bypass)
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "packaging" / "validators" / "validate-agent-guidance.py"


def _run_validator(tmp_root: Path) -> tuple[int, str]:
    """Run the validator as a subprocess with ROOT pointed at tmp_root.

    We copy the validator script into tmp_root/packaging/validators/ so its
    `ROOT = Path(__file__).resolve().parents[2]` resolves to tmp_root.
    """
    validators_dir = tmp_root / "packaging" / "validators"
    validators_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(VALIDATOR, validators_dir / VALIDATOR.name)
    result = subprocess.run(
        [sys.executable, str(validators_dir / VALIDATOR.name)],
        cwd=tmp_root,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout + result.stderr


def _make_baseline_source_repo(root: Path) -> None:
    """Set up the minimum directory tree the validator needs to NOT fail on
    unrelated checks (rule mirrors, skill wiring, etc.). Each helper writes
    a placeholder that just satisfies presence checks."""
    (root / "README.md").write_text("install-fabric-agent profiles/codex profiles/claude\n")
    (root / "AGENTS.md").write_text("install-fabric-agent profiles/codex profiles/claude\n")
    (root / "CLAUDE.md").write_text("install-fabric-agent profiles/codex profiles/claude\n")

    for skill in [
        "rtk", "fabric-ingest", "fabric-transform", "fabric-model", "fabric-validate",
        "fabric-notebook-loop", "fabric-ops", "fabric-pipeline", "semantic-model",
        "mock-data", "prd", "grill-me", "git-commit", "caveman",
    ]:
        (root / "profiles" / "skills" / skill).mkdir(parents=True, exist_ok=True)
        (root / "profiles" / "skills" / skill / "SKILL.md").write_text(f"# {skill}\n")

    (root / "profiles" / "claude" / "agents").mkdir(parents=True, exist_ok=True)
    (root / "profiles" / "codex" / "agents").mkdir(parents=True, exist_ok=True)
    for agent in ["orchestrator", "developer", "tester", "operator"]:
        (root / "profiles" / "claude" / "agents" / f"{agent}.md").write_text(
            f"# {agent}\nfabric-transform fabric-model fabric-validate tester\n"
        )
        (root / "profiles" / "codex" / "agents" / f"{agent}.toml").write_text(
            f"name = '{agent}'\n# fabric-transform fabric-model fabric-validate tester\n"
        )

    (root / "profiles" / "codex" / "config.toml").write_text("")
    (root / "profiles" / "claude" / "settings.local.json").write_text("{}")
    content_rules = root / "content" / "rules"
    content_rules.mkdir(parents=True, exist_ok=True)
    (content_rules / "data-engineering.md").write_text("# DE\nfabric-transform fabric-validate\n")
    (content_rules / "fabric-platform.md").write_text("# FP\nfabric-model\n")
    (content_rules / "security.md").write_text("# SEC\n")

    docs_dir = root / "docs"
    docs_dir.mkdir(exist_ok=True)
    (docs_dir / "tooling-map.md").write_text(
        "fabric-transform fabric-model fabric-validate DE-06 FP-08 DE-04\n"
    )

    gc = root / "content" / "graph-content"
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
        "fab-sandbox auth login\n"
        "Do **not** read `.env` contents\n"
        "Setup incomplete\n"
        "verify `.env`, `fab`, and `fab auth`\n"
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
    (tmp_path / "profiles" / "claude" / "CLAUDE.md").write_text(body)
    (tmp_path / "profiles" / "codex" / "AGENTS.md").write_text(body)
    code, out = _run_validator(tmp_path)
    assert code == 0, out


def test_validator_rejects_bloated_profile_over_50_lines(tmp_path):
    _make_baseline_source_repo(tmp_path)
    fat_body = _hard_minimal_profile_body() + "\n".join(f"line {i}" for i in range(60)) + "\n"
    (tmp_path / "profiles" / "claude" / "CLAUDE.md").write_text(fat_body)
    (tmp_path / "profiles" / "codex" / "AGENTS.md").write_text(fat_body)
    code, out = _run_validator(tmp_path)
    assert code != 0
    assert "hard-minimal" in out


def test_validator_rejects_profile_without_anchor(tmp_path):
    _make_baseline_source_repo(tmp_path)
    bad = "# Profile\n\nCall graph_get_entry first.\n"
    (tmp_path / "profiles" / "claude" / "CLAUDE.md").write_text(bad)
    (tmp_path / "profiles" / "codex" / "AGENTS.md").write_text(bad)
    code, out = _run_validator(tmp_path)
    assert code != 0
    assert "anti-drift anchor" in out


def test_validator_rejects_profile_with_operational_section_heading(tmp_path):
    _make_baseline_source_repo(tmp_path)
    bad = _hard_minimal_profile_body() + "\n## Pipeline Structure\n\nstuff here\n"
    (tmp_path / "profiles" / "claude" / "CLAUDE.md").write_text(bad)
    (tmp_path / "profiles" / "codex" / "AGENTS.md").write_text(bad)
    code, out = _run_validator(tmp_path)
    assert code != 0
    assert "operational section heading" in out
