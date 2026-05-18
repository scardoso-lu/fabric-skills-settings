# Tooling Map

Shows which **skills** call which **tools**, which **rules** mandate specific tools, and which **tools** depend on other tools.

> **Scope**: source-package relationships. `rules/` lives in the source repo only and is not installed to target repos — rule codes (SEC-*, FP-*, DE-*) are embedded inline in skill and agent guidance instead.

```mermaid
flowchart LR
  subgraph SK["Skills — .claude/skills/"]
    s_ingest["fabric-ingest"]
    s_nbloop["fabric-notebook-loop"]
    s_ops["fabric-ops"]
    s_pipe["fabric-pipeline"]
    s_mock["mock-data"]
    s_sem["semantic-model"]
  end

  subgraph R["Rules — rules/ ⚠ source-only"]
    r_de["data-engineering.md"]
    r_fp["fabric-platform.md"]
    r_sec["security.md"]
  end

  subgraph TN["tool/notebook/"]
    t_build["build.py"]
    t_deploy["deploy.py"]
    t_smoke["smoke-test.ps1/sh"]
  end

  subgraph TP["tool/pipeline/"]
    t_manage["manage.py"]
  end

  subgraph TD["tool/data/"]
    t_mock["mock-data-generator.py"]
  end

  subgraph TL["tool/lakehouse/"]
    t_list["list-tables.py"]
  end

  subgraph TSM["tool/semantic-model/"]
    t_inspect["inspect.py"]
  end

  subgraph TV["tool/validate/"]
    t_lineage["pipeline-lineage.py"]
    t_contract["source-contract.py ⚠ no skill calls this"]
  end

  subgraph TST["tool/setup/"]
    t_sandbox["fab-sandbox.ps1/sh"]
    t_inventory["fabric-inventory-readonly"]
  end

  %% Skills → Tools
  s_ingest -- "run before build" --> t_lineage
  s_nbloop --> t_build
  s_nbloop --> t_deploy
  s_nbloop --> t_smoke
  s_ops --> t_list
  s_ops -- "monitor" --> t_deploy
  s_pipe --> t_manage
  s_mock --> t_mock
  s_sem --> t_inspect

  %% Rules → Tools  (FP-03/04 mandate the notebook toolchain)
  r_fp -- "FP-03: build step" --> t_build
  r_fp -- "FP-03/04: deploy + monitor" --> t_deploy

  %% Tools → Tools
  t_smoke -- "calls exec" --> t_deploy
  t_deploy -- "fab CLI" --> t_sandbox
  t_manage -- "fab CLI" --> t_sandbox
  t_list -- "fab auth token" --> t_sandbox
  t_inventory -- "fab API" --> t_sandbox
```

## Skills with no direct tool calls

These skills guide notebook code generation but do not invoke `tool/` scripts directly:

| Skill | Why no tool call |
|---|---|
| `fabric-transform` | Silver/Gold Spark code is written into notebooks; build/deploy handled by `fabric-notebook-loop` |
| `fabric-model` | Gold DAX/dimensional patterns written into notebooks |
| `fabric-validate` | GX code written into dq_*.py notebooks; run via the notebook loop |
| `prd` | Document generation only |
| `grill-me` | Q&A interrogation only |
| `git-commit` | Uses `git` CLI, not `tool/` scripts |
| `caveman` | Response-compression mode only |

## Tool → Tool dependency chain (notebook workflow)

```
author .py  →  build.py  →  deploy.py  →  smoke-test  →  deploy.py (exec+monitor)
                                 ↓
                           fab-sandbox  ←  also called by manage.py, list-tables.py, fabric-inventory-readonly
```
