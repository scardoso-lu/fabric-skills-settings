# Microsoft Fabric Data Engineering — Claude Code Profile

<<<<<<< HEAD
You are a Fabric engineering agent operating inside this repository.
=======
## Agent Operating Principles

**1. Core Operating Principles**

- **Do not assume**: If a requirement is ambiguous, incomplete, or missing context, stop and ask specific clarifying questions. Do not guess the user's intent.
- **Expose confusion**: If you do not understand how a piece of existing code works, state what you don't understand before attempting to modify it.
- **Correctness over completion**: Do not rush to provide a complete solution if it is structurally flawed. A perfectly correct partial step is better than a complete but broken file.

**2. Think Before Coding (Planning Phase)**

Before writing any code, output a `<plan>` block containing: the exact goal in one sentence, the constraints and edge cases, and a step-by-step logical approach in plain English. Wait for the user to approve the plan before proceeding, unless explicitly instructed to skip approval.

**3. Surgical Edits Only (Execution Phase)**

When modifying existing code: make targeted changes only — do not rewrite, refactor, or clean up unrelated code. Match the exact naming conventions, indentation, and architectural style of the surrounding code. Specify exactly which lines to replace using clear BEFORE/AFTER blocks or precise line references.

**4. Simplicity First (Design Phase)**

Write the simplest possible code that satisfies the goal. Do not create abstract classes, complex generic interfaces, or boilerplate unless explicitly requested. Rely on standard libraries over installing new packages whenever possible.

---

This repository is the runtime workspace. Work from this repository root; do not use an external wrapper path as the runtime root.
>>>>>>> 7f090e27d7bb7d3202705269a048fd0709803fbf

You know NOTHING about this project except how to call the graph tool.
All project knowledge — the mandatory setup gate, operating rules,
pipeline structure, skills, agents, semantic models, memory, and
per-topic context — lives in a knowledge graph. You MUST discover what
you need by traversing the graph. Do not read project markdown files
directly; use the graph.

## How to work

1. Call the Fabric graph MCP `graph_get_entry` tool first, before any
   other action. In Codex this is exposed as
   `mcp__fabric_graph__.graph_get_entry`; in clients that flatten MCP
   names, use the equivalent `fabric-graph` `graph_get_entry` tool.
   The returned node is the mandatory setup gate. Follow it literally
   — do not start any Fabric task until every gate check passes.
2. If the current node does not answer the user's question, call
   `graph_get_linked` with that node's id to see its neighbors.
   Choose one and call `graph_get_node`.
3. You may only navigate to node ids returned by `graph_get_entry`,
   `graph_get_linked`, or `graph_search`. Never guess or hallucinate
   a node id.
4. Use `graph_search` only when no linked node looks relevant and a
   fresh entry point is needed.
5. When the answer is in hand, cite the node ids you sourced from
   (e.g. "per `graph-content/workflow/pipeline-structure` and
   `skill-fixes/silver-do-not-trust-bronze-types`").
6. To author or modify a knowledge node, use `graph_create_node` /
   `graph_update_node` / `graph_add_edge` rather than direct file
   edits. To remove graph knowledge, use `graph_delete_node` /
   `graph_remove_edge` only when explicitly asked.

## Graph tool surface

<<<<<<< HEAD
Read: `graph_get_entry`, `graph_get_node`, `graph_get_linked`,
`graph_search`, `graph_list_kinds`.
Write: `graph_create_node`, `graph_update_node`, `graph_delete_node`,
`graph_add_edge`, `graph_remove_edge`. All write operations
re-serialize the graph atomically.
=======
   A workspace confirmation covers the whole session. Re-confirm only after the human explicitly runs `switch.py`.

   If **any check fails**, respond exactly:
   > "Setup incomplete. Fix the item(s) above - I will not start any Fabric task until setup passes."

   Then stop. Do not attempt workarounds or partial execution.

1. Read `memory/MEMORY.md` and each global file it lists.
2. Read all files in `memory/skill-fixes/`; these override `SKILL.md` defaults where they conflict.
3. If the request concerns a specific topic, read `memory/<topic>/project.md`.
4. Mention relevant context briefly, then apply the Agent Operating Principles above before proceeding with any implementation.

## Directory Layout

```text
workspace/
  <topic>/
    <name>.py            <- transient working source (# %% cells); removed after successful fetch
    <name>.Notebook/     <- canonical git artifact; ready for human commit after every passing run,
                           synced with Fabric UI via Git integration

fabric_notebooks/        <- build intermediates (gitignored), do not commit
  <topic>/
    <name>.Notebook/     <- built by build.py, consumed by deploy.py REST upload
```

Use one topic subfolder per data source or business domain, for example `workspace/lux_energy_price/`. Notebook stems must be unique across all subfolders because Fabric display names are flat.

## Notebook Workflow

```text
author -> build -> deploy REST -> smoke test -> fetch -> human commits via Fabric UI
.py       fabric_notebooks/  Fabric      exec+monitor  workspace/<topic>/<name>.Notebook/
```

Deploy and smoke test are separate steps:

- Deploy on source change: `python tool/notebook/deploy.py deploy <name> <workspace_id>`.
- Smoke test an existing deployed notebook: Windows `tool\notebook\smoke-test.ps1 -Notebook <name>`; Linux/Mac `tool/notebook/smoke-test.sh --notebook <name>`.
- Fetch after a passing run: `python tool/notebook/deploy.py fetch <name> <workspace_id>`.

The smoke test never deploys. It triggers a job on whatever is already in Fabric and reports status. After fetch, stop and report to the orchestrator. Do not run `git add`, `git rm`, or `git commit` for fetched Fabric notebook artifacts unless the human explicitly asks for a repository commit.

## Tool Layout

| Directory | Invoked by | Purpose |
|---|---|---|
| `tool/setup/` | Human once, agents verify only | `setup.ps1` / `setup.sh` environment bootstrap; `fab-sandbox` authenticated Fabric CLI wrapper; `fabric-inventory-readonly` read-only workspace/item lookup |
| `tool/workspace/` | Developer agent, orchestrator | `init.py` discovers all workspaces and resources from the Fabric API; `switch.py` sets the active workspace and writes resource IDs to `.env`; `transfer.py` transfers notebooks and pipelines between workspaces |
| `tool/data/` | Developer agent | `mock-data-generator.py` creates deterministic synthetic CSV files under `data/sandbox/` when no real source is available |
| `tool/notebook/` | Developer agent | `build.py` compiles `.py` to `.Notebook`; `deploy.py` deploys, executes, monitors, and fetches through REST; `smoke-test.ps1` / `smoke-test.sh` triggers and monitors |
| `tool/lakehouse/` | Developer agent, tester agent | `list-tables.py` lists lakehouse tables with column names and types |
| `tool/semantic-model/` | Developer agent, tester agent | `inspect.py` lists and inspects semantic models, tables, columns, DAX measures, and relationships |
| `tool/pipeline/` | Developer agent | `manage.py` creates, deploys, runs, and monitors Data Factory pipelines that chain topic notebooks |
| `tool/validate/` | Developer agent | `pipeline-lineage.py` validates staging-path consistency before build |
| `tool/mcp/` | Infrastructure | MCP server exposing repo-owned Fabric operations through the sandbox wrapper |
| `tool/pre-commit-check.ps1` / `tool/pre-commit-check.sh` | Developer agent | Runs completion validators before reporting done |

## Workspace Management

All workspace and resource IDs come exclusively from `workspaces.json` — never from manually entered values or `.env` edits.

### Discovery (once per session, after auth)

```bash
python tool/workspace/init.py
```

Queries the Fabric API for every accessible workspace and its Lakehouses, Warehouses, Notebooks, and DataPipelines. Writes the full API response to `workspaces.json`. Run this if `workspaces.json` is missing or stale.

### Listing and switching

```bash
python tool/workspace/switch.py list           # show all discovered workspaces; marks active
python tool/workspace/switch.py <displayName>  # set active workspace; writes resource IDs to .env
```

`switch.py` writes `FABRIC_WORKSPACE_ID`, `FABRIC_LAKEHOUSE_<NAME>`, `FABRIC_WAREHOUSE_<NAME>`, and `FABRIC_WAREHOUSE_HOST` into the auto-generated section of `.env`. Do not edit these values manually.

After switching, remind the human to reload their Claude Code session — the MCP server reads `.env` only at startup.

### Transferring artifacts between workspaces

Transfer does **not** change the active workspace. Lakehouses and warehouses are matched by `displayName` (e.g. "Bronze", "Silver", "Gold", "DataWarehouse"). If a name is not found in the target workspace, the tool prompts the user for the ID — never abort silently.

```bash
# Transfer a single notebook to another workspace
python tool/workspace/transfer.py --notebook <name>  --to <displayName>

# Transfer all notebooks for a topic
python tool/workspace/transfer.py --topic    <topic> --to <displayName>

# Transfer a pipeline (notebooks must already be deployed in the target workspace)
python tool/workspace/transfer.py --pipeline <topic> --to <displayName>
```

## Operating Rules

- Never ask for, echo, store, or commit credentials, tokens, connection strings, or real Fabric IDs.
- Never commit `.env`, `workspaces.json`, data files, logs, `fabric_notebooks/`, or generated build intermediates.
- Humans must create the Fabric workspace and any lakehouses first. Resource IDs are discovered automatically via `python tool/workspace/init.py`.
- Agents may create or update notebook items and workspace folders automatically via `tool/notebook/deploy.py`.
- Agents must not run `tool/setup/setup.ps1` or `tool/setup/setup.sh`; they verify setup state and report blockers.
- All Fabric CLI/API access must route through `tool/setup/fab-sandbox.ps1` on Windows or `bash tool/setup/fab-sandbox` on Linux/Mac, or through a repo helper that uses that wrapper.
- Use `memory/rules/fabric-platform.md`, `memory/rules/data-engineering.md`, and `memory/rules/security.md` as active runtime rules; they are installed from the source package `rules/` folder.
- Source contracts belong in notebook `# %% [contract]` cells as Python dataclasses, not YAML files.
- Thresholds belong in notebook `# %% [parameters]` cells so Fabric pipeline parameters can override them.
- Keep download, ingestion, and data quality separate: `download_<source>.py` fetches, `bronze_<source>.py` ingests only new files, and `dq_bronze_<source>.py` validates.
- If no source files exist for a new or demo topic, use the `mock-data` skill and `python tool/data/mock-data-generator.py`. Always pass `--schema '<json>'` or `--schema-file <path>` derived from the target table.

## Pipeline Structure

Every data source topic starts with exactly three notebooks:

| Notebook | Naming | Responsibility |
|---|---|---|
| Download | `download_<source>.py` | Call source API, skip existing sandbox files, save raw files as-is. No Spark. No Delta writes. Print existing, downloaded, and failed counts. |
| Ingestion | `bronze_<source>.py` | Read sandbox files, compare against Bronze Delta table, process only new files, then MERGE or partition-overwrite. Never full-overwrite. |
| Data quality | `dq_bronze_<source>.py` | Great Expectations checks for row count, null PKs, duplicate PKs, schema match, and business sanity. Print structured PASS/FAIL per check and raise on any failure. |

A single notebook that downloads, ingests, and overwrites is always wrong. The developer agent may create the DQ notebook scaffold; the tester agent owns independent validation logic and final DQ validation.

## Skills

Use project skills in `.claude/skills/`:

- `fabric-ingest` for source-to-Bronze ingestion.
- `fabric-transform` for developer-owned Silver/Gold transformations and MERGE patterns; rule anchor: DE-06.
- `fabric-model` for developer-owned Gold facts, dimensions, KPIs, and semantic models; rule anchor: FP-08.
- `fabric-validate` for tester-owned independent DQ checks; rule anchor: DE-04.
- `fabric-notebook-loop` for local `.py` to Fabric notebook iteration.
- `fabric-ops` for orchestration, VACUUM, inventory, and platform operations.
- `fabric-pipeline` for creating, deploying, and testing the Data Factory pipeline that chains all topic notebooks end-to-end.
- `mock-data` for deterministic synthetic sandbox CSV files when no real source exists.
- `semantic-model` for listing and inspecting Fabric Semantic Models before writing DAX or mapping Gold outputs to KPIs.
- `prd` for implementation-ready requirements documents.
- `grill-me` for stress-testing a plan or design through one-question-at-a-time interrogation.
- `git-commit` for focused conventional commits when the human explicitly asks for a git commit.
- `caveman` for ultra-compressed responses when the user asks for caveman mode or lower token usage.

## Agents

Use project subagents in `.claude/agents/`:

- `orchestrator` scopes and routes.
- `developer` implements.
- `tester` validates independently.
- `operator` reviews security, PII, and access.

## RTK Token Optimizer

RTK reduces shell output token consumption. It is installed by `tool/setup/setup.sh` / `tool/setup/setup.ps1`.

Claude Code sessions handle RTK automatically through the Bash hook; no manual command prefix is required.

Do not call raw `fab`. Use `tool/setup/fab-sandbox.ps1` on Windows or `bash tool/setup/fab-sandbox` on Linux/Mac for Fabric CLI checks.
>>>>>>> 7f090e27d7bb7d3202705269a048fd0709803fbf
