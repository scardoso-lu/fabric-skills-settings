"""Layout assertions for the 2-package structure (cli / server)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


# ── validators are now pytest modules, not a standalone packaging/ tree ───────
def test_validators_are_pytest_modules():
    """The former packaging/validators/ scripts moved into tests/ as pytest
    modules backed by importable logic under tests/_validation/."""
    assert (ROOT / "tests" / "_validation" / "install_package.py").is_file()
    assert (ROOT / "tests" / "_validation" / "agent_guidance.py").is_file()
    assert (ROOT / "tests" / "test_install_package.py").is_file()
    assert (ROOT / "tests" / "test_agent_guidance.py").is_file()
    # The standalone packaging/ tree is gone.
    assert not (ROOT / "packaging").exists()


def test_cli_has_no_rules_dir():
    """Rules moved to server/content/rules/ — cli/rules/ must be gone."""
    assert not (ROOT / "cli" / "rules").exists()


# ── cli/ : CLI + everything it ships into target repos ────────────────────────
def test_cli_layout():
    """cli/ contains the installer wheel package (src/ layout) + the user-facing
    install scripts + profile/tool/setup content that the CLI installs into
    target repos."""
    cli = ROOT / "cli"
    # New src/ layout — fabric_skills_settings package with Typer CLI.
    pkg = cli / "src" / "fabric_skills_settings"
    assert (pkg / "__init__.py").is_file()
    assert (pkg / "cli.py").is_file()
    assert (pkg / "commands" / "install.py").is_file()
    assert (pkg / "commands" / "check.py").is_file()
    assert (pkg / "commands" / "refresh.py").is_file()
    assert (pkg / "core" / "files.py").is_file()
    assert (pkg / "core" / "gitignore.py").is_file()
    assert (pkg / "core" / "profiles.py").is_file()
    assert (pkg / "core" / "bootstrap.py").is_file()
    # Canonical CLI install is `uv tool install fabric-skills-settings` —
    # no top-level cli/setup.{sh,ps1} wrapper. `cli/setup/setup.{sh,ps1}`
    # is the target-repo bootstrap, shipped to <target>/tool/setup/.
    assert not (cli / "setup.sh").exists()
    assert not (cli / "setup.ps1").exists()
    # Legacy launcher and old package layout are gone.
    assert not (cli / "fabric_agent_installer").exists()
    assert not (cli / "install-fabric-agent").exists()
    assert (cli / "profiles" / "claude" / "CLAUDE.md").is_file()
    assert (cli / "profiles" / "codex" / "AGENTS.md").is_file()
    assert not (cli / "profiles" / "skills").exists()
    # .mcp.json is written by the target bootstrap, not shipped as a scaffold template.
    assert not (cli / "profiles" / "shared" / "scaffold" / ".mcp.json").exists()
    assert (cli / "setup" / "setup.sh").is_file()
    assert (cli / "setup" / "setup.ps1").is_file()
    # fab-sandbox / fabric-inventory-readonly removed — fab is server-side now
    assert not (cli / "setup" / "fab-sandbox").exists()
    assert not (cli / "setup" / "fabric-inventory-readonly").exists()
    # ms-fabric-cli-dependent helpers live in cli/tools/ (target-side, invoked via Bash).
    assert (cli / "tools" / "notebook" / "build.py").is_file()
    assert (cli / "tools" / "notebook" / "deploy.py").is_file()
    assert (cli / "tools" / "pipeline" / "manage.py").is_file()
    assert (cli / "tools" / "lakehouse" / "list-tables.py").is_file()
    assert (cli / "tools" / "workspace" / "init.py").is_file()
    assert (cli / "tools" / "workspace" / "switch.py").is_file()
    assert (cli / "tools" / "workspace" / "transfer.py").is_file()
    # Deterministic lints + pre-commit aggregator also live target-side now.
    assert (cli / "tools" / "lint" / "__init__.py").is_file()
    assert (cli / "tools" / "lint" / "core.py").is_file()
    assert (cli / "tools" / "precommit" / "pre-commit-check.sh").is_file()
    assert (cli / "tools" / "precommit" / "pre-commit-check.ps1").is_file()


# ── server/ : MCP servers + graph runtime + graph content + graph builders ───
def test_server_layout():
    """server/ is self-contained: FastMCP app + graph runtime + graph content + builders + Dockerfile."""
    server = ROOT / "server"
    assert (server / "app.py").is_file()
    # *_tools.py wrappers moved to server/tools/<name>/tools.py
    assert not (server / "fabric_tools.py").exists()
    assert not (server / "graph_tools.py").exists()
    assert (server / "Dockerfile").is_file()
    assert (server / "docker-compose.yml").is_file()
    assert (server / "graph" / "store.py").is_file()
    assert (server / "graph" / "search.py").is_file()
    assert (server / "graph" / "writes.py").is_file()
    assert (server / "content" / "entry.md").is_file()
    assert (server / "content" / "rules" / "security.md").is_file()
    assert (server / "tools" / "semantic_model" / "inspect.py").is_file()
    assert (server / "tools" / "graph" / "tools.py").is_file()
    assert (server / "tools" / "validate" / "pipeline-lineage.py").is_file()
    assert (server / "tools" / "data" / "mock-data-generator.py").is_file()
    assert (server / "builders" / "build-graph.py").is_file()
    assert (server / "skills" / "rtk" / "SKILL.md").is_file()
    assert (server / "skills" / "fabric-transform" / "SKILL.md").is_file()
    # Fab-dependent tools moved to cli/tools/ — server no longer has them.
    assert not (server / "fab.py").exists()
    assert not (server / "tools" / "fabric").exists()
    assert not (server / "tools" / "notebook").exists()
    assert not (server / "tools" / "pipeline").exists()
    assert not (server / "tools" / "lakehouse").exists()
    assert not (server / "tools" / "workspace").exists()
    # Lint + pre-commit moved to cli/tools/ — server no longer registers them.
    assert not (server / "tools" / "lint").exists()
    assert not (server / "tools" / "precommit").exists()


# ── Legacy roots that should be gone ──────────────────────────────────────────
def test_legacy_top_levels_removed():
    """After the split, these top-level folders disappear (children migrated):
    bin/, build/, content/, mcp/, rules/, tool/, fabric_agent_installer/,
    fabric_skills_settings/."""
    for legacy in ("bin", "build", "content", "mcp", "rules", "tool",
                   "fabric_agent_installer", "fabric_skills_settings"):
        assert not (ROOT / legacy).exists(), f"legacy top-level {legacy!r} still present"


