---
name: tool-layout
description: Map of fabric-cli subcommands and fabric-server MCP tools with their owner agent and purpose. Use to pick the right interface before acting.
kind: content
links:
  - graph-content/workflow/notebook-workflow
  - graph-content/workflow/workspace-management
---

# Tool layout

Two interfaces front everything: the **`fabric-cli`** proxy (Bash, runs the
target-side `tool/` scripts) and the **`fabric-server`** MCP (graph + a few
Fabric helpers that run without `ms-fabric-cli`).

## `fabric-cli` (Bash, target-side)

| Command | Invoked by | Purpose |
|---|---|---|
| `fabric-cli workspace {init,switch,transfer,pick}` | Developer agent, orchestrator | `init` discovers all workspaces/resources from the Fabric API; `switch` sets the active workspace and writes resource IDs to `.env`; `transfer` moves notebooks/pipelines between workspaces; `pick` is the interactive picker |
| `fabric-cli notebook {build,deploy,smoke-test}` | Developer agent | `build` compiles `.py` to `.Notebook`; `deploy {deploy,run,exec,fetch,monitor}` deploys/executes/monitors/fetches through REST; `smoke-test` triggers and monitors a deployed notebook |
| `fabric-cli lakehouse list-tables` | Developer agent, tester agent | Lists lakehouse tables with column names and types |
| `fabric-cli pipeline manage` | Developer agent | Creates, deploys, runs, and monitors Data Factory pipelines that chain topic notebooks |
| `fabric-cli lint` | Developer agent | Deterministic lints (SEC-01 secrets, DE-09 Faker seed); pure Python, no fab |
| `fabric-cli precommit` | Developer agent | Aggregate pre-commit check before reporting done |

Environment bootstrap (`tool/setup/setup.{ps1,sh}`) is run once by the human at
install time; agents only verify the gate (see [[graph-content/entry]]).

## `fabric-server` MCP

| Tool | Invoked by | Purpose |
|---|---|---|
| `data_mock_generate` | Developer agent | Generates deterministic synthetic CSV test data when no real source exists |
| `semantic_model_list` / `semantic_model_show` | Developer agent, tester agent | Lists and inspects semantic models, measures, and relationships via `sempy.fabric` |
| `pipeline_lineage_check` | Developer agent | Validates staging-path consistency from uploaded notebook contents |
| `graph_*` | All agents | Knowledge-graph read/write tools |
