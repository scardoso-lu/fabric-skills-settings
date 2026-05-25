# Workflow — agents, skills, and tools

What you get in the **target repo** after `setup.ps1` (or `install-fabric-agent`) runs. Reads top-down: a request reaches an agent, the agent picks a skill, the skill drives one or more local tools, the tools talk to Microsoft Fabric.

```mermaid
flowchart TD
    classDef agent fill:#fff4e6,stroke:#cc7700,stroke-width:2px,color:#000
    classDef skill fill:#e6f0ff,stroke:#0055cc,color:#000
    classDef tool fill:#e6ffe6,stroke:#00aa00,color:#000
    classDef ext fill:#fde4e1,stroke:#cc0000,color:#000

    H([Human request])
    H --> ORC

    ORC["orchestrator<br/>━━━━━━━━━━<br/>scope · route · handoff<br/>uses: prd · grill-me · caveman"]:::agent
    ORC --> SUBS

    SUBS["Sub-agents (orchestrator picks one)<br/>━━━━━━━━━━<br/>developer · tester · operator"]:::agent
    SUBS --> SKILLS

    SKILLS["Skills by sub-agent<br/>━━━━━━━━━━<br/>developer ⇒ fabric-ingest · fabric-transform · fabric-model<br/>fabric-notebook-loop · fabric-pipeline<br/>mock-data · semantic-model · git-commit<br/>tester ⇒ fabric-validate · fabric-notebook-loop<br/>operator ⇒ fabric-ops · rtk"]:::skill
    SKILLS --> TOOLS

    TOOLS["Local tools in target repo<br/>━━━━━━━━━━<br/>tool/notebook/ — build · deploy · smoke-test · fetch<br/>tool/lakehouse/ — list-tables<br/>tool/semantic-model/ — inspect<br/>tool/pipeline/ — manage<br/>tool/workspace/ — init · switch · transfer<br/>tool/data/ — mock-data-generator<br/>tool/validate/ — pipeline-lineage<br/>tool/setup/ — fab-sandbox CLI wrapper<br/>mcp/ — fabric & fabric-graph servers"]:::tool
    TOOLS --> FAB

    FAB[("Microsoft Fabric<br/>workspace · REST API · CLI")]:::ext
```

## What the colours mean

| Colour | Layer | Where it lives in the target |
|---|---|---|
| 🟠 Orange | Agents (4) | `.claude/agents/*.md` and `.codex/agents/*.toml` |
| 🔵 Blue | Skills (14) | `.claude/skills/<name>/SKILL.md`, `.agents/skills/<name>/SKILL.md` |
| 🟢 Green | Tools (8 dirs) | `tool/<area>/*.py` and `*.sh`/`*.ps1` |
| 🔴 Red | External | Microsoft Fabric workspace (CLI + REST API) |

## What each tool does

| Tool dir | Scripts | Used by |
|---|---|---|
| `tool/notebook/` | `build.py`, `deploy.py`, `smoke-test.{ps1,sh}` | Most data-engineering skills |
| `tool/data/` | `mock-data-generator.py` | `mock-data`, `fabric-ingest` (when no real source) |
| `tool/lakehouse/` | `list-tables.py` | `fabric-transform`, `fabric-validate` |
| `tool/semantic-model/` | `inspect.py` | `semantic-model`, `fabric-model` |
| `tool/pipeline/` | `manage.py` | `fabric-pipeline` |
| `tool/workspace/` | `init.py`, `switch.py`, `transfer.py` | `fabric-ops`, all agents at session start |
| `tool/validate/` | `pipeline-lineage.py` | `fabric-validate`, pre-commit check |
| `tool/setup/` | `fab-sandbox{,.ps1}`, `fabric-inventory-readonly{,.ps1}`, `setup.{ps1,sh}` | Humans once at install; agents call `fab-sandbox` for every Fabric CLI access |

`tool/setup/setup.{ps1,sh}` and `tool/pre-commit-check.{ps1,sh}` are human-run; agents do not invoke them. `tool/graph/` and `mcp/` are infrastructure for the knowledge-graph layer — see [knowledge-graph.md](knowledge-graph.md).
