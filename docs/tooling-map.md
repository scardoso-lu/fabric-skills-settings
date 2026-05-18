# Tooling Map

This map shows the current source-package relationships between profile guidance, installed skills, installed rules, and target-repo tools.

> Scope: source package and installed target layout. The installer copies `profiles/skills/` to `.agents/skills/` for Codex and `.claude/skills/` for Claude, copies `rules/` into target repos as `memory/rules/`, and copies `profiles/shared/project-layout/tool/` as `tool/`.

```mermaid
flowchart LR
  subgraph G["Installed guidance"]
    g_codex["AGENTS.md"]
    g_claude["CLAUDE.md"]
    g_memory["memory/MEMORY.md"]
    g_rules["memory/rules/*.md"]
    g_mcp["Codex MCP config"]
  end

  subgraph S["Installed skills"]
    s_ingest["fabric-ingest"]
    s_transform["fabric-transform"]
    s_model["fabric-model"]
    s_validate["fabric-validate"]
    s_nbloop["fabric-notebook-loop"]
    s_ops["fabric-ops"]
    s_pipe["fabric-pipeline"]
    s_mock["mock-data"]
    s_sem["semantic-model"]
    s_other["document / response skills"]
  end

  subgraph SETUP["tool/setup/"]
    t_setup["setup.ps1 / setup.sh\nhuman only"]
    t_sandbox["fab-sandbox.ps1 / fab-sandbox"]
    t_inventory["fabric-inventory-readonly"]
  end

  subgraph NOTEBOOK["tool/notebook/"]
    t_build["build.py"]
    t_deploy["deploy.py"]
    t_smoke["smoke-test.ps1 / smoke-test.sh"]
  end

  subgraph PIPELINE["tool/pipeline/"]
    t_manage["manage.py"]
  end

  subgraph DATA["tool/data/"]
    t_mock["mock-data-generator.py"]
  end

  subgraph INSPECT["inspection tools"]
    t_lake["tool/lakehouse/list-tables.py"]
    t_sem["tool/semantic-model/inspect.py"]
  end

  subgraph VALIDATE["validation tools"]
    t_lineage["tool/validate/pipeline-lineage.py"]
    t_precommit["tool/pre-commit-check.ps1 / .sh"]
  end

  subgraph MCP["tool/mcp/"]
    t_mcp["server.py"]
  end

  g_codex -- "mandatory setup gate\n(.env, fab, fab auth)" --> t_sandbox
  g_claude -- "session setup gate" --> t_sandbox
  g_memory --> g_rules
  g_rules -- "Fabric API access must use wrapper" --> t_sandbox
  g_mcp --> t_mcp

  s_ingest -- "pre-build lineage check" --> t_lineage
  s_transform -- "developer-owned\nDE-06 MERGE/upserts" --> g_rules
  s_transform -- "writes Silver/Gold notebooks" --> s_nbloop
  s_model -- "developer-owned\nFP-08 Gold design" --> g_rules
  s_model -- "aligns KPIs and semantic outputs" --> t_sem
  s_validate -- "tester-owned\nDE-04 quality gates" --> g_rules
  s_validate -- "writes/runs DQ notebooks" --> s_nbloop
  s_nbloop --> t_build
  s_nbloop --> t_deploy
  s_nbloop --> t_smoke
  s_nbloop -- "completion check" --> t_precommit
  s_ops --> t_lake
  s_ops --> t_inventory
  s_ops -- "Fabric API operations" --> t_sandbox
  s_pipe --> t_manage
  s_mock --> t_mock
  s_sem --> t_sem

  t_setup -. "not agent-run" .- g_codex
  t_setup -. "not agent-run" .- g_claude
  t_precommit --> t_lineage
  t_smoke -- "exec + monitor" --> t_deploy
  t_deploy -- "Fabric CLI/API through wrapper" --> t_sandbox
  t_manage -- "Fabric CLI/API through wrapper" --> t_sandbox
  t_lake -- "auth through wrapper" --> t_sandbox
  t_inventory -- "read-only Fabric API through wrapper" --> t_sandbox
  t_mcp -- "Fabric API through wrapper" --> t_sandbox
```

## Human-Only Boundary

| Tool | Boundary |
|---|---|
| `tool/setup/setup.ps1` / `tool/setup/setup.sh` | Human-triggered bootstrap only. Agents verify setup state and report blockers; they do not re-run setup or attempt setup repair. |

## Wrapper Boundary

All Fabric CLI/API access in installed guidance must route through `tool/setup/fab-sandbox.ps1` on Windows or `bash tool/setup/fab-sandbox` on Linux/Mac. Guidance should not show raw `fab auth`, `fab api`, or PATH-based Fabric CLI discovery.

## Skill-to-Tool Summary

| Skill or guidance | Tool relationship |
|---|---|
| `fabric-ingest` | Runs `tool/validate/pipeline-lineage.py` before notebook build. |
| `fabric-transform` | Wired to the developer agent and DE-06 for Silver/Gold Spark transformations and MERGE patterns; build/deploy still runs through `fabric-notebook-loop`. |
| `fabric-model` | Wired to the developer agent and FP-08 for Gold facts, dimensions, KPIs, and semantic-model-aligned outputs. |
| `fabric-validate` | Wired to the tester agent and DE-04 for independent DQ notebook authoring and validation. |
| `fabric-notebook-loop` | Uses notebook build, deploy, smoke-test, fetch/monitor flows, then `tool/pre-commit-check`. |
| `fabric-ops` | Uses read-only inventory, lakehouse listing, and fab-sandbox for safe Fabric operations. |
| `fabric-pipeline` | Uses `tool/pipeline/manage.py`; that helper uses fab-sandbox for Fabric access. |
| `mock-data` | Uses `tool/data/mock-data-generator.py`. |
| `semantic-model` | Uses `tool/semantic-model/inspect.py`. |
| Codex MCP config | Points to `tool/mcp/server.py`; the server uses the same wrapper boundary. |
| Developer agent guidance | Runs `tool/pre-commit-check.ps1` or `tool/pre-commit-check.sh` before reporting complete. |

## Non-Fabric Tool Skills

These skills do not invoke repository `tool/` scripts and are not Fabric notebook authoring or validation workflows:

| Skill | Reason |
|---|---|
| `prd` | Requirements document generation only. |
| `grill-me` | Plan interrogation only. |
| `git-commit` | Uses `git`, not repository `tool/` scripts. |
| `caveman` | Response-format mode only. |

## Notebook Workflow Chain

```text
author notebook .py
  -> tool/notebook/build.py
  -> tool/notebook/deploy.py
  -> tool/notebook/smoke-test.ps1 or smoke-test.sh
  -> tool/notebook/deploy.py exec/monitor
  -> tool/pre-commit-check.ps1 or pre-commit-check.sh

Fabric calls inside the chain go through tool/setup/fab-sandbox.
```
