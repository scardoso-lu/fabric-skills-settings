# Fabric Codex — Data Engineering Wrapper

Newcomer-ready operating system for Microsoft Fabric data engineering teams.
Run `setup.sh` on day one. Use Claude Code for structured, safe, enterprise-grade Fabric work from the start.

> **Codex CLI users**: see `AGENTS.md` — it is a self-contained version with all agent definitions inlined.
> Keep this file aligned with `AGENTS.md`, `.claude/agents/`, and the rule files.

---

## Session Start (every session)

1. Read `.codex-fabric/MEMORY.md` — the project memory index.
2. Read `.codex-fabric/memory/project.md` — active pipelines and known issues.
3. Briefly surface relevant context before addressing the user's request.

Memory persists across sessions. Agents must update the relevant memory file after significant work.

---

## Project Review Summary

This repository is a configuration wrapper, not a Fabric workspace. It gives agents a repeatable operating model for sandbox-first Microsoft Fabric data engineering.

| Area | Files/directories | Notes for agents |
|---|---|---|
| Runtime instructions | `CLAUDE.md`, `AGENTS.md`, `.claude/agents/` | Claude Code uses split sub-agent specs; Codex uses `AGENTS.md`. Keep guidance consistent across both runtimes. |
| Persistent memory | `.codex-fabric/MEMORY.md`, `.codex-fabric/memory/` | Always read the index and project state first; update memory for project, platform, decision, validation, and security changes. |
| Rules | `rules/security.md`, `rules/data-engineering.md`, `rules/fabric-platform.md` | These apply to all roles. Read the full relevant rules before implementation, validation, or security review. |
| Skills | `skills/core/*/SKILL.md`, `skills/external/` | Read the relevant `SKILL.md` before starting related work. External packs are optional and installed with `bin/install-skills.sh`. |
| Templates | `templates/` | Use source contracts, briefs, mock data, runbooks, release, DQ, incident, and security templates instead of inventing formats. |
| Thresholds | `config/thresholds.yaml` | Read this file for all DQ threshold values (quarantine rate, row count drop, null rate, RI failures). Never hardcode thresholds. |
| Tooling | `setup.sh`, `bin/build_fabric_notebooks.py`, `bin/fab-sandbox`, `bin/nbmon-sandbox`, `bin/install-skills.sh` | Prefer sandbox wrappers and the local `.py` → `.Notebook` build flow. |

---

## Sprint Improvements Implemented

Roadmap items were accepted where they reinforced the project purpose: a newcomer-ready, sandbox-first Fabric wrapper. Adjustments made during implementation:
- External skill discovery is documented as optional reference material; bundled `skills/core/` and `rules/` remain authoritative.
- Skill usage wording says to read `SKILL.md` files instead of invoking aspirational slash commands.
- Runbooks are split into Phase 1 (known before first run) and Phase 2 (observed after first successful run).
- Quarantine escalation is treated as an operator investigation until schema, validation, or PII/masking root cause is known.

---

## Day-One Checklist

1. [ ] Run `./setup.sh` to create local folders and `.env` from `.env.example`.
2. [ ] Run `./setup.sh --install-tools` if `uv`, Fabric CLI (`fab`), or `nbmon` are missing.
3. [ ] Create or identify the sandbox Fabric workspace and three lakehouses: `bronze_lh`, `silver_lh`, and `gold_lh`.
4. [ ] Fill placeholder IDs in `.env`, then run `fab auth login` if the setup auth check is not authenticated.
5. [ ] Register sandbox source placeholders as `SRC_<SYSTEM>_TYPE=file` and `SRC_<SYSTEM>_PATH=./data/sandbox/<file>.csv`.
6. [ ] Validate source contracts with `python3 bin/validate-source-contract.py <contract.yaml>`.
7. [ ] Use `docs/fabric-sandbox-smoke-test.md` and `docs/fabric-mcp-readonly-discovery.md` for human-run sandbox discovery/smoke checks.
8. [ ] Start with the orchestrator: "I need to build a pipeline from [source] to [target]."

Agents must never ask for, receive, echo, or commit real credentials while helping with these steps.

**Fabric item creation**: agents cannot create Fabric items (notebooks, pipelines, lakehouses). The human must create items in the portal first, then tell the agent the item name. The agent uses the Fabric MCP read-only tools to look up the item ID. The human copies the ID into `.env`. See `docs/fabric-mcp-readonly-discovery.md` for the full sequence.

---

## Agent Team

Sub-agents are defined in `.claude/agents/` and loaded automatically by Claude Code.
Each agent has tool restrictions enforced via frontmatter — they cannot exceed their scope.

| Agent | Tools | Role |
|---|---|---|
| `orchestrator` | Read, Glob, Grep | Scopes tasks, routes to specialists — never implements |
| `developer` | Read, Write, Edit, Bash, Glob, Grep | All implementation: PySpark, SQL, notebooks, pipelines, mock data, repo maintenance |
| `tester` | Read, Bash, Glob, Grep | Independent validation — never modifies data or code |
| `operator` | Read, Bash, Glob, Grep | Security review: Key Vault, PII, access control, audit, quarantine escalation |

**Standard workflow**: orchestrator → developer → tester.
**Add operator** for any task touching secrets, PII, access control, quarantine >5%, or production handoff.

---

## Memory (persists across sessions)

```
.codex-fabric/
├── MEMORY.md                  # Index — read every session start
└── memory/
    ├── project.md             # Active pipelines, current focus, known issues
    ├── platform.md            # Fabric items and source systems
    ├── decisions.md           # Architecture decisions with rationale
    ├── runbooks/              # One .md per scheduled pipeline
    └── security/              # Key Vault refs, access decisions (operator writes here)
```

Agents write to memory before handoff. Never rely on conversation history alone. Run `python3 bin/validate-agent-guidance.py` after guidance changes.

---

## Skills

Core skills ship bundled. Read the relevant `SKILL.md` before starting a task.

| Skill | Purpose |
|---|---|
| `skills/core/fabric-ingest/SKILL.md` | Any source → Lakehouse/Warehouse ingestion |
| `skills/core/fabric-transform/SKILL.md` | Silver: cleaning, MERGE, type casting, quarantine |
| `skills/core/fabric-model/SKILL.md` | Gold: star schema, KPIs, referential integrity |
| `skills/core/fabric-validate/SKILL.md` | DQ checks, row counts, schema drift, anomalies |
| `skills/core/fabric-notebook-loop/SKILL.md` | Local `.py` → deploy → run → capture run ID → nbmon → fix cycle |
| `skills/core/fabric-ops/SKILL.md` | VACUUM, DAG orchestration, platform inventory, daily checks |

External skill packs are optional. Read `roadmap/external-skills.md` before installing them from GitHub.
Use `--verify` to review recent commits before accepting a pack:

```bash
./bin/install-skills.sh add microsoft/skills-for-fabric --verify
./bin/install-skills.sh add PatrickGallucci/fabric-skills --verify
./bin/install-skills.sh list
./bin/install-skills.sh update
./bin/install-skills.sh remove <pack-name>
```

⚠ External skill packs execute as agent context — only install from repos you have reviewed.

---

## Absolute Rule — Credentials

**Agents never ask for, receive, or output real credentials.**
All connection details (hosts, passwords, tokens, API keys, connection strings) are output as placeholders such as `os.environ["SRC_ORDERS_HOST"]` or Key Vault refs.
The human fills in the values. See `rules/security.md` SEC-00.

If the user pastes a real credential: warn them it may be exposed, ask them to rotate it, do not use it, and do not repeat it.

## Rules (always enforced)

Read the full rule files — these apply to all agents:
- `rules/security.md` — SEC-00 credentials boundary, Key Vault refs, sanitization, audit envelope
- `rules/data-engineering.md` — idempotency, lineage, quality gates, schema evolution
- `rules/fabric-platform.md` — async API (202+poll), nbmon debugging, Spark/SQL patterns

---

## Quick Start

```bash
./setup.sh                    # create folders, .env, and show Fabric next steps/auth status
./setup.sh --install-tools    # install/check uv, Fabric CLI, nbmon
fab auth login                # authenticate once if setup says Fabric auth is not authenticated
```

---

## Project Structure

```
fabric-skills-settings/
├── CLAUDE.md                  # Claude Code instructions (this file)
├── AGENTS.md                  # Codex CLI instructions (agents inlined, self-contained)
├── CONTEXT.md                 # Shared Fabric vocabulary
├── README.md                  # Human-facing overview
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
├── templates/                 # source-contract · pipeline-brief · mock-data · runbook · …
│
├── bin/
│   ├── install-skills.sh      # Extension manager
│   ├── validate-source-contract.py # Source contract validator
│   ├── validate-agent-guidance.py # Guidance drift check
│   ├── fabric-inventory-readonly # Human-run read-only inventory helper
│   ├── build_fabric_notebooks.py  # .py → .Notebook converter
│   ├── fab-sandbox            # Fabric CLI sandbox wrapper
│   └── nbmon-sandbox          # Lightweight job monitor
│
├── docs/                      # Agent guidance map, smoke tests, MCP discovery, examples

├── roadmap/
│   ├── ROADMAP.md             # Improvement backlog and sprint status
│   └── external-skills.md     # Optional external skill discovery guide
│
└── .codex-fabric/             # Persistent agent memory (committed)
    ├── MEMORY.md
    └── memory/
```
