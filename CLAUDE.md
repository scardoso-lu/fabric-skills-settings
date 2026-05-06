# Fabric Codex — Data Engineering Wrapper

Newcomer-ready operating system for Microsoft Fabric data engineering teams.
Run `setup.sh` on day one. Use Claude Code for structured, safe, enterprise-grade Fabric work from the start.

> **Codex CLI users**: see `AGENTS.md` — it is a self-contained version with all agent definitions inlined.

---

## Session Start (every session)

1. Read `.codex-fabric/MEMORY.md` — the project memory index
2. Read `.codex-fabric/memory/project.md` — active pipelines and known issues
3. Briefly surface relevant context before addressing the user's request

Memory persists across sessions. Agents must update it after significant work.

---

## Agent Team

Sub-agents are defined in `.claude/agents/` and loaded automatically by Claude Code.
Each agent has tool restrictions enforced via frontmatter — they cannot exceed their scope.

| Agent | Tools | Role |
|---|---|---|
| `orchestrator` | Read, Glob, Grep | Scopes tasks, routes to specialists — never implements |
| `developer` | Read, Write, Edit, Bash, Glob, Grep | All implementation: PySpark, SQL, notebooks, pipelines |
| `tester` | Read, Bash, Glob, Grep | Independent validation — never modifies data or code |
| `operator` | Read, Bash, Glob, Grep | Security review: Key Vault, PII, access control, audit |

**Standard workflow**: orchestrator → developer → tester
**Add operator** for any task touching secrets, PII, or access control.

---

## Memory (persists across sessions)

```
.codex-fabric/
├── MEMORY.md                  # Index — read every session start
└── memory/
    ├── project.md             # Active pipelines, current focus, known issues
    ├── platform.md            # Fabric items: workspaces, lakehouses, warehouses
    ├── decisions.md           # Architecture decisions with rationale
    ├── runbooks/              # One .md per scheduled pipeline
    └── security/              # Key Vault refs, access decisions (operator writes here)
```

Agents write to memory before handoff. Never rely on conversation history alone.

---

## Skills

Core skills ship bundled. Read the relevant `SKILL.md` before starting a task.

| Skill | Purpose |
|---|---|
| `skills/core/fabric-ingest` | Any source → Lakehouse/Warehouse ingestion |
| `skills/core/fabric-transform` | Silver: cleaning, MERGE, type casting, quarantine |
| `skills/core/fabric-model` | Gold: star schema, KPIs, referential integrity |
| `skills/core/fabric-validate` | DQ checks, row counts, schema drift, anomalies |
| `skills/core/fabric-notebook-loop` | Local .py → deploy → run → nbmon → fix cycle |
| `skills/core/fabric-ops` | VACUUM, DAG orchestration, platform inventory |

Install external skill packs from any GitHub repo:
```bash
./bin/install-skills.sh add microsoft/skills-for-fabric
./bin/install-skills.sh add PatrickGallucci/fabric-skills
./bin/install-skills.sh list
./bin/install-skills.sh remove <pack-name>
```

---

## Absolute Rule — Credentials

**Agents never ask for, receive, or output real credentials.**
All connection details (hosts, passwords, tokens, API keys) are output as `os.environ["PLACEHOLDER"]` only.
The human fills in the values. See `rules/security.md` SEC-00.

## Rules (always enforced)

Read the full rule files — these apply to all agents:
- `rules/security.md` — SEC-00 credentials boundary, Key Vault refs, sanitization, audit envelope
- `rules/data-engineering.md` — idempotency, lineage, quality gates, schema evolution
- `rules/fabric-platform.md` — async API (202+poll), nbmon debugging, Spark/SQL patterns

---

## Quick Start

```bash
./setup.sh --install-tools     # install uv, Fabric CLI, nbmon
fab auth login                 # authenticate once — token shared across all tools
cp .env.example .env           # fill in workspace IDs and source credentials
```

---

## Project Structure

```
fabric-skills-settings/
├── CLAUDE.md                  # Claude Code instructions (this file)
├── AGENTS.md                  # Codex CLI instructions (agents inlined, self-contained)
├── CONTEXT.md                 # Shared Fabric vocabulary
├── setup.sh                   # Bootstrap script (run once)
│
├── .claude/
│   ├── agents/                # orchestrator · developer · tester · operator
│   └── settings.json          # Project-level tool permissions (committed)
│
├── rules/
│   ├── security.md
│   ├── data-engineering.md
│   └── fabric-platform.md
│
├── skills/
│   ├── core/                  # 6 bundled skill packs
│   └── external/              # Installed extensions (add via install-skills.sh)
│
├── templates/                 # source-contract · pipeline-brief · runbook · …
│
├── bin/
│   ├── install-skills.sh      # Extension manager
│   ├── build_fabric_notebooks.py  # .py → .Notebook converter
│   ├── fab-sandbox            # Fabric CLI sandbox wrapper
│   └── nbmon-sandbox          # Lightweight job monitor
│
└── .codex-fabric/             # Persistent agent memory (committed)
    ├── MEMORY.md
    └── memory/
```
