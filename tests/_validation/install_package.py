"""Validate the vendor-native Fabric agent profile package layout.

Importable form of the former packaging/validators/validate-install-package.py.
Call `collect_errors(root)`; an empty list means the layout is valid.
"""

from __future__ import annotations

import re
from pathlib import Path

SKILLS = {
    "rtk",
    "fabric-ingest",
    "fabric-transform",
    "fabric-model",
    "fabric-validate",
    "fabric-notebook-loop",
    "fabric-ops",
    "fabric-pipeline",
    "semantic-model",
    "mock-data",
    "prd",
    "grill-me",
    "git-commit",
    "caveman",
}
AGENTS = {"orchestrator", "developer", "tester", "operator"}
FORBIDDEN = [
    "wrapper repo",
    "configuration wrapper",
    "ignore target repo instructions",
    "this repo is the authoritative harness",
    "everything goes to $TARGET_REPO_PATH",
]


def _skill_names(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {p.parent.name for p in path.glob("*/SKILL.md")}


def _agent_names(path: Path, suffix: str) -> set[str]:
    if not path.exists():
        return set()
    return {p.stem for p in path.glob(f"*{suffix}")}


class _Validator:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.profiles = root / "cli" / "profiles"
        self.setup = root / "cli" / "setup"
        self.cli_tools = root / "cli" / "tools"
        self.server = root / "server"
        self.tools = self.server / "tools"
        self.graph_content = self.server / "content"
        self.rules = self.graph_content / "rules"
        self.errors: list[str] = []

    # ── helpers ──────────────────────────────────────────────────────────────
    def _rel(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.root))
        except ValueError:
            return str(path)

    def _require(self, path: Path) -> None:
        if not path.exists():
            self.errors.append(f"Missing required path: {self._rel(path)}")

    # ── checks ───────────────────────────────────────────────────────────────
    def required(self) -> None:
        p = self.profiles
        self._require(p / "codex" / "AGENTS.md")
        self._require(p / "codex" / "config.toml")
        self._require(p / "claude" / "CLAUDE.md")
        self._require(p / "claude" / "settings.local.json")
        if (p / "claude" / "settings.json").exists():
            self.errors.append(
                "profiles/claude/settings.json must not exist; Claude local installs use settings.local.json"
            )
        self._require(p / "shared" / ".env.example")
        self._require(p / "shared" / ".gitignore.fragment")
        # .mcp.json is no longer shipped as a scaffold template — the target
        # bootstrap (tool/setup/setup.{sh,ps1}) writes it with a concrete URL.
        if (p / "shared" / "scaffold" / ".mcp.json").exists():
            self.errors.append(
                "profiles/shared/scaffold/.mcp.json must not exist; the bootstrap writes .mcp.json dynamically"
            )
        self._require(self.rules / "data-engineering.md")
        self._require(self.rules / "fabric-platform.md")
        self._require(self.rules / "security.md")
        self._require(self.graph_content / "entry.md")
        # server/ — MCP server + graph runtime + graph content + graph builders.
        self._require(self.server / "__init__.py")
        self._require(self.server / "app.py")
        self._require(self.server / "script_runner.py")
        self._require(self.server / "audit.py")
        self._require(self.server / "Dockerfile")
        self._require(self.server / "graph" / "store.py")
        self._require(self.server / "graph" / "search.py")
        self._require(self.server / "graph" / "writes.py")
        self._require(self.server / "builders" / "build-graph.py")
        # server/tools/ — MCP-exposed helpers that don't need ms-fabric-cli.
        self._require(self.tools / "semantic_model" / "tools.py")
        self._require(self.tools / "semantic_model" / "inspect.py")
        self._require(self.tools / "validate" / "tools.py")
        self._require(self.tools / "validate" / "pipeline-lineage.py")
        self._require(self.tools / "data" / "tools.py")
        self._require(self.tools / "data" / "mock-data-generator.py")
        self._require(self.tools / "graph" / "tools.py")
        # cli/tools/ — target-side helpers invoked locally via Bash (NOT MCP).
        self._require(self.cli_tools / "notebook" / "build.py")
        self._require(self.cli_tools / "notebook" / "deploy.py")
        self._require(self.cli_tools / "notebook" / "smoke-test.ps1")
        self._require(self.cli_tools / "notebook" / "smoke-test.sh")
        self._require(self.cli_tools / "pipeline" / "manage.py")
        self._require(self.cli_tools / "lakehouse" / "list-tables.py")
        self._require(self.cli_tools / "workspace" / "init.py")
        self._require(self.cli_tools / "workspace" / "switch.py")
        self._require(self.cli_tools / "workspace" / "transfer.py")
        self._require(self.cli_tools / "workspace" / "pick.py")
        self._require(self.cli_tools / "lint" / "__init__.py")
        self._require(self.cli_tools / "lint" / "core.py")
        self._require(self.cli_tools / "precommit" / "pre-commit-check.ps1")
        self._require(self.cli_tools / "precommit" / "pre-commit-check.sh")
        # cli/setup/ — env-setup scripts (shipped to target as tool/setup/).
        self._require(self.setup / "setup.ps1")
        self._require(self.setup / "setup.sh")
        # Skills live on the server and are served via graph_get_node.
        server_skills = _skill_names(self.server / "skills")
        if (p / "skills").exists():
            self.errors.append("cli/profiles/skills must not exist; skills moved to server/skills/")
        if server_skills != SKILLS:
            self.errors.append(
                f"Server skills mismatch: expected {sorted(SKILLS)}, found {sorted(server_skills)}"
            )
        codex_agents = _agent_names(p / "codex" / "agents", ".toml")
        claude_agents = _agent_names(p / "claude" / "agents", ".md")
        if codex_agents != AGENTS:
            self.errors.append(f"Codex agents mismatch: expected {sorted(AGENTS)}, found {sorted(codex_agents)}")
        if claude_agents != AGENTS:
            self.errors.append(f"Claude agents mismatch: expected {sorted(AGENTS)}, found {sorted(claude_agents)}")

    def forbidden_text(self) -> None:
        for path in (q for q in self.profiles.rglob("*") if q.is_file()):
            text = path.read_text(errors="ignore")
            rel = self._rel(path)
            for phrase in FORBIDDEN:
                if phrase in text:
                    self.errors.append(f"Forbidden phrase {phrase!r} in {rel}")
            if "TARGET_REPO_PATH" in text:
                self.errors.append(f"Unexpected TARGET_REPO_PATH usage in {rel}")

    def safe_datalake_controls(self) -> None:
        settings = self.profiles / "claude" / "settings.local.json"
        if settings.exists():
            text = settings.read_text(errors="ignore")
            for phrase in ("Bash(fab *)", "Bash(rtk *)", "mcp__fabric__fabric_api_get"):
                if phrase in text:
                    self.errors.append(f"Unsafe agent permission {phrase!r} in {self._rel(settings)}")

    def env_example(self) -> None:
        env_file = self.profiles / "shared" / ".env.example"
        if not env_file.exists():
            return
        env_text = env_file.read_text(errors="ignore")
        suspicious_patterns = [
            r"=https?://",
            r"=abfss://",
            r"=jdbc:",
            r"=AccountKey=",
            r"=SharedAccessSignature=",
            r"=eyJ[A-Za-z0-9_-]+",
        ]
        for line in env_text.splitlines():
            stripped = line.lstrip()
            if not stripped or stripped.startswith("#"):
                continue
            for pattern in suspicious_patterns:
                if re.search(pattern, stripped):
                    self.errors.append(
                        f"Suspicious non-placeholder value in profiles/shared/.env.example matching {pattern}"
                    )

    def shared_scope(self) -> None:
        shared = self.profiles / "shared"
        for path in (shared / ".agents", shared / ".codex", shared / ".claude", shared / "skills", shared / "agents"):
            if path.exists():
                self.errors.append(f"Shared profile must not contain vendor runtime assets: {self._rel(path)}")

    def rule_mirrors(self) -> None:
        for name in ("data-engineering.md", "fabric-platform.md", "security.md"):
            if not (self.rules / name).exists():
                self.errors.append(f"Missing source rule file: server/content/rules/{name}")
        platform = self.rules / "fabric-platform.md"
        if platform.exists():
            text = platform.read_text(errors="ignore")
            for phrase in ("fab auth login", "fab auth token", "fab api "):
                if phrase in text:
                    self.errors.append(
                        f"server/content/rules/fabric-platform.md must reference the MCP fabric_* tools instead of raw {phrase!r}"
                    )

    def ps1_syntax(self) -> None:
        location = self.cli_tools / "notebook" / "smoke-test.ps1"
        if location.exists() and "?." in location.read_text(errors="ignore"):
            self.errors.append(
                f"PS7-only null-conditional '?.' found in {self._rel(location)} — must be PS5.1 compatible"
            )

    def load_env_strips_comments(self) -> None:
        for name in ("build.py", "deploy.py"):
            location = self.cli_tools / "notebook" / name
            if not location.exists():
                continue
            if 'val.split("#")[0]' not in location.read_text(errors="ignore"):
                self.errors.append(
                    f"_load_env in {self._rel(location)} does not strip inline comments"
                    ' — add val.split("#")[0].strip() before setdefault'
                )

    def gitignore_fragment(self) -> None:
        path = self.profiles / "shared" / ".gitignore.fragment"
        if not path.exists():
            return
        if ".mcp.json" not in path.read_text(errors="ignore"):
            self.errors.append(
                "profiles/shared/.gitignore.fragment must ignore .mcp.json"
                " — MCP settings are installed for local target runtime use"
            )

    def setup_contract(self) -> None:
        for location in (self.setup / "setup.ps1", self.setup / "setup.sh"):
            if not location.exists():
                continue
            text = location.read_text(errors="ignore")
            rel_path = self._rel(location)
            if "Fabric workspace GUID" in text:
                self.errors.append(
                    f"{rel_path} must not prompt for FABRIC_WORKSPACE_ID; use the workspace_init/workspace_switch MCP tools"
                )
            for phrase in ("FABRIC_TENANT_ID", "FABRIC_CLIENT_ID", "FABRIC_CLIENT_SECRET", "FABRIC_SERVER_URL"):
                if phrase not in text:
                    self.errors.append(f"{rel_path} missing setup contract phrase {phrase!r}")
            # Bootstrap is the sole creator of .mcp.json (no scaffold template ships).
            if ".mcp.json" not in text:
                self.errors.append(f"{rel_path} must write .mcp.json with the MCP server URL")
            # Bootstrap must also patch the Codex MCP endpoint in .codex/config.toml.
            if ".codex/config.toml" not in text:
                self.errors.append(
                    f"{rel_path} must patch .codex/config.toml [mcp_servers.fabric-server] url"
                )

    def setup_no_graph_build(self) -> None:
        for location in (self.setup / "setup.ps1", self.setup / "setup.sh"):
            if not location.exists():
                continue
            text = location.read_text(errors="ignore").replace("\\", "/")
            rel_path = self._rel(location)
            for forbidden in ("server/builders/build-graph.py", "bin/build-graph.py"):
                if forbidden in text:
                    self.errors.append(
                        f"{rel_path} must not reference the graph builder "
                        "(target users do not build graphs; the MCP server owns the graph)"
                    )

    def run(self) -> list[str]:
        self.required()
        self.forbidden_text()
        self.safe_datalake_controls()
        self.env_example()
        self.shared_scope()
        self.rule_mirrors()
        self.ps1_syntax()
        self.load_env_strips_comments()
        self.gitignore_fragment()
        self.setup_contract()
        self.setup_no_graph_build()
        return self.errors


def collect_errors(root: Path) -> list[str]:
    return _Validator(root).run()
