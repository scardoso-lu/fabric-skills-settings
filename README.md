# Fabric Codex

Newcomer-ready operating system for Microsoft Fabric data engineering teams.

Run `setup.sh` on day one. Start with the `orchestrator` agent. Build enterprise-grade Fabric pipelines from the first day.

## Quick Start

```bash
git clone <this-repo>
cd fabric-skills-settings
./setup.sh                        # check tools, create folders, generate .env
./setup.sh --install-tools        # also install uv, Fabric CLI, nbmon
./setup.sh --install-skills       # also install recommended external skill packs
python3 bin/validate-source-contract.py --allow-placeholders templates/source-contract.yaml
python3 bin/validate-agent-guidance.py
```

Then open Claude Code or Codex and type:
> "I need to build a pipeline from [source] to [target]"

The `orchestrator` agent will scope the work and route it to the right specialist.


## Day One Checklist

1. [ ] Clone this repo and run `./setup.sh --install-tools`.
2. [ ] Create or open a sandbox Fabric workspace in <https://app.fabric.microsoft.com>.
3. [ ] Create three lakehouses in that workspace: `bronze_lh`, `silver_lh`, and `gold_lh`.
4. [ ] Copy the workspace and lakehouse IDs into `.env`.
5. [ ] Run `fab auth login` and rerun `./setup.sh` to confirm the auth check passes.
6. [ ] If you do not have source files yet, ask the orchestrator: "I need to build a test pipeline with mock orders data."
7. [ ] If you do have source files, place them under `data/sandbox/` and register placeholder `SRC_<SYSTEM>_*` entries.



## Validation and Discovery Helpers

| Helper | Purpose | Safe boundary |
|---|---|---|
| `python3 bin/validate-source-contract.py <contract.yaml>` | Validates source contract shape, primary keys, sensitive fields, outputs, and validation rules. | Local only; does not read `.env`, source data, or Fabric. |
| `python3 bin/validate-agent-guidance.py` | Checks runtime docs and sub-agent guidance for drift against bundled core skills and canonical docs. | Local only; no Fabric or network calls. |
| `bin/fabric-inventory-readonly` | Lets a human list Fabric workspaces/items with `fab api get`. | Read-only; never writes `.env`, memory, or Fabric resources. |

See `docs/fabric-sandbox-smoke-test.md`, `docs/fabric-mcp-readonly-discovery.md`, and `docs/agent-guidance-map.md` for the completed in-scope follow-up sprints.

## Agent Team

| Agent | Role |
|---|---|
| **orchestrator** | Confirms scope, routes tasks — never implements |
| **developer** | PySpark, SQL, notebooks, pipeline assets, sandbox execution |
| **tester** | Independent validation and repeatable DQ checks |
| **operator** | Key Vault, access control, sensitive data, security review |

**Standard flow**: orchestrator → developer → tester  
**Add operator** for any task touching secrets, PII, or access control.

## Skills

### Core (bundled)

| Skill | Purpose |
|---|---|
| `fabric-ingest` | Any source → Lakehouse/Warehouse ingestion |
| `fabric-transform` | Cleaning, typing, deduplication, MERGE |
| `fabric-model` | Dimensions, facts, KPIs, semantic models |
| `fabric-validate` | DQ checks, schema drift, row counts, anomalies |
| `fabric-notebook-loop` | Local .py → deploy → run → nbmon → fix cycle |
| `fabric-ops` | Orchestration, VACUUM, platform inventory |

### External (installable extensions)

```bash
./bin/install-skills.sh add microsoft/skills-for-fabric
./bin/install-skills.sh add PatrickGallucci/fabric-skills
./bin/install-skills.sh list
./bin/install-skills.sh update
./bin/install-skills.sh remove <pack-name>
```

External skills land in `skills/external/` and are immediately available to agents.

## Project Structure

```
fabric-skills-settings/
├── CLAUDE.md / AGENTS.md        # Runtime-specific agent instructions kept aligned
├── CONTEXT.md                   # Shared Fabric vocabulary
├── setup.sh                     # Bootstrap script (run once)
├── docs/                        # Smoke tests, MCP discovery, guidance map, examples
│
├── .claude/agents/
│   ├── orchestrator.md          # Scope + route
│   ├── developer.md             # Implement
│   ├── tester.md                # Validate
│   └── operator.md              # Security + access
│
├── rules/
│   ├── security.md              # Secrets, Key Vault, audit
│   ├── data-engineering.md      # Idempotency, lineage, DQ
│   └── fabric-platform.md       # Fabric API, Spark, async patterns
│
├── skills/
│   ├── core/                    # 6 bundled skill packs
│   └── external/                # Installed extensions (gitignored)
│
├── templates/
│   ├── source-contract.yaml
│   ├── pipeline-brief.md
│   ├── mock-data-generator.py
│   └── runbook.md
│
├── bin/
│   ├── install-skills.sh        # Extension manager
│   ├── validate-source-contract.py # Source contract validator
│   ├── validate-agent-guidance.py # Agent guidance drift check
│   ├── fabric-inventory-readonly # Human-run read-only Fabric inventory
│   ├── build_fabric_notebooks.py # .py → .Notebook converter
│   ├── fab-sandbox              # Fabric CLI sandbox wrapper
│   └── nbmon-sandbox            # Lightweight job monitor
│
├── .codex-fabric/               # Persistent agent memory (committed)
│   ├── MEMORY.md
│   └── memory/
│       ├── project.md           # Active pipelines and known issues
│       ├── platform.md          # Fabric items and source systems
│       ├── decisions.md         # Architecture decisions
│       ├── runbooks/            # Pipeline runbooks
│       └── security/            # Access reviews, Key Vault refs
│
└── .env.example                 # Environment variable template
```

## Rules (always enforced)

- **security.md** — no hardcoded secrets, sanitization barrier, audit envelope, sandbox boundary
- **data-engineering.md** — idempotency, lineage, quality gates, schema evolution, error handling
- **fabric-platform.md** — 202+poll async pattern, auth, Spark/SQL gotchas, Gold optimization

## Requirements

| Tool | Purpose | Install |
|---|---|---|
| Python 3.10+ | Runtime | python.org |
| uv | Package management | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Fabric CLI (fab) | Deploy and run Fabric items | `uv tool install ms-fabric-cli` |
| nbmon | Spark job debugging | `uv tool install nbmon` |
| Git | Clone and version control | git-scm.com |

## What This Is Not

- Not a Fabric workspace — it's a configuration wrapper you use alongside a Fabric workspace
- Not a specific project — it's a template you adapt to your pipelines
- Not prescriptive about architecture — Medallion is the default, but streaming, ODS, wide tables, and data vault patterns are all supported

## License

MIT
