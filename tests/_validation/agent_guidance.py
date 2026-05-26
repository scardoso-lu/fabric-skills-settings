"""Validate source-package guidance for the vendor-native installer setup.

Importable form of the former packaging/validators/validate-agent-guidance.py.
Profiles are checked only for hard-minimal shape (<= 50 lines, must mention the
graph tool, no operational section headings); operational content lives in
graph-content nodes. Call `collect_errors(root)`; empty list means valid.
"""

from __future__ import annotations

from pathlib import Path

REQUIRED_SKILLS = {
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
REQUIRED_AGENTS = {"orchestrator", "developer", "tester", "operator"}
FORBIDDEN_GUIDANCE_PHRASES = [
    "configuration wrapper",
    "authoritative harness",
    "ignore target repo instructions",
    "everything goes to `$TARGET_REPO_PATH`",
]
PROFILE_MAX_LINES = 50
PROFILE_ANCHOR = "You know NOTHING about this project except how to call the graph tool"
PROFILE_ENTRY_TOOL = "graph_get_entry"
PROFILE_FORBIDDEN_SECTION_NAMES = [
    "## Pipeline Structure",
    "## Tool Layout",
    "## Directory Layout",
    "## Operating Rules",
    "## Notebook Workflow",
    "## Smoke-test Diagnostics",
    "## Semantic Models",
    "## Workspace Management",
]


def _skill_names(base: Path) -> set[str]:
    return {p.parent.name for p in base.glob("*/SKILL.md")} if base.exists() else set()


def _agent_names(base: Path, suffix: str) -> set[str]:
    return {p.stem for p in base.glob(f"*{suffix}")} if base.exists() else set()


class _Validator:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.profile_files = [
            root / "cli" / "profiles" / "claude" / "CLAUDE.md",
            root / "cli" / "profiles" / "codex" / "AGENTS.md",
        ]
        self.graph_content = root / "server" / "content"
        self.entry_file = self.graph_content / "entry.md"
        self.operating_rules_file = self.graph_content / "session" / "operating-rules.md"
        self.skills_index_file = self.graph_content / "indexes" / "skills-index.md"
        self.forbidden_root_runtime = [
            root / ".claude" / "agents",
            root / ".claude" / "skills",
            root / "skills",
        ]
        self.errors: list[str] = []

    def _rel(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.root))
        except ValueError:
            return str(path)

    def _require(self, path: Path) -> None:
        if not path.exists():
            self.errors.append(f"missing required path: {self._rel(path)}")

    # ── checks ───────────────────────────────────────────────────────────────
    def root_guidance(self) -> None:
        for path in (self.root / "AGENTS.md", self.root / "CLAUDE.md", self.root / "README.md"):
            self._require(path)
            if not path.exists():
                continue
            text = path.read_text(errors="ignore")
            if "fabric-agents" not in text:
                self.errors.append(
                    f"{self._rel(path)} must describe installer-first usage (fabric-agents)"
                )
            if "profiles/codex" not in text and path.name != "README.md":
                self.errors.append(f"{self._rel(path)} must reference profiles/codex")
            if "profiles/claude" not in text and path.name != "README.md":
                self.errors.append(f"{self._rel(path)} must reference profiles/claude")
            for phrase in FORBIDDEN_GUIDANCE_PHRASES:
                if phrase in text:
                    self.errors.append(f"forbidden wrapper phrase {phrase!r} in {self._rel(path)}")

    def profiles(self) -> None:
        r = self.root
        self._require(r / "cli" / "profiles" / "codex" / "AGENTS.md")
        self._require(r / "cli" / "profiles" / "codex" / "config.toml")
        self._require(r / "cli" / "profiles" / "claude" / "CLAUDE.md")
        self._require(r / "cli" / "profiles" / "claude" / "settings.local.json")
        if (r / "cli" / "profiles" / "claude" / "settings.json").exists():
            self.errors.append(
                "profiles/claude/settings.json must not exist; Claude local installs use settings.local.json"
            )
        self._require(r / "server" / "content" / "rules" / "data-engineering.md")
        self._require(r / "server" / "content" / "rules" / "fabric-platform.md")
        self._require(r / "server" / "content" / "rules" / "security.md")

        server_skills = _skill_names(r / "server" / "skills")
        if (r / "cli" / "profiles" / "skills").exists():
            self.errors.append("cli/profiles/skills must not exist; skills moved to server/skills/")
        if server_skills != REQUIRED_SKILLS:
            self.errors.append(f"Server skill set mismatch: {sorted(server_skills)}")

        codex_agents = _agent_names(r / "cli" / "profiles" / "codex" / "agents", ".toml")
        claude_agents = _agent_names(r / "cli" / "profiles" / "claude" / "agents", ".md")
        if codex_agents != REQUIRED_AGENTS:
            self.errors.append(f"Codex agent set mismatch: {sorted(codex_agents)}")
        if claude_agents != REQUIRED_AGENTS:
            self.errors.append(f"Claude agent set mismatch: {sorted(claude_agents)}")
        if codex_agents != claude_agents:
            self.errors.append("Codex and Claude profile agents differ")

        settings = r / "cli" / "profiles" / "claude" / "settings.local.json"
        if settings.exists():
            text = settings.read_text(errors="ignore")
            for phrase in ("Bash(fab *)", "Bash(rtk *)", "mcp__fabric__fabric_api_get"):
                if phrase in text:
                    self.errors.append(
                        f"{self._rel(settings)} must not allow {phrase!r}; agents consume only the safe sandbox workspace"
                    )

    def profile_minimalism(self) -> None:
        for path in self.profile_files:
            if not path.exists():
                continue
            text = path.read_text(errors="ignore")
            line_count = text.count("\n") + (0 if text.endswith("\n") else 1)
            if line_count > PROFILE_MAX_LINES:
                self.errors.append(
                    f"{self._rel(path)} has {line_count} lines; hard-minimal profile must be <= {PROFILE_MAX_LINES}"
                )
            if PROFILE_ENTRY_TOOL not in text:
                self.errors.append(f"{self._rel(path)} must reference {PROFILE_ENTRY_TOOL!r}")
            if PROFILE_ANCHOR not in text:
                self.errors.append(
                    f"{self._rel(path)} must contain anti-drift anchor sentence: {PROFILE_ANCHOR!r}"
                )
            for forbidden in PROFILE_FORBIDDEN_SECTION_NAMES:
                if forbidden in text:
                    self.errors.append(
                        f"{self._rel(path)} contains operational section heading {forbidden!r};"
                        " move that content to a graph-content node"
                    )

    def entry_node(self) -> None:
        if not self.entry_file.exists():
            self.errors.append(f"missing entry node: {self._rel(self.entry_file)}")
            return
        text = self.entry_file.read_text(errors="ignore")
        required = [
            # Target bootstrap (raw scripts — runs before fabric-cli is on the target's PATH).
            "tool\\setup\\setup.ps1",
            "tool/setup/setup.sh",
            "FABRIC_WORKSPACE_ID",
            "docker compose up",
            "graph_get_entry",
            # Direct ms-fabric-cli probes (NOT proxied — `fab` is the upstream tool).
            "fab --version",
            "fab api workspaces",
            # Daily helpers go through the fabric-cli proxy.
            "fabric-cli workspace init",
            "fabric-cli workspace switch",
            "fabric-cli notebook deploy",
            "Do **not** read `.env` contents",
            "Setup incomplete",
            "Mandatory setup gate",
            "before accepting any Fabric work",
            "network",
            "lakehouse",
            "notebook",
        ]
        for phrase in required:
            if phrase not in text:
                self.errors.append(f"missing required phrase in {self._rel(self.entry_file)}: {phrase!r}")
        if "FABRIC_WORKSPACE_ID` is missing" in text:
            self.errors.append(
                f"entry node {self._rel(self.entry_file)} implies reading .env via 'FABRIC_WORKSPACE_ID` is missing'"
            )

    def skills_index_node(self) -> None:
        if not self.skills_index_file.exists():
            self.errors.append(f"missing skills index node: {self._rel(self.skills_index_file)}")
            return
        text = self.skills_index_file.read_text(errors="ignore")
        for skill in REQUIRED_SKILLS:
            if f"`{skill}`" not in text:
                self.errors.append(f"{self._rel(self.skills_index_file)} must list installed skill `{skill}`")

    def session_nodes(self) -> None:
        if not self.operating_rules_file.exists():
            self.errors.append(f"missing operating-rules node: {self._rel(self.operating_rules_file)}")
            return
        text = self.operating_rules_file.read_text(errors="ignore")
        for rule_id in ("rules/security", "rules/data-engineering", "rules/fabric-platform"):
            if rule_id not in text:
                self.errors.append(f"{self._rel(self.operating_rules_file)} must reference {rule_id!r}")

    def platform_rules_use_wrapper(self) -> None:
        path = self.root / "server" / "content" / "rules" / "fabric-platform.md"
        if not path.exists():
            return
        text = path.read_text(errors="ignore")
        for phrase in ("fab auth login", "fab auth token", "fab api "):
            if phrase in text:
                self.errors.append(
                    f"{self._rel(path)} must reference the MCP fabric_* tools instead of raw {phrase!r}"
                )

    def skill_wiring(self) -> None:
        r = self.root
        required = [
            (r / "cli" / "profiles" / "claude" / "agents" / "developer.md", ["fabric-transform", "fabric-model"]),
            (r / "cli" / "profiles" / "codex" / "agents" / "developer.toml", ["fabric-transform", "fabric-model"]),
            (r / "cli" / "profiles" / "claude" / "agents" / "tester.md", ["fabric-validate", "tester"]),
            (r / "cli" / "profiles" / "codex" / "agents" / "tester.toml", ["fabric-validate", "tester"]),
            (r / "server" / "content" / "rules" / "data-engineering.md", ["fabric-transform", "fabric-validate"]),
            (r / "server" / "content" / "rules" / "fabric-platform.md", ["fabric-model"]),
        ]
        for path, phrases in required:
            if not path.exists():
                self.errors.append(f"missing required path for skill wiring: {self._rel(path)}")
                continue
            text = path.read_text(errors="ignore")
            for phrase in phrases:
                if phrase not in text:
                    self.errors.append(f"missing skill wiring phrase {phrase!r} in {self._rel(path)}")

    def no_root_runtime(self) -> None:
        for path in self.forbidden_root_runtime:
            if path.exists():
                self.errors.append(f"root runtime directory should not exist in source package: {self._rel(path)}")

    def run(self) -> list[str]:
        self.root_guidance()
        self.profiles()
        self.profile_minimalism()
        self.entry_node()
        self.skills_index_node()
        self.session_nodes()
        self.platform_rules_use_wrapper()
        self.skill_wiring()
        self.no_root_runtime()
        return self.errors


def collect_errors(root: Path) -> list[str]:
    return _Validator(root).run()
