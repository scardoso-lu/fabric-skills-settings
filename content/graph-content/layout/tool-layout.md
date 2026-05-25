---
name: tool-layout
description: Map of tool/ subdirectories with their owner agent and purpose. Use to pick the right tool before invoking shell commands.
kind: content
links:
  - graph-content/workflow/notebook-workflow
  - graph-content/workflow/workspace-management
---

# Tool layout

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
| `mcp/` | Infrastructure | MCP servers (top-level, parallel to `tool/`): `server.py` (Fabric CLI wrapper), `graph-server.py` (knowledge graph) |
| `tool/graph/` | Infrastructure | networkx-backed knowledge graph indexing the agent profile vault; consumed by `graph-server.py` |
| `tool/pre-commit-check.ps1` / `tool/pre-commit-check.sh` | Developer agent | Runs completion validators before reporting done |
