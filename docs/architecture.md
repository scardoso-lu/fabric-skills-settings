# Architecture

Fabric Agent Pack installs two MCP servers into every target repository. Together they give Claude Code and Codex a structured way to discover project knowledge and act against a Microsoft Fabric workspace.

| Server | Role | Module |
|---|---|---|
| `fabric` | Wraps the Fabric CLI: list/get items, authenticated REST API calls. | `mcp/server.py` |
| `fabric-graph` | RAG knowledge graph: BM25 + 1-hop edge-aware read tools and full CRUD over nodes and edges. | `mcp/graph-server.py` |

The installed `CLAUDE.md` / `AGENTS.md` entrypoints are minimal (~30 lines). They tell the agent to call `graph_get_entry` first and then traverse the graph; all operational knowledge — setup gate, session-start order, workflow steps, skills, tools, rules — is encoded as graph nodes, not as static markdown for the agent to read directly.

```mermaid
flowchart TD
    CC["Claude Code"]

    subgraph Agents["Agents (sub-agents)"]
        ORC["Orchestrator"]
        DEV["Developer"]
        TST["Tester"]
        OPS["Operator"]
    end

    subgraph MCP["Local MCP Servers"]
        FAB["fabric MCP server\nmcp/server.py"]
        GRF["fabric-graph MCP server\nmcp/graph-server.py\n(BM25 + 1-hop search + CRUD)"]
    end

    subgraph GraphStore["memory/.graph/ (target runtime; source-side build outputs live at dist/.graph/)"]
        GJ["graph.json"]
        BM["graph-bm25.pkl"]
    end

    subgraph FabricTools["Local domain tools"]
        TN["tool/notebook/"]
        TP["tool/pipeline/"]
        TL["tool/lakehouse/"]
        TV["tool/validate/"]
    end

    MSF["Microsoft Fabric Workspace\n(Fabric CLI / REST API)"]

    CC -->|spawns| Agents
    CC -->|MCP| FAB
    CC -->|MCP| GRF

    FAB -->|Fabric CLI / REST| MSF
    FAB -->|invokes| FabricTools
    FabricTools -->|Fabric CLI / REST| MSF

    GRF -->|reads| GraphStore
    GRF -->|CRUD write → atomic rebuild| GraphStore

```


## Subagents

Four native subagents are installed alongside the entrypoint:

| Subagent | Owns | Reports to |
|---|---|---|
| `orchestrator` | Scoping, routing, human handoff | Human |
| `developer` | Notebooks, transforms, models, pipelines | `orchestrator` |
| `tester` | DQ, schema drift, RI, metric sanity | `orchestrator` |
| `operator` | Security review, secrets, access, supply chain | `orchestrator` |

Subagents are discovered by Claude and Codex from their native profile directories (`.claude/agents/*.md`, `.codex/agents/*.toml`). They are not primary graph nodes — the capability graph in `memory/.graph/agent-capabilities.json` is a derived inspection artifact only.

## Where things live

| Concern | Source (this repo) | Installed location (target repo) |
|---|---|---|
| Entry instructions | `profiles/claude/CLAUDE.md`, `profiles/codex/AGENTS.md` | Target repo root |
| Subagents | `profiles/{claude,codex}/agents/` | `.claude/agents/`, `.codex/agents/` |
| Skills | `profiles/skills/` | `.claude/skills/`, `.agents/skills/` |
| Rules | `content/rules/*.md` | `memory/rules/*.md` |
| Knowledge graph content | `content/graph-content/` | `memory/graph-content/` |
| Seed memory | `profiles/shared/memory/` | `memory/` |
| Target scaffold (data/sandbox/, workspace/, ...) | `profiles/shared/scaffold/` | Target repo root |
| `.mcp.json` | not shipped — written by `tool/setup/setup.{sh,ps1}` | Target repo root (concrete MCP URL) |
| Graph artifacts | `dist/.graph/` (source build output, gitignored) | `memory/.graph/` (shipped by installer + rebuilt by `tool/graph/writes.py` on CRUD) |
| MCP servers | `mcp/` (top-level, parallel to `tool/`) | `mcp/` |
| Graph runtime | `tool/graph/` | `tool/graph/` |
| Source-package CLI | `cli/src/fabric_skills_settings/` | installed as the `fabric-skills-settings` wheel |
| Source-package validators | `tests/test_install_package.py`, `tests/test_agent_guidance.py` (+ `tests/_validation/`) | **not installed** (maintainer pytest) |

## Setup CLI — install path

The CLI is published as `fabric-skills-settings` on PyPI and exposes two
console scripts:

| Command | Role |
|---|---|
| `fabric-agents` | Typer installer with `install` / `check` / `refresh` subcommands. Writes profile, scaffold, and tool files into a target repo, then runs the target bootstrap. |
| `fabric-cli` | Typer proxy for target-side helpers — `notebook`, `pipeline`, `lakehouse`, `workspace`, `lint`, `precommit`. Run from the target repo root. |

Install the package itself with:

```bash
uv tool install fabric-skills-settings        # recommended
# or
pip install fabric-skills-settings
```

Then install a profile into your project repo:

```bash
fabric-agents install --profile claude --target /path/to/project
fabric-agents check   --profile claude --target /path/to/project
fabric-agents refresh --profile claude --target /path/to/project
```

After the install copies files, the installer automatically invokes
`<target>/tool/setup/setup.{ps1,sh}` to finish the bootstrap: create `.venv`,
install Fabric CLI helpers (`ms-fabric-cli`, `Faker`, `pandas`, `networkx`,
`rank-bm25`, RTK), prompt for any missing `FABRIC_TENANT_ID` /
`FABRIC_CLIENT_ID` / `FABRIC_CLIENT_SECRET`, verify auth via
`fab api workspaces`, and populate `workspaces.json`. Pass `--no-bootstrap`
to skip — `--dry-run` and the `check` subcommand skip implicitly.

```mermaid
flowchart TD
    PIP["uv tool install fabric-skills-settings<br/>(or pip install)"]
    PIP --> CLI
    CLI["fabric-agents install --profile X --target Y"]
    CLI --> INST

    INST["fabric_skills_settings.commands.install<br/>copy files into target"]
    INST --> TGT
    TGT["target/<br/>CLAUDE.md · mcp/ · tool/ · memory/ · .mcp.json · ..."]
    TGT --> BOOT

    BOOT["target/tool/setup/setup.{ps1,sh}<br/>.venv · Fabric CLI helpers · RTK<br/>prompt for FABRIC_* credentials<br/>tool/workspace/init.py → workspaces.json"]
    INST -.->|"--no-bootstrap · --dry-run · --check"| DONE
    BOOT --> DONE

    DONE([target ready — open in Claude Code / Codex])
```

## Folder structure

### Source repository (this repo)

```text
fabric-skills-settings/
├── README.md  CLAUDE.md  AGENTS.md  LICENSE  pyproject.toml  uv.lock  .gitignore
│
├── cli/                                 installable assets
│   ├── src/fabric_skills_settings/      pip-installable wheel package
│   │   ├── __init__.py  __main__.py  cli.py
│   │   ├── commands/{install,check,refresh}.py
│   │   └── core/{files,gitignore,profiles,bootstrap,markers,paths}.py
│   ├── builders/                        source-only graph builders
│   │   ├── build-graph.py
│   │   ├── build-agent-capability-graph.py
│   │   └── graph_build/                 build-time-only modules (visualize, agent_capabilities)
│   └── validators/                      source-only validators
│       ├── validate-install-package.py
│       └── validate-agent-guidance.py
│
├── tool/                                Fabric runtime helpers (single source of truth)
│   ├── data/  graph/  lakehouse/  notebook/  pipeline/  semantic-model/
│   ├── setup/  validate/  workspace/
│   └── pre-commit-check.{ps1,sh}
│
├── mcp/                                 MCP servers (top-level, parallel to tool/)
│   ├── server.py                        fabric MCP — wraps the Fabric CLI
│   └── graph-server.py                  fabric-graph MCP — knowledge graph
│
├── content/                             installable content sources
│   ├── rules/                           security, data-engineering, fabric-platform, notebook-authoring
│   └── graph-content/                   entry.md, session/, workflow/, layout/, indexes/,
│                                        integrations/, diagnostics/, semantic/
│
├── profiles/
│   ├── claude/                          CLAUDE.md, agents/, settings.local.json
│   ├── codex/                           AGENTS.md, agents/, config.toml
│   ├── skills/                          shared skill source (installed to both .claude/ and .agents/)
│   └── shared/
│       ├── .env.example  .gitignore.fragment
│       ├── memory/                      seed memory (.gitkeep, skill-fixes/) → target memory/
│       └── scaffold/                    target-only scaffolding (data/sandbox/, workspace/);
│                                        .mcp.json is NOT here — the bootstrap writes it
│
├── dist/                                build outputs
│   ├── .graph/                          source-side knowledge-graph artifacts (gitignored)
│   │   ├── graph.json  graph-bm25.pkl
│   │   ├── materialized-graph.{html,svg}
│   │   └── agent-capabilities.{html,json}
│   └── *.whl  *.tar.gz                  wheel + sdist from `uv build`
│
├── docs/
│   └── architecture.md
└── tests/                               pytest suite (includes test_layout.py)
```

Disappeared as part of the redesign: `bin/`, `build/`, `rules/` at root, `profiles/shared/project-layout/`, `profiles/shared/graph-content/`, `tool/mcp/`, source-side `memory/.graph/`.

### Installed target repository (what `fabric-agents install` produces)

```text
<target-repo>/
├── CLAUDE.md  or  AGENTS.md             from profiles/{claude,codex}/  (hard-minimal stub)
├── .env.example  .gitignore             managed block
├── .mcp.json                            written by tool/setup/setup.{sh,ps1} (concrete MCP URL)
│
├── .claude/                             agents/, skills/, settings.local.json   (claude profile)
├── .codex/                              agents/, config.toml                    (codex profile)
├── .agents/skills/                      same skills as .claude/skills/          (codex profile)
│
├── tool/                                Fabric runtime helpers
├── mcp/                                 MCP servers (server.py, graph-server.py)
│
├── memory/                              runtime persistence root
│   ├── .graph/                          shipped pre-built; rebuilt on CRUD writes
│   ├── rules/                           from content/rules/
│   ├── graph-content/                   from content/graph-content/
│   ├── skill-fixes/
│   ├── notebook-authoring.md            from scaffold/memory/
│   └── pipeline-authoring.md
│
├── contracts/  data/sandbox/  workspace/   scaffold placeholders
```