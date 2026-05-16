# Microsoft Fabric Data Engineering — Codex Profile

This repository is the runtime workspace. Work from this repo root; do not use an external wrapper path as the runtime root.

## Session Start — Run Every Session, In Order

1. Read `memory/MEMORY.md` and each global file it lists.
2. Read all files in `memory/skill-fixes/` — these override SKILL.md defaults where they conflict.
3. If the request concerns a specific topic, read `memory/<topic>/project.md`.
3. **Verify setup — check all of the following before accepting any Fabric work:**

   | Check | Pass | Fail — stop and show this |
   |---|---|---|
   | `.env` exists | file present | Run setup: Windows `.\tool\setup\setup.ps1` · Linux/Mac `bash tool/setup/setup.sh` |
   | `FABRIC_WORKSPACE_ID` set | non-empty in `.env` | Edit `.env` → set `FABRIC_WORKSPACE_ID=<uuid>`, then rerun setup |
   | `FABRIC_WAREHOUSE_HOST` set | non-empty in `.env` (if project uses a Data Warehouse) | Fabric UI → Data Warehouse → Settings → Connection strings → SQL connection string |
   | `fab` reachable | Windows: `tool\setup\fab-sandbox.ps1 --version` exits 0 · Linux/Mac: `bash tool/setup/fab-sandbox --version` exits 0 | Run setup script; it installs `ms-fabric-cli` via `uv tool install ms-fabric-cli` |
   | `fab` authenticated | Windows: `tool\setup\fab-sandbox.ps1 api workspaces --output_format json` exits 0 · Linux/Mac: `bash tool/setup/fab-sandbox api workspaces --output_format json` exits 0 | Windows: `tool\setup\fab-sandbox.ps1 auth login` · Linux/Mac: `bash tool/setup/fab-sandbox auth login` · If exit code is non-zero due to network restriction (sandbox/firewall), escalate and request network access before retrying — do not treat a network block as a permanent auth failure |

   Do **not** read `.env` contents. Check only that the file exists and that `FABRIC_WORKSPACE_ID` is present (use Windows: `Select-String -Path .env -Pattern FABRIC_WORKSPACE_ID -Quiet` · Linux/Mac: `grep -q FABRIC_WORKSPACE_ID .env`).

   If **any check fails**, respond exactly:
   > "⚠ Setup incomplete. Fix the item(s) above — I will not start any Fabric task until setup passes."

   Then stop. Do not attempt workarounds or partial execution.

4. Mention relevant context briefly, then address the request.

## Directory Layout

```
workspace/
  <topic>/
    <name>.py            ← transient working source (# %% cells); deleted after successful fetch
    <name>.Notebook/     ← canonical git artifact; committed after every passing run,
                           synced with Fabric UI via Git integration

fabric_notebooks/        ← build intermediates (gitignored), do NOT commit
  <topic>/
    <name>.Notebook/     ← built by build.py, consumed by deploy.py REST upload
```

One topic subfolder per data source or business domain (e.g. `workspace/lux_energy_price/`). Stems must be unique across all subfolders because Fabric display names are flat.

## Notebook Workflow

```
author  →  build  →  deploy (REST)  →  smoke test  →  fetch  →  human commits via Fabric UI
  .py        fabric_notebooks/           Fabric       (exec+monitor)  workspace/<topic>/<name>.Notebook/
```

Deploy and smoke test are separate steps:
- Deploy (on source change): `python tool/notebook/deploy.py deploy <name> <workspace_id>`
- Smoke test (trigger existing notebook): Windows `tool\notebook\smoke-test.ps1 -Notebook <name>` · Linux/Mac `tool/notebook/smoke-test.sh --notebook <name>`
- Fetch after a passing run: `python tool/notebook/deploy.py fetch <name> <workspace_id>`

The smoke test never deploys. It triggers a job on whatever is already in Fabric and reports STATUS. After fetch, stop and report to the orchestrator — never run `git add`, `git rm`, or `git commit`. The human manages all git commits via the Fabric UI Git integration.

## tool/ layout

| Directory | Invoked by | Purpose |
|---|---|---|
| `tool/setup/` | Human (once) | `setup.ps1/sh` environment check · `fab-sandbox` authenticated Fabric CLI wrapper · `fabric-inventory-readonly` read-only workspace/item lookup |
| `tool/data/` | Developer agent | `mock-data-generator.py` creates deterministic synthetic CSV files under `data/sandbox/` when no real source is available; optional engines support Faker, Mimesis, and sklearn |
| `tool/notebook/` | Developer agent | `build.py` compile `.py` → `.Notebook` · `deploy.py` deploy/exec/fetch via REST · `smoke-test.ps1/sh` trigger and monitor |
| `tool/lakehouse/` | Developer agent | `list-tables.py` list all lakehouse tables with column names and types |
| `tool/semantic-model/` | Developer agent | `inspect.py` list and inspect semantic models — tables, columns, DAX measures, relationships |
| `tool/pipeline/` | Developer agent | `manage.py` create, deploy, run, and monitor a Data Factory pipeline that chains all topic notebooks |
| `tool/validate/` | Developer agent | `pipeline-lineage.py` staging-path consistency (run before every build) · `source-contract.py` contracts/ YAML shape check |
| `tool/mcp/` | Infrastructure | MCP server exposing Fabric CLI commands to agents |
| `tool/pre-commit-check.ps1/sh` | Developer agent | Runs all pre-commit validators before committing |

## Operating Rules

- Sandbox Fabric work only unless an operator explicitly approves production handoff.
- Never ask for, echo, store, or commit credentials, tokens, connection strings, or real Fabric IDs.
- Never commit `.env`, data files, logs, or `fabric_notebooks/` build artifacts.
- Humans must create the Fabric **workspace** and any **lakehouses** first and provide their names/IDs in `.env`. Agents may create or update **notebook items and workspace folders** automatically via `tool/notebook/deploy.py`.
- Source contracts belong in notebook `# %% [contract]` cells as Python dataclasses, not YAML files.
- Thresholds belong in notebook `# %% [parameters]` cells so Fabric pipeline parameters can override them.
- Keep download, ingestion, and data quality separate: `download_<source>.py` fetches, `bronze_<source>.py` ingests only new files, `dq_bronze_<source>.py` validates.
- If no source files exist for a new or demo topic, generate synthetic sandbox data using the **mock-data** skill (`python tool/data/mock-data-generator.py`). Always pass `--schema '<json>'` or `--schema-file <path>` derived from the target table — there are no default schemas. Use `--engine faker` for realistic PII-shaped values, `--engine mimesis` for high-volume generation, or `--engine sklearn` for controlled ML fixtures. See `.agents/skills/mock-data/SKILL.md` for the full engine selection guide and column type reference.

## Pipeline Structure

Every data source topic requires exactly three notebooks. No exceptions.

| Notebook | Naming | Responsibility |
|---|---|---|
| Download | `download_<source>.py` | Call source API → skip existing sandbox files → save raw files as-is. No Spark. No Delta writes. Print: existing / downloaded / failed counts. |
| Ingestion | `bronze_<source>.py` | Read sandbox files → compare against Bronze Delta table → process only new files → MERGE or partition-overwrite. Never full-overwrite. Print: new files processed, rows written, table row count. |
| Data quality | `dq_bronze_<source>.py` | Great Expectations checks: row count > 0, no null PKs, no duplicate PKs, schema match, business sanity. Print structured PASS/FAIL per check. Raise on any FAIL. |

A single notebook that downloads + ingests + overwrites is always wrong. The developer agent creates stubs for all three; the tester agent owns and fills `dq_bronze_<source>.py`.

## Skills

Use repo skills in `.agents/skills/`:

- `fabric-ingest` for source-to-Bronze ingestion.
- `fabric-transform` for Silver transformations and MERGE patterns.
- `fabric-model` for Gold facts, dimensions, KPIs, and semantic models.
- `fabric-validate` for independent DQ checks.
- `fabric-notebook-loop` for local `.py` to Fabric notebook iteration.
- `fabric-ops` for orchestration, VACUUM, inventory, and platform operations.
- `fabric-pipeline` for creating, deploying, and testing the Data Factory pipeline that chains all topic notebooks end-to-end.
- `mock-data` for generating deterministic synthetic sandbox CSV files when no real source exists.
- `semantic-model` for listing and inspecting Fabric Semantic Models (tables, DAX measures, relationships) before writing DAX or mapping Gold outputs to KPIs.

## Agents

Project-scoped Codex custom agents live in `.codex/agents/*.toml`. Use the role that matches the work:

- `orchestrator` scopes and routes.
- `developer` implements.
- `tester` validates independently.
- `operator` reviews security, PII, access, and production handoff.

## RTK Token Optimizer

RTK reduces shell output token consumption 60–90%. It is installed by `tool/setup/setup.sh` / `tool/setup/setup.ps1`.

Codex has no Bash hook, so prefix shell commands manually with `rtk` — it applies its filter if one exists, otherwise passes the command through unchanged:

- `rtk git status` · `rtk git log` · `rtk git diff`
- `rtk pytest` · `rtk ruff check` · `rtk pip`
- `rtk fab` for Fabric CLI commands

Use `rtk gain` to see token savings and `rtk discover` to find new opportunities.

Note: Claude Code sessions handle RTK automatically via the Bash hook — no manual prefix needed there.
