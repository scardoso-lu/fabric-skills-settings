# Workflow — agents, skills, and tools

What you get in the **target repo** after `fabric-agents install` runs. Reads top-down: a request reaches an agent, the agent picks a skill, the skill drives one or more local tools, the tools talk to Microsoft Fabric.

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

    TOOLS["fabric-cli proxy (Bash, target-side)<br/>━━━━━━━━━━<br/>notebook — build · deploy · smoke-test · fetch<br/>lakehouse — list-tables<br/>pipeline — manage<br/>workspace — init · switch · transfer · pick<br/>lint · precommit<br/>━━━━━━━━━━<br/>fabric-server MCP<br/>data_mock_generate · semantic_model_* · pipeline_lineage_check · graph_*"]:::tool
    TOOLS --> FAB

    FAB[("Microsoft Fabric<br/>workspace · REST API · CLI")]:::ext
```

## What the colours mean

| Colour | Layer | Where it lives in the target |
|---|---|---|
| 🟠 Orange | Agents (4) | `.claude/agents/*.md` and `.codex/agents/*.toml` |
| 🔵 Blue | Skills (14) | served from the `fabric-server` graph via `graph_get_node('skills/<name>')` |
| 🟢 Green | Tools | `fabric-cli` subcommands (Bash, target-side `tool/`) + `fabric-server` MCP tools |
| 🔴 Red | External | Microsoft Fabric workspace (CLI + REST API) |

## What each command does

`fabric-cli` (Bash, runs the target-side `tool/` scripts):

| Command | Used by |
|---|---|
| `fabric-cli notebook {build,deploy,smoke-test}` | Most data-engineering skills |
| `fabric-cli lakehouse list-tables` | `fabric-transform`, `fabric-validate` |
| `fabric-cli pipeline manage` | `fabric-pipeline` |
| `fabric-cli workspace {init,switch,transfer,pick}` | `fabric-ops`, all agents at session start |
| `fabric-cli lint` / `fabric-cli precommit` | pre-completion validation |

`fabric-server` MCP (no `ms-fabric-cli` needed):

| Tool | Used by |
|---|---|
| `data_mock_generate` | `mock-data`, `fabric-ingest` (when no real source) |
| `semantic_model_list` / `semantic_model_show` | `semantic-model`, `fabric-model` |
| `pipeline_lineage_check` | `fabric-validate`, pre-commit check |
| `graph_*` | all agents (knowledge graph read/write) |

`tool/setup/setup.{ps1,sh}` is human-run at install time; agents do not invoke it. The knowledge graph + MCP tools are served by the `fabric-server` Docker container — see [knowledge-graph.md](knowledge-graph.md).
