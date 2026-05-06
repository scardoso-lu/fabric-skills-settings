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
```

Then open Claude Code and type:
> "I need to build a pipeline from [source] to [target]"

The `orchestrator` agent will scope the work and route it to the right specialist.

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
├── CLAUDE.md / AGENTS.md        # Agent instructions (cross-runtime, identical content)
├── CONTEXT.md                   # Shared Fabric vocabulary
├── setup.sh                     # Bootstrap script (run once)
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
│   └── runbook.md
│
├── bin/
│   ├── install-skills.sh        # Extension manager
│   ├── build-notebooks.py       # .py → .Notebook converter
│   └── fab-sandbox              # Fabric CLI sandbox wrapper
│
├── .codex-fabric/               # Agent memory (not committed)
│   └── memory/
│       ├── adr/                 # Architecture decisions
│       ├── platform-inventory/  # Fabric items catalog
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
