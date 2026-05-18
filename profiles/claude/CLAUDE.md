# Microsoft Fabric Data Engineering - Claude Code Profile

This repository is the runtime workspace. Work from this repository root; do not use an external wrapper path as the runtime root.

## Session Start - Run Every Session, In Order

0. **Mandatory setup gate - before accepting any Fabric work, verify `.env`, `fab`, and `fab auth`:**

   | Check | Pass | Fail - stop and show this |
   |---|---|---|
   | `.env` exists | file present | Human runs setup: Windows `.\tool\setup\setup.ps1` or Linux/Mac `bash tool/setup/setup.sh` |
   | `FABRIC_WORKSPACE_ID` set | key present in `.env` | Human edits `.env`, sets `FABRIC_WORKSPACE_ID=<uuid>`, then reruns setup |
   | `FABRIC_WAREHOUSE_HOST` set | key present in `.env` if project uses a Data Warehouse | Human gets it from Fabric UI, Data Warehouse, Settings, Connection strings, SQL connection string |
   | `fab` reachable | Windows: `tool\setup\fab-sandbox.ps1 --version` exits 0; Linux/Mac: `bash tool/setup/fab-sandbox --version` exits 0 | Human runs setup; it installs `ms-fabric-cli` via `uv tool install ms-fabric-cli` |
   | `fab` authenticated | Windows: `tool\setup\fab-sandbox.ps1 api workspaces --output_format json` exits 0; Linux/Mac: `bash tool/setup/fab-sandbox api workspaces --output_format json` exits 0 | Windows: `tool\setup\fab-sandbox.ps1 auth login`; Linux/Mac: `bash tool/setup/fab-sandbox auth login`. If the check fails due to network restriction, escalate and request network access before retrying. |

   Do **not** read `.env` contents or print values. Check only that the file exists and that required variable names are present. For example: Windows `Select-String -Path .env -Pattern FABRIC_WORKSPACE_ID -Quiet`; Linux/Mac `grep -q FABRIC_WORKSPACE_ID .env`.

   If **any check fails**, respond exactly:
   > "Setup incomplete. Fix the item(s) above - I will not start any Fabric task until setup passes."

   Then stop. Do not attempt workarounds or partial execution.

1. Read `memory/MEMORY.md` and each global file it lists.
2. Read all files in `memory/skill-fixes/`; these override `SKILL.md` defaults where they conflict.
3. If the request concerns a specific topic, read `memory/<topic>/project.md`.
4. Mention relevant context briefly, then address the request.

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
| `tool/data/` | Developer agent | `mock-data-generator.py` creates deterministic synthetic CSV files under `data/sandbox/` when no real source is available |
| `tool/notebook/` | Developer agent | `build.py` compiles `.py` to `.Notebook`; `deploy.py` deploys, executes, monitors, and fetches through REST; `smoke-test.ps1` / `smoke-test.sh` triggers and monitors |
| `tool/lakehouse/` | Developer agent, tester agent | `list-tables.py` lists lakehouse tables with column names and types |
| `tool/semantic-model/` | Developer agent, tester agent | `inspect.py` lists and inspects semantic models, tables, columns, DAX measures, and relationships |
| `tool/pipeline/` | Developer agent | `manage.py` creates, deploys, runs, and monitors Data Factory pipelines that chain topic notebooks |
| `tool/validate/` | Developer agent | `pipeline-lineage.py` validates staging-path consistency before build |
| `tool/mcp/` | Infrastructure | MCP server exposing repo-owned Fabric operations through the sandbox wrapper |
| `tool/pre-commit-check.ps1` / `tool/pre-commit-check.sh` | Developer agent | Runs completion validators before reporting done |

## Operating Rules

- Never ask for, echo, store, or commit credentials, tokens, connection strings, or real Fabric IDs.
- Never commit `.env`, data files, logs, `fabric_notebooks/`, or generated build intermediates.
- Humans must create the Fabric workspace and any lakehouses first and provide their names/IDs in `.env`.
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
