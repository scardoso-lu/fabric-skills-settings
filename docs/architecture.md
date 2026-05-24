# Architecture

Fabric Agent Pack installs two MCP servers into every target repository. Together they give Claude Code and Codex a structured way to discover project knowledge and act against a Microsoft Fabric workspace.

| Server | Role | Module |
|---|---|---|
| `fabric` | Wraps the Fabric CLI: list/get items, authenticated REST API calls. | `tool/mcp/server.py` |
| `fabric-graph` | RAG knowledge graph: BM25 + 1-hop edge-aware read tools and full CRUD over nodes and edges. | `tool/mcp/graph-server.py` |

The installed `CLAUDE.md` / `AGENTS.md` entrypoints are minimal (~30 lines). They tell the agent to call `graph_get_entry` first and then traverse the graph; all operational knowledge — setup gate, session-start order, workflow steps, skills, tools, rules — is encoded as graph nodes, not as static markdown for the agent to read directly.

## Diagram 1 — `fabric-graph`: the RAG flow

How knowledge enters the graph, gets indexed, and is served to the agent.

```mermaid
flowchart TD
  subgraph Sources["Knowledge sources (source package)"]
    direction TB
    GC["profiles/shared/graph-content/**/*.md<br/>(entry, session, workflow, layout,<br/>diagnostics, semantic, indexes,<br/>integrations)"]
    SK["profiles/skills/*/SKILL.md<br/>(+ sections/)"]
    RL["rules/*.md<br/>(security, data-engineering,<br/>fabric-platform)"]
    SF["memory/skill-fixes/*.md<br/>(runtime feedback)"]
  end

  Sources -- "frontmatter links: +<br/>auto-extracted path mentions" --> Builder
  Builder["bin/build-graph.py<br/>(uses tool/graph/builder.py)"]
  Builder --> Artifacts

  subgraph Artifacts["memory/.graph/ (gitignored)"]
    direction TB
    GJ[("graph.json<br/>NetworkX DiGraph")]
    BM[("graph-bm25.pkl<br/>BM25 index")]
    SVG[("materialized-graph.svg<br/>(visualization)")]
  end

  GJ --> Server
  BM --> Server
  Server["fabric-graph MCP<br/>(tool/mcp/graph-server.py)"]

  subgraph ReadTools["Read tools"]
    direction TB
    T1["graph_get_entry<br/>(first call of every session)"]
    T2["graph_get_node<br/>(read one node by id)"]
    T3["graph_get_linked<br/>(1-hop neighbors, optional kind filter)"]
    T4["graph_search<br/>(BM25 + 1-hop edge-aware re-rank)"]
    T5["graph_list_kinds"]
  end

  subgraph WriteTools["CRUD tools (atomic rebuild after each write)"]
    direction TB
    W1["graph_create_node"]
    W2["graph_update_node"]
    W3["graph_delete_node"]
    W4["graph_add_edge"]
    W5["graph_remove_edge"]
  end

  Server --> ReadTools
  Server --> WriteTools
  WriteTools -. "tool/graph/writes.py<br/>re-runs builder + BM25 +<br/>atomic file-lock swap" .-> Builder

  Agent(["Claude Code / Codex agent"]) --> ReadTools
  Agent --> WriteTools
```

Key properties:

- **Single source of truth**: all knowledge lives in markdown files under known paths. The graph is a derived artifact, never edited by hand.
- **BM25 + edges**: `graph_search` returns BM25 hits and re-ranks by 1-hop edge proximity, so a hit on a rule surfaces its linked skill.
- **No static project state**: there is no `memory/project.md`, `memory/runbooks/`, `memory/security/`, or `templates/` folder. Per-pipeline state, incident notes, and security reviews are graph nodes created via `graph_create_node`.
- **Capability graph (derived)**: a second build (`bin/build-agent-capability-graph.py`) groups the same nodes under the four subagents (orchestrator, developer, tester, operator) using each agent's frontmatter `links:` + `skills:` as the source of truth. It is an inspection artifact, not used at runtime for routing.

## Diagram 2 — Skills and tools inside each MCP server

What the agent reaches for. Skills are vendor-neutral markdown workflows under `profiles/skills/`; they shell out to runtime helpers under `tool/` and to MCP tools.

```mermaid
flowchart LR
  Agent(["Claude Code / Codex agent"])

  subgraph FabricMCP["fabric MCP - tool/mcp/server.py"]
    direction TB
    F1["fabric_list<br/>(items in workspace,<br/>optional type filter)"]
    F2["fabric_get<br/>(one item by name or id)"]
    F3["fabric_api_get<br/>(authenticated GET on<br/>Fabric REST API)"]
  end

  subgraph GraphMCP["fabric-graph MCP - tool/mcp/graph-server.py"]
    direction TB
    subgraph GR["Read"]
      G1[graph_get_entry]
      G2[graph_get_node]
      G3[graph_get_linked]
      G4[graph_search]
      G5[graph_list_kinds]
    end
    subgraph GW["CRUD"]
      G6[graph_create_node]
      G7[graph_update_node]
      G8[graph_delete_node]
      G9[graph_add_edge]
      G10[graph_remove_edge]
    end
  end

  subgraph Skills["Skills - profiles/skills/ -> .claude/skills/ + .agents/skills/"]
    direction TB
    SK_RTK["rtk<br/>token-optimizing shell proxy"]
    SK_ING["fabric-ingest<br/>Bronze ingestion"]
    SK_TRF["fabric-transform<br/>Silver/Gold MERGE"]
    SK_MOD["fabric-model<br/>Gold facts/dims/KPIs"]
    SK_VAL["fabric-validate<br/>DQ, schema drift, RI"]
    SK_NB["fabric-notebook-loop<br/>build/deploy/smoke"]
    SK_OPS["fabric-ops<br/>maintenance + VACUUM"]
    SK_PIPE["fabric-pipeline<br/>Data Factory orchestration"]
    SK_SEM["semantic-model<br/>DAX + measure inspection"]
    SK_MK["mock-data<br/>synthetic CSV staging"]
    SK_PRD["prd<br/>requirements shaping"]
    SK_GRL["grill-me<br/>plan interrogation"]
    SK_GIT["git-commit"]
    SK_CAV["caveman<br/>session-start sanity"]
  end

  subgraph RuntimeTools["Runtime helpers - tool/"]
    direction TB
    RT_NB["tool/notebook/<br/>build, deploy, smoke-test,<br/>fetch, run, monitor"]
    RT_PIPE["tool/pipeline/<br/>manage.py - create/run/status"]
    RT_LH["tool/lakehouse/<br/>list-tables.py"]
    RT_SEM["tool/semantic-model/<br/>inspect.py"]
    RT_DATA["tool/data/<br/>mock-data-generator.py"]
    RT_VAL["tool/validate/<br/>pipeline-lineage.py"]
    RT_SET["tool/setup/<br/>fab-sandbox, inventory"]
  end

  Agent --> GraphMCP
  Agent --> FabricMCP
  Agent --> Skills

  Skills --> RuntimeTools
  Skills -- "discover items and<br/>verify deployment" --> FabricMCP
  Skills -- "load workflow,<br/>persist state" --> GraphMCP

  RuntimeTools -. "Fabric REST API" .-> FabricMCP
```

Key properties:

- **Skills are workflows**, not code. They live as markdown under `profiles/skills/` and instruct the agent which `tool/` helpers and which MCP tools to call in what order.
- **`fabric` MCP** is a thin wrapper. It hides the Fabric CLI auth + REST plumbing so agents don't shell out to `fab` directly.
- **`fabric-graph` MCP** is both the read path (RAG retrieval over the project knowledge) and the write path (persistence for everything that used to live in `memory/project.md`, `memory/runbooks/`, `memory/security/`, or `templates/`).
- **Source-package split**: build-time graph code lives at `build/graph_build/` (visualize, agent_capabilities) and is used only by `bin/build-*.py`. Runtime code lives at `tool/graph/` and is what the MCP server loads in the target repo.

## Subagents

Four native subagents are installed alongside the entrypoint:

| Subagent | Owns | Reports to |
|---|---|---|
| `orchestrator` | Scoping, routing, human handoff | Human |
| `developer` | Notebooks, transforms, models, pipelines | `orchestrator` |
| `tester` | DQ, schema drift, RI, metric sanity | `orchestrator` |
| `operator` | Security review, secrets, access, supply chain | `orchestrator` |

Subagents are discovered by Claude and Codex from their native profile directories (`.claude/agents/*.md`, `.codex/agents/*.toml`). They are not primary graph nodes — the capability graph in `memory/.graph/agent-capabilities.json` is a derived inspection artifact only.

## Where things live

| Concern | Source | Installed location |
|---|---|---|
| Entry instructions | `profiles/claude/CLAUDE.md`, `profiles/codex/AGENTS.md` | Target repo root |
| Subagents | `profiles/{claude,codex}/agents/` | `.claude/agents/`, `.codex/agents/` |
| Skills | `profiles/skills/` | `.claude/skills/`, `.agents/skills/` |
| Rules | `rules/*.md` | `memory/rules/*.md` |
| Knowledge graph content | `profiles/shared/graph-content/` | `memory/graph-content/` |
| Seed memory | `profiles/shared/memory/` | `memory/` |
| Graph artifacts | (built at install / on-write) | `memory/.graph/` (gitignored) |
| MCP servers | `tool/mcp/` | `tool/mcp/` |
| Graph runtime | `tool/graph/` | `tool/graph/` |
| Graph build-time | `build/graph_build/` | **not installed** |
