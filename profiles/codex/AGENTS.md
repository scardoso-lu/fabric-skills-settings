# Microsoft Fabric Data Engineering - Codex Profile

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

## Session Start - Run Every Session, In Order

0. **Mandatory setup gate - before accepting any Fabric work, verify `.env`, `fab`, and `fab auth`, and confirm the active workspace:**

   | Check | Pass | Fail - stop and show this |
   |---|---|---|
   | `.env` exists | file present | Human runs setup: Windows `.\tool\setup\setup.ps1` or Linux/Mac `bash tool/setup/setup.sh` |
   | `fab` reachable | Windows: `tool\setup\fab-sandbox.ps1 --version` exits 0; Linux/Mac: `bash tool/setup/fab-sandbox --version` exits 0 | Human runs setup; it installs `ms-fabric-cli` via `uv tool install ms-fabric-cli` |
   | `fab` authenticated | Windows: `tool\setup\fab-sandbox.ps1 api workspaces --output_format json` exits 0; Linux/Mac: `bash tool/setup/fab-sandbox api workspaces --output_format json` exits 0 | Windows: `tool\setup\fab-sandbox.ps1 auth login`; Linux/Mac: `bash tool/setup/fab-sandbox auth login`. If the check fails due to network restriction, escalate and request network access before retrying. |
   | Workspace registry | `workspaces.json` present in project root | Run `python tool/workspace/init.py` — queries the Fabric API and writes the complete workspace and resource registry |
   | Active workspace set | `workspaces.json` has `"active"` field that is not null | Run `python tool/workspace/switch.py list`, then `python tool/workspace/switch.py <displayName>` |
   | Active workspace confirmed | Human has confirmed the active workspace this session | Show `workspaces.json["active"]` value; **stop and ask**: "Active workspace is `<displayName>`. Proceed with this workspace?" — do not start any build, deploy, or pipeline action until confirmed |

   Do **not** read `.env` contents or print values. Check only that the file and key names are present. Do **not** echo workspace IDs or resource IDs — refer to workspaces and resources by `displayName` only.

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
    semantic-model/      <- TMDL definitions for any Power BI semantic model exposing topic tables
      <model>.tmdl       <- table + measure definitions (source of truth)
      README.md          <- UI creation walkthrough

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
- Keep every layer in its own notebook: `download_<source>.py`, `bronze_<source>.py`, `dq_bronze_<source>.py`, then optionally `silver_<source>.py`, `dq_silver_<source>.py`, `features_<source>.py`, `dq_features_<source>.py`, `train_<source>.py`, `predict_<source>.py`. Never collapse two layers into one notebook.
- If no source files exist for a new or demo topic, use the `mock-data` skill and `python tool/data/mock-data-generator.py`. Always pass `--schema '<json>'` or `--schema-file <path>` derived from the target table.
- Silver and downstream notebooks must NOT trust bronze column types — bronze tables drift via `mergeSchema=true`. Verify with `DESCRIBE TABLE bronze_<source>` before authoring, and derive computable columns (date, hour, quarter) from authoritative timestamps rather than casting bronze. See `memory/skill-fixes/silver-do-not-trust-bronze-types.md`.

## Pipeline Structure

Every data source topic starts with exactly three notebooks. Topics that proceed to analytics or ML add layers on top — each layer in its own notebook, never collapsed.

### Base layer (always required)

| Notebook | Naming | Responsibility |
|---|---|---|
| Download | `download_<source>.py` | Call source API, skip existing sandbox files, save raw files as-is. No Spark. No Delta writes. Print existing, downloaded, and failed counts. |
| Ingestion | `bronze_<source>.py` | Read sandbox files, compare against Bronze Delta table, process only new files, then MERGE or partition-overwrite. Never full-overwrite. |
| Data quality | `dq_bronze_<source>.py` | Great Expectations checks for row count, null PKs, duplicate PKs, schema match, and business sanity. Print structured PASS/FAIL per check and raise on any failure. |

### Silver layer (optional — clean and conformed)

| Notebook | Naming | Responsibility |
|---|---|---|
| Silver transform | `silver_<source>.py` | SQL-first MERGE from bronze into `silver_<source>` Delta. Cast all columns explicitly. Dedup by PK keeping latest `_ingest_ts`. Drop null-PK rows with a logged count (never silent). Derive computable columns from authoritative timestamps; do NOT cast bronze columns whose type may have drifted. |
| Silver DQ | `dq_silver_<source>.py` | Row count, no null PKs, no duplicate PKs, schema match, business range checks. PASS/FAIL with raise. |

### ML layer (optional — forecasting / scoring)

| Notebook | Naming | Responsibility |
|---|---|---|
| Features | `features_<source>.py` | Build feature Delta table from silver. Lag columns, rolling stats, calendar attributes. MERGE on PK. |
| Features DQ | `dq_features_<source>.py` | PK uniqueness, target presence, lag-coverage thresholds, schema match. |
| Train | `train_<source>.py` | Train model, log params/metrics/artifact to MLflow, register model. **Runs interactively in Fabric UI only** — SPN-triggered runs fail with `MwcTokenValidationException`. See `memory/skill-fixes/fabric-mlflow-spn-blocked.md`. MLflow experiment names: only `[A-Za-z0-9_-]`, must start with letter/digit. See `memory/skill-fixes/fabric-mlflow-experiment-name.md`. |
| Predict | `predict_<source>.py` | Load registered model from MLflow, score the forecast horizon, write `forecast_<source>` Delta. Also runs interactively when it uses `models:/.../latest`. For closed-loop scoring, switch persistence to `joblib` under `Files/models/`. |

A single notebook that combines two of these responsibilities is always wrong. The developer agent may create DQ notebook scaffolds; the tester agent owns independent validation logic and final DQ validation.

## Smoke-test Diagnostics

`tool/notebook/deploy.py monitor` reports only the generic Spark failure message; it does **not** surface cell-level tracebacks. When a smoke test prints `System cancelled the Spark session due to statement execution failures`, do not guess at fixes — open the failed run in the Fabric UI for the cell traceback, instrument the source `.py` with `try/except` + `traceback.format_exc()`, or bisect by commenting cells. See `memory/skill-fixes/smoke-test-cell-errors.md`.

## Semantic Models

Semantic models (Power BI datasets) live under `workspace/<topic>/semantic-model/` and have two files:

- `<model>.tmdl` — authoritative TMDL definition: column mappings, format strings, hidden columns, DAX measures
- `README.md` — UI walkthrough to create the Direct Lake model from the underlying lakehouse table and paste the TMDL

Per the `semantic-model` skill, **agents do not create or modify semantic models via REST API**. Author TMDL in the repo as the source of truth; humans create the Direct Lake model in the Fabric UI ("New semantic model" from the lakehouse) and paste the TMDL via the editor's TMDL view. Re-runs of the source predict/transform notebooks update the model via Direct Lake automatically.

Direct Lake limitations to respect when authoring TMDL:
- No calculated columns — every visible column must come from the underlying Delta table.
- Measures (pure DAX) are fully supported.
- Hide engineering/lineage columns (`_ingest_ts`, lag columns, raw tracking fields) via `isHidden`.

## Skills

Use repo skills in `.agents/skills/`:

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

Project-scoped Codex custom agents live in `.codex/agents/*.toml`. Use the role that matches the work:

- `orchestrator` scopes and routes.
- `developer` implements.
- `tester` validates independently.
- `operator` reviews security, PII, and access.

## RTK Token Optimizer

RTK reduces shell output token consumption. It is installed by `tool/setup/setup.sh` / `tool/setup/setup.ps1`.

Codex has no Bash hook, so prefix shell commands manually with `rtk`. It applies its filter if one exists, otherwise passes the command through unchanged:

- `rtk git status`, `rtk git log`, `rtk git diff`
- `rtk pytest`, `rtk ruff check`, `rtk pip`
- `rtk bash tool/setup/fab-sandbox ...` or `rtk powershell -File tool/setup/fab-sandbox.ps1 ...` for Fabric CLI checks

Do not call raw `fab`. Use `rtk gain` to see token savings and `rtk discover` to find new opportunities.

Claude Code sessions handle RTK automatically through the Bash hook, so manual `rtk` prefixes are Codex-specific.
