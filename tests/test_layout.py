"""Layout assertions for the 3-package structure (cli / server / packaging)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


# ── packaging/ : validators only ──────────────────────────────────────────────
def test_packaging_only_has_validators():
    """After the 3-package split, packaging/ is just the validators dir."""
    assert (ROOT / "packaging" / "validators" / "validate-install-package.py").is_file()
    assert (ROOT / "packaging" / "validators" / "validate-agent-guidance.py").is_file()
    # No legacy children
    assert not (ROOT / "packaging" / "fabric_agent_installer").exists()
    assert not (ROOT / "packaging" / "install-fabric-agent").exists()
    assert not (ROOT / "packaging" / "builders").exists()


def test_cli_has_no_rules_dir():
    """Rules moved to server/content/rules/ — cli/rules/ must be gone."""
    assert not (ROOT / "cli" / "rules").exists()


# ── cli/ : CLI + everything it ships into target repos ────────────────────────
def test_cli_layout():
    """cli/ contains the installer wheel package + the executable + profile/tool/rule/setup
    content that the CLI installs into target repos."""
    cli = ROOT / "cli"
    assert (cli / "fabric_agent_installer" / "_installer.py").is_file()
    assert (cli / "install-fabric-agent").is_file()
    assert (cli / "profiles" / "claude" / "CLAUDE.md").is_file()
    assert (cli / "profiles" / "codex" / "AGENTS.md").is_file()
    assert not (cli / "profiles" / "skills").exists()
    assert (cli / "profiles" / "shared" / "scaffold" / ".mcp.json").is_file()
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
    bin/, build/, content/, mcp/, rules/, tool/, fabric_agent_installer/."""
    for legacy in ("bin", "build", "content", "mcp", "rules", "tool", "fabric_agent_installer"):
        assert not (ROOT / legacy).exists(), f"legacy top-level {legacy!r} still present"


