# Plan: Graph-Driven Knowledge Retrieval for Claude/Codex Profiles

Status: DRAFT — awaiting review before branch + implementation.
Author: assistant (sco@slg.lu)
Date: 2026-05-24

## 1. Goal

Replace the current "read every CLAUDE.md / AGENTS.md / MEMORY.md at session start" model with an autonomous knowledge-retrieval agent.

The agent's profile (`CLAUDE.md` / `AGENTS.md`) shrinks to a ~30-line entrypoint that knows **only one thing**: how to call a graph tool. All operational knowledge (setup gate, session-start rules, pipeline structure, skills, rules, templates, memory) lives as nodes in a networkx graph. The agent discovers what it needs by traversing the graph, never by guessing file names.

## 2. Non-goals

- No semantic / vector embeddings. Retrieval is lexical (BM25) + graph topology.
- No new database. Graph is a pickled / JSON networkx artifact on disk.
- No change to the installer surface area (still `bin/install-fabric-agent`, still `fabric_skills_settings`).
- No change to existing `tool/notebook`, `tool/pipeline`, `tool/lakehouse`, `tool/semantic-model`, `tool/data` semantics.
- No removal of the existing Fabric MCP server. The graph server is **additive**.

## 3. Architecture Overview

```
┌──────────────────────────────────────────────────────────┐
│ Source package (this repo)                                │
│                                                            │
│   profiles/claude/CLAUDE.md     ← 30-line entrypoint       │
│   profiles/codex/AGENTS.md      ← 30-line entrypoint       │
│                                                            │
│   profiles/shared/graph-content/   ← new tree (domain tree)│
│     entry.md                                                │
│     session/{session-start, operating-rules}.md             │
│     layout/{directory-layout, tool-layout}.md               │
│     workflow/{notebook-workflow, pipeline-structure,        │
│               workspace-management}.md                       │
│     diagnostics/smoke-test-diagnostics.md                   │
│     semantic/semantic-models.md                              │
│     indexes/{skills-index, agents-index}.md                 │
│     integrations/rtk.md                                      │
│                                                            │
│   profiles/skills/*/SKILL.md       ← existing, indexed     │
│   profiles/shared/memory/*.md      ← existing, indexed     │
│   profiles/shared/project-layout/memory/rules/*.md         │
│   rules/*.md   templates/*.md                              │
│                                                            │
│   tool/mcp/server.py            ← existing Fabric ops MCP  │
│   tool/mcp/graph-server.py      ← NEW knowledge graph MCP  │
│   tool/graph/                   ← NEW graph code           │
│     builder.py  store.py  search.py  schema.py             │
│                                                            │
│   bin/build-graph.py            ← NEW: build graph artifact│
│   bin/install-fabric-agent      ← UPDATED: invokes builder │
│   fabric_skills_settings/_installer.py  ← mirror update    │
└──────────────────────────────────────────────────────────┘
                          │ install
                          ▼
┌──────────────────────────────────────────────────────────┐
│ Target repo (after install)                               │
│                                                            │
│   CLAUDE.md / AGENTS.md         ← installed entrypoints    │
│   memory/graph-content/**/*.md  ← installed content tree   │
│   memory/.graph/graph.json      ← NEW: serialized graph    │
│   memory/.graph/graph-bm25.pkl  ← NEW: BM25 index          │
│   memory/MEMORY.md, memory/rules/*, memory/skill-fixes/*   │
│   .claude/skills/*  .agents/skills/*                       │
│   .claude/settings.local.json   ← registers BOTH MCP svrs  │
│   .codex/config.toml            ← registers BOTH MCP svrs  │
│   tool/mcp/server.py  tool/mcp/graph-server.py  tool/graph/│
└──────────────────────────────────────────────────────────┘
                          │ runtime
                          ▼
┌──────────────────────────────────────────────────────────┐
│ Claude Code / Codex session                                │
│                                                            │
│   Profile says: call mcp__fabric-graph__get_entry then traverse.  │
│   Agent calls graph_get_entry → entry node (setup gate).   │
│   Agent runs setup checks; on PASS, graph_get_linked(entry)│
│   → session-start, project, skills-index, ...              │
│   Agent traverses until it has enough to act.              │
│   Agent cites node IDs in its answer.                       │
└──────────────────────────────────────────────────────────┘
```

## 4. Locked Decisions

| # | Question | Decision |
|---|---|---|
| 1 | Profile minimalism | **Hard minimal**: ~30 lines, only graph tool usage. |
| 2 | Graph storage | **Built at install time**, shipped as `memory/graph.json` + `memory/graph-bm25.pkl` in target repo. |
| 3 | Node/edge model | **File-level nodes**; edges from `links:` frontmatter (curated) + auto-extracted path mentions and `[[wiki-links]]`. |
| 4 | Tool delivery | **New dedicated MCP server** `tool/mcp/graph-server.py`; existing Fabric MCP stays untouched. |
| 5 | Setup gate enforcement | **Entry node IS the gate**. `graph_get_entry()` returns the gate as its first content; profile rule is "follow entry node literally before any other action". |
| 6 | CRUD scope | **Full CRUD via graph tool**: create/update/delete nodes, add/remove edges. Each write touches the `.md` file AND atomically re-serializes `graph.json` + BM25. |
| 7 | Search backend | **Hybrid BM25 + 1-hop edge-aware re-ranking**. |
| 8 | Content tree | **New `profiles/shared/graph-content/`** for content split out of the old profile, organized as a **domain tree** (see §7); existing skills/rules/templates/memory indexed in place. |
| 9 | Edge bootstrap | **Auto-extract first, hand-curate second**. Build script parses raw path mentions (no `[[wiki-link]]` support — see Q2 below); frontmatter `links:` field adds curated structural edges on top. |
| 10 | Graph artifacts in git | **Gitignored** (`memory/.graph/`). Builder runs at install + on refresh. |
| 11 | Wiki-link syntax | **Dropped**. Curated edges are frontmatter `links:` only; auto-extraction reads raw path mentions in prose. Simpler grammar, no second syntax to teach. |
| 12 | Undo of agent writes | **No** `graph_undo`. Git is the undo mechanism. No `.md.bak` shadow files. |
| 13 | Skill file splitting | **Split skills > 150 lines by H2**, but **gated on a TDD baseline** (see Phase P5.5). Pre-split, capture the current per-skill content as a regression fixture; post-split, the split nodes must collectively cover the fixture and the graph traversal from `skills-index` must reach every section in ≤ 2 hops. Skills affected: `fabric-notebook-loop` (275), `fabric-ingest` (212), `fabric-transform` (202), `fabric-validate` (177), `prd` (143), `semantic-model` (142). |
| 14 | Codex `AGENTS.md` validator | **Rewrite `bin/validate-agent-guidance.py` in Phase P4** (see §12.1). Existing per-profile phrase/skill checks move to node-presence checks against `entry.md`, `session/session-start.md`, `session/operating-rules.md`, and `indexes/skills-index.md`. Profile checks become: ≤ 50 lines, must mention `mcp__fabric-graph__get_entry`, must NOT contain operational content. |
| 15 | Templates | **Indexed as nodes** (kind=`template`). Curated edges added from `rules/data-engineering`, `rules/fabric-platform`, `rules/security` to the templates they instantiate (e.g. `rules/security` → `templates/security-review`, `templates/access-review`). |
| 16 | MCP server name | **`fabric-graph`**. Tools appear as `mcp__fabric-graph__*`. Keeps the namespace distinct from any future generic graph server. |

## 5. Node & Edge Schema

### 5.1 Node

```python
@dataclass(frozen=True)
class Node:
    id: str               # canonical: "skills/fabric-transform" or "graph-content/entry"
    path: Path            # absolute path to .md file
    title: str            # H1 or frontmatter `name`
    description: str      # frontmatter `description` (one line)
    kind: str             # entry | content | skill | rule | template | memory | skill-fix | agent
    body: str             # full markdown body (loaded lazily, not stored on the graph)
    frontmatter: dict     # raw frontmatter
    mtime: float          # for freshness checks
```

Stored in networkx as `G.nodes[id]` attributes — `body` lives on disk, not in graph.json; only the metadata is serialized.

### 5.2 Edge

```python
@dataclass(frozen=True)
class Edge:
    src: str
    dst: str
    kind: str             # curated | auto-path | auto-wiki
    anchor: str | None    # optional H2 slug if the link targeted a section
```

### 5.3 Frontmatter contract (additive — backward compatible)

```yaml
---
name: fabric-transform                # existing
description: Silver/Gold transforms…  # existing
links:                                 # NEW (optional)
  - rules/data-engineering.md
  - memory/skill-fixes/silver-do-not-trust-bronze-types.md
  - skills/fabric-validate
---
```

Existing files without `links:` still work — auto-extraction supplies their edges. The validator emits a warning (not an error) on an orphan node (in-degree 0 AND out-degree 0).

## 6. MCP Tool Surface

All tools live on `mcp__fabric-graph__*`. Strict JSON in/out. No file paths are leaked; node IDs only.

### 6.1 Read

| Tool | Args | Returns |
|---|---|---|
| `graph_get_entry` | — | `{id, title, body, links: [id…]}` — the entry node |
| `graph_get_node` | `id: str` | `{id, title, body, kind, links: [id…]}` |
| `graph_get_linked` | `id: str, kinds?: [str]` | `[{id, title, description, kind, edge_kind}…]` 1-hop neighbors |
| `graph_search` | `query: str, k?: int=5` | `[{id, title, score, why_matched}…]` BM25 + edge re-rank |
| `graph_list_kinds` | — | `{entry: 1, content: 8, skill: 13, rule: 3, …}` map |

### 6.2 Write

| Tool | Args | Behavior |
|---|---|---|
| `graph_create_node` | `id, path, body, frontmatter, links?` | Writes the `.md` file, validates frontmatter, adds node + edges, re-pickles. Rejects duplicate IDs. |
| `graph_update_node` | `id, body?, frontmatter?` | Loads the file, applies changes, re-writes atomically (tmp + rename), re-pickles, re-indexes BM25 for that node. |
| `graph_delete_node` | `id, *, allow_orphans=False` | Refuses if other nodes link to it unless `allow_orphans=True` (forced cascade removes the dangling edges instead of failing). Removes the file. |
| `graph_add_edge` | `src, dst, kind="curated"` | Updates `links:` frontmatter on the src file. Refuses if `dst` doesn't exist. |
| `graph_remove_edge` | `src, dst` | Curated edges only — auto edges can only be removed by editing the prose that mentions the target. |

All writes are atomic against `graph.json`: the tool acquires an OS-level file lock (`fcntl` on POSIX, `msvcrt.locking` on Windows), writes the new graph to `graph.json.tmp`, fsyncs, renames over `graph.json`, releases the lock. Audit-logged the same way `tool/mcp/server.py` already does.

### 6.3 Diagnostics (optional, low priority)

| Tool | Args | Behavior |
|---|---|---|
| `graph_check_setup` | — | Runs the same gate checks (env, fab, workspaces.json, active). Returns structured PASS/FAIL. Lets future profiles delegate the gate to Python if we ever regret the entry-node approach. |
| `graph_stats` | — | Node count by kind, edge count by kind, orphans, stale (mtime > graph build time). |

## 7. Storage Layout

Graph artifacts and content are organized as a **domain tree**, not a flat directory. The tree mirrors the structure of the agent's mental model: session bootstrap → layout → workflow → diagnostics → indexes. Node IDs encode their position in the tree (e.g. `graph-content/workflow/pipeline-structure`), which makes traversal paths visible in citations.

```
target_repo/memory/
  .graph/                      # build artifacts (gitignored, see §15 Q1)
    graph.json                 # node metadata + edges (no bodies)
    graph-bm25.pkl             # rank_bm25 OkapiBM25 index
    graph.lock                 # OS file lock for concurrent writes
  graph-content/               # installed content (was inside CLAUDE.md)
    entry.md                   # root node — setup gate
    session/
      session-start.md         # read order after the gate
      operating-rules.md       # non-negotiables that apply every session
    layout/
      directory-layout.md      # workspace/ + fabric_notebooks/ tree
      tool-layout.md           # tool/* responsibility map
    workflow/
      notebook-workflow.md     # author → build → deploy → smoke → fetch
      pipeline-structure.md    # base / silver / ml layer notebooks
      workspace-management.md  # init / list / switch / transfer
    diagnostics/
      smoke-test-diagnostics.md
    semantic/
      semantic-models.md       # Direct Lake authoring constraints
    indexes/
      skills-index.md          # what skills exist + when to invoke
      agents-index.md          # what subagents exist + when to route
    integrations/
      rtk.md                   # token optimizer integration
  …existing memory/ files (MEMORY.md, project.md, rules/, skill-fixes/, <topic>/)…
```

### 7.1 Source tree (this repo)

`profiles/shared/graph-content/` mirrors the installed tree byte-for-byte:

```
profiles/shared/graph-content/
  entry.md
  session/{session-start.md, operating-rules.md}
  layout/{directory-layout.md, tool-layout.md}
  workflow/{notebook-workflow.md, pipeline-structure.md, workspace-management.md}
  diagnostics/smoke-test-diagnostics.md
  semantic/semantic-models.md
  indexes/{skills-index.md, agents-index.md}
  integrations/rtk.md
```

### 7.2 Node ID convention

Node IDs are the canonical relative path from the indexed root, **with** the directory segments, **without** the `.md` suffix, with forward slashes regardless of OS:

| Path | Node ID |
|---|---|
| `memory/graph-content/entry.md` | `graph-content/entry` |
| `memory/graph-content/workflow/pipeline-structure.md` | `graph-content/workflow/pipeline-structure` |
| `memory/graph-content/diagnostics/smoke-test-diagnostics.md` | `graph-content/diagnostics/smoke-test-diagnostics` |
| `.claude/skills/fabric-transform/SKILL.md` | `skills/fabric-transform` (kind nodes drop the `SKILL` filename) |
| `memory/rules/data-engineering.md` | `rules/data-engineering` |
| `memory/skill-fixes/silver-do-not-trust-bronze-types.md` | `skill-fixes/silver-do-not-trust-bronze-types` |
| `memory/<topic>/project.md` | `topic/<topic>/project` |

This means an agent's citation like *"per `graph-content/workflow/pipeline-structure` and `skill-fixes/silver-do-not-trust-bronze-types`"* tells a human reading the answer **where in the knowledge tree** the facts came from, not just which file.

### 7.3 graph.json schema (top level)

```json
{
  "version": 1,
  "built_at": "2026-05-24T16:30:00Z",
  "built_by": "bin/build-graph.py 0.1.0",
  "nodes": [
    {
      "id": "graph-content/entry",
      "path": "memory/graph-content/entry.md",
      "title": "Mandatory setup gate",
      "kind": "entry",
      "description": "...",
      "frontmatter": {...},
      "mtime": 1727000000.0
    },
    ...
  ],
  "edges": [
    {"src": "graph-content/entry", "dst": "graph-content/session/session-start", "kind": "curated"},
    {"src": "graph-content/session/session-start", "dst": "graph-content/workflow/notebook-workflow", "kind": "curated"},
    ...
  ]
}
```

## 8. Build Pipeline (`bin/build-graph.py`)

```
bin/build-graph.py
  --root <target-repo-root>     # default: cwd
  --out  memory/.graph/graph.json
  --bm25 memory/.graph/graph-bm25.pkl
  [--validate]                  # run schema + orphan checks, exit non-zero on errors
  [--strict]                    # treat orphan warnings as errors
```

Pipeline:

1. **Discover** all `.md` under indexed roots, **recursively** (the content tree is hierarchical):
   - `memory/graph-content/**/*.md`
   - `.claude/skills/*/SKILL.md` and `.agents/skills/*/SKILL.md`
   - `memory/rules/**/*.md`
   - `memory/skill-fixes/*.md`
   - `memory/<topic>/*.md` (any subfolder of `memory/` that isn't `graph-content/`, `.graph/`, `rules/`, `skill-fixes/`, `runbooks/`, `security/`)
   - `memory/MEMORY.md`, `memory/notebook-authoring.md`, `memory/RTK.md`, `memory/project.md`
   - `templates/*.md` (if installed)
   Skip `memory/.graph/`, `.venv/`, `__pycache__/`, and any file with a leading dot.
2. **Parse** frontmatter + body. Derive node id from path (canonical relative path without `.md` suffix, normalized to forward slashes).
3. **Auto-extract edges** (path mentions only — no wiki-link syntax, per locked decision §4 #11):
   - Regex `[\w./-]+\.md` against the body, resolve to node IDs that exist.
   - Code-fenced regions excluded to avoid false positives on examples.
   - Reference-like phrases (`See \`path\``, `per memory/...`) handled by the same path regex — no separate parser.
4. **Curated edges**: read `links:` frontmatter; reject unknown targets with a clear error.
5. **Validate**: warn on orphan nodes; error on duplicate IDs; error on circular curated cycles longer than 4 hops (heuristic — long cycles signal misuse).
6. **Build BM25** index over `title + description + body` per node (using `rank_bm25.BM25Okapi`).
7. **Write** `graph.json` (atomic) + `graph-bm25.pkl` (atomic). Embed schema version 1.

Idempotent. Safe to re-run. No network access.

## 9. Profile Rewrite

### 9.1 New `profiles/claude/CLAUDE.md` (full content)

```markdown
# Microsoft Fabric Data Engineering — Claude Code Profile

You are a Fabric engineering agent operating inside this repository.

You know NOTHING about this project except how to call the graph tool.
All project knowledge (setup gate, rules, skills, pipelines, semantic
models, memory) lives in a knowledge graph. You MUST discover what you
need by traversing it.

## How to work

1. Call `mcp__fabric-graph__get_entry`. Read the returned node's body literally.
   It contains the mandatory setup gate. Follow it before any other action.
2. If the answer is not in the current node, call
   `mcp__fabric-graph__get_linked(id)` to see which nodes it connects to.
3. You may ONLY navigate to node IDs returned by `get_linked` or
   `graph_search`. Never guess a node ID. Never read project markdown
   files directly with the Read tool — use the graph.
4. Use `mcp__fabric-graph__search(query)` only when no linked node looks
   relevant and you need to discover a new entry point.
5. When you have enough information, synthesize the answer and cite the
   node IDs you sourced from, e.g. "per `skills/fabric-transform` and
   `memory/skill-fixes/silver-do-not-trust-bronze-types`".

## Graph tool surface

- `mcp__fabric-graph__get_entry()`           — root node (mandatory first call)
- `mcp__fabric-graph__get_node(id)`          — full content of one node
- `mcp__fabric-graph__get_linked(id)`        — 1-hop neighbors of a node
- `mcp__fabric-graph__search(query)`         — BM25 + edge-aware candidates
- `mcp__fabric-graph__create_node(...)`      — author a new node
- `mcp__fabric-graph__update_node(id, ...)`  — modify an existing node
- `mcp__fabric-graph__add_edge(src, dst)`    — add a curated link
- `mcp__fabric-graph__list_kinds()`          — what node kinds exist

Write operations re-serialize the graph atomically. Use them when you'd
otherwise use `Edit` / `Write` on a project markdown file.
```

`profiles/codex/AGENTS.md` mirrors this verbatim (Codex-specific differences only if `validate-agent-guidance.py` requires them).

### 9.2 Old CLAUDE.md content distribution

The 215 lines of the current `profiles/claude/CLAUDE.md` get split into focused nodes:

| Section in old CLAUDE.md | New node (path) | Node ID |
|---|---|---|
| Session Start (#0 setup gate) | `graph-content/entry.md` | `graph-content/entry` |
| Session Start (#1–#4 read order) | `graph-content/session/session-start.md` | `graph-content/session/session-start` |
| Operating Rules | `graph-content/session/operating-rules.md` | `graph-content/session/operating-rules` |
| Directory Layout | `graph-content/layout/directory-layout.md` | `graph-content/layout/directory-layout` |
| Tool Layout | `graph-content/layout/tool-layout.md` | `graph-content/layout/tool-layout` |
| Notebook Workflow | `graph-content/workflow/notebook-workflow.md` | `graph-content/workflow/notebook-workflow` |
| Pipeline Structure (base/silver/ml) | `graph-content/workflow/pipeline-structure.md` | `graph-content/workflow/pipeline-structure` |
| Workspace Management | `graph-content/workflow/workspace-management.md` | `graph-content/workflow/workspace-management` |
| Smoke-test Diagnostics | `graph-content/diagnostics/smoke-test-diagnostics.md` | `graph-content/diagnostics/smoke-test-diagnostics` |
| Semantic Models | `graph-content/semantic/semantic-models.md` | `graph-content/semantic/semantic-models` |
| Skills (list) | `graph-content/indexes/skills-index.md` | `graph-content/indexes/skills-index` |
| Agents (list) | `graph-content/indexes/agents-index.md` | `graph-content/indexes/agents-index` |
| RTK Token Optimizer | `graph-content/integrations/rtk.md` | `graph-content/integrations/rtk` |

Each new node:
- Starts with frontmatter (`name`, `description`, `links:`).
- Body is verbatim or near-verbatim from the original section (no rewrite — diff-friendly migration).
- Curated `links:` express the traversal graph. Top-level skeleton:
  ```
  graph-content/entry
    → graph-content/session/session-start
    → graph-content/session/operating-rules

  graph-content/session/session-start
    → graph-content/layout/directory-layout
    → graph-content/layout/tool-layout
    → graph-content/workflow/notebook-workflow
    → graph-content/indexes/skills-index
    → graph-content/indexes/agents-index

  graph-content/workflow/notebook-workflow
    → graph-content/workflow/pipeline-structure
    → graph-content/workflow/workspace-management
    → graph-content/diagnostics/smoke-test-diagnostics

  graph-content/workflow/pipeline-structure
    → graph-content/semantic/semantic-models
    → skills/fabric-transform
    → skills/fabric-validate
    → skill-fixes/silver-do-not-trust-bronze-types

  graph-content/indexes/skills-index
    → skills/fabric-ingest, skills/fabric-transform, skills/fabric-model,
      skills/fabric-validate, skills/fabric-notebook-loop, skills/fabric-ops,
      skills/fabric-pipeline, skills/mock-data, skills/semantic-model,
      skills/prd, skills/grill-me, skills/git-commit, skills/caveman
  ```
  Worst-case depth from `entry` to any leaf skill is 3 hops; the validator enforces ≤ 4.

## 10. Installer Changes

`bin/install-fabric-agent` and `fabric_skills_settings/_installer.py`:

1. Copy `profiles/shared/graph-content/` → `<target>/memory/graph-content/`.
2. Copy `tool/graph/` → `<target>/tool/graph/`.
3. Copy `tool/mcp/graph-server.py` → `<target>/tool/mcp/graph-server.py`.
4. Run `python bin/build-graph.py --root <target>` after all files are copied.
5. Register the second MCP server in `.claude/settings.local.json` and `.codex/config.toml`:

   ```json
   "mcpServers": {
     "fabric":       { "command": "python", "args": ["tool/mcp/server.py"] },
     "fabric-graph": { "command": "python", "args": ["tool/mcp/graph-server.py"] }
   }
   ```

   Tools are exposed to the agent as `mcp__fabric-graph__get_entry`, `mcp__fabric-graph__get_node`, etc.

6. Add `memory/.graph/` to the installed `.gitignore` (resolved §4 #10 — gitignored).
7. `REFRESHABLE_SCAFFOLD_MARKERS`: extend to recognize `memory/graph-content/`, `tool/graph/`, `tool/mcp/graph-server.py`.

`bin/install-fabric-agent --refresh` rebuilds `memory/.graph/graph.json` after copying. The `--check` mode validates that the graph artifact exists and matches the installed files (rebuild in tmp + diff).

## 11. Tool Modules

```
tool/graph/
  __init__.py
  schema.py         # Node, Edge dataclasses, frontmatter validation
  store.py          # GraphStore wrapping nx.DiGraph; load/save graph.json
  builder.py        # build pipeline used by bin/build-graph.py
  search.py         # BM25 index + edge-aware re-rank
  extract.py        # auto-edge regex extractors
  lock.py           # cross-platform file lock helper
```

`tool/mcp/graph-server.py` is a thin MCP wrapper: imports from `tool/graph/`, exposes the 10 tools listed in §6, audit-logs every call (same format as `tool/mcp/server.py`).

## 12. Validation Strategy

### 12.1 Rewrite `bin/validate-agent-guidance.py` (Phase P4)

The current validator (read in full at planning time) enforces these on `profiles/claude/CLAUDE.md` and `profiles/codex/AGENTS.md`:

| Current profile check | After hard-minimal rewrite |
|---|---|
| Profile lists every required skill name as `` `skill-name` `` (`validate_profiles`) | Move check to `profiles/shared/graph-content/indexes/skills-index.md` |
| `tool\setup\setup.ps1`, `tool/setup/setup.sh`, `FABRIC_WORKSPACE_ID`, `fab-sandbox auth login`, `` Do **not** read `.env` contents ``, `Setup incomplete` (`validate_setup_guidance`) | Move all six phrases to `profiles/shared/graph-content/entry.md` |
| `Mandatory setup gate`, `` verify `.env`, `fab`, and `fab auth` ``, `before accepting any Fabric work` (Codex-specific) | Move all three phrases to `profiles/shared/graph-content/entry.md` |
| `network` keyword in auth-failure row (`validate_auth_network_guidance`) | Move to `entry.md` (gate table) |
| `lakehouse` + `notebook` keywords (`validate_item_creation_guidance`) | Move `lakehouse` check to `entry.md` or `session/operating-rules.md`; `notebook` already in many nodes |

New profile checks (replace the moved ones):
- `profiles/claude/CLAUDE.md` and `profiles/codex/AGENTS.md` are each ≤ 50 lines.
- Both reference `mcp__fabric-graph__get_entry`.
- Both contain the literal sentence "You know NOTHING about this project except how to call the graph tool" (anti-drift anchor).
- Neither contains any of: `tool/notebook/`, `tool/pipeline/`, `Pipeline Structure`, `Smoke-test`, `Semantic Models`, `Operating Rules`, `Directory Layout`, `Tool Layout` (anti-bypass — these are content section names that must NOT leak back into the profile).

The validator is rewritten in Phase P4, in the same commit that shrinks the profiles. Both sides land together so the validator never points at an inconsistent state.

### 12.2 Additions to `bin/validate-install-package.py`

- `profiles/shared/graph-content/entry.md` exists, has H1 and frontmatter.
- Every `links:` target in graph-content nodes resolves to an existing file in this repo.
- `tool/graph/` mirrors `profiles/shared/project-layout/tool/graph/` byte-for-byte.
- `profiles/shared/graph-content/` tree depth ≤ 3 levels (e.g. `graph-content/workflow/pipeline-structure.md` is the max — no deeper nesting).

### 12.3 New unit tests under `tests/`

- `test_graph_builder.py` — builds from a temp tree; auto edges resolve; orphans warn.
- `test_graph_store.py` — round-trip serialize/deserialize; atomic write under simulated crash (truncated tmp file is rejected).
- `test_graph_search.py` — BM25 ranks expected node first; edge expansion surfaces 1-hop neighbor.
- `test_graph_mcp.py` — every tool against an in-memory graph; CRUD invariants (delete refuses inbound-linked nodes unless `allow_orphans=True`).
- `test_extract.py` — raw path mentions extracted; code-fenced examples ignored; no wiki-link parsing.
- `test_validator_profile_minimal.py` — synthetic 30-line profile passes the new validator; a 200-line profile containing operational content fails it.
- `test_skill_split_coverage.py` and `test_skill_split_traversal.py` — see §12.4 below.

### 12.4 TDD baseline for skill splitting (Phase P5.5)

Resolved §4 #13 mandates a TDD discipline for skill splits. Before any skill SKILL.md is touched:

1. **Capture baseline**: for each skill > 150 lines (`fabric-notebook-loop`, `fabric-ingest`, `fabric-transform`, `fabric-validate`, `prd`, `semantic-model`), write a fixture file under `tests/fixtures/skill-baselines/<skill>.txt` containing the normalized full body of the current SKILL.md (whitespace-normalized, frontmatter stripped, then sha256 of the canonical form).
2. **Define query/answer pairs**: for each skill, pick 3–5 representative queries with the expected node ID that should be returned and the expected token cost of the retrieved content. Stored as `tests/fixtures/skill-queries/<skill>.yaml`.
3. **Lock the test gate** — these tests are written and committed **before** any splitting work:
   - `test_skill_split_coverage.py`: for each split skill, `concat(body for body in split_nodes) == baseline_body` (modulo formatting normalization).
   - `test_skill_split_traversal.py`: for each query in the fixture, BM25+edge search returns the expected node in the top 3, the retrieval path from `graph-content/indexes/skills-index` is ≤ 2 hops, and the token cost of the retrieved section is ≤ 60% of the pre-split full-skill cost.
4. **Now split**. Tests must stay green at every commit during the split work.

This guarantees the post-split graph behaves observably the same as the pre-split graph for known workflows.

### 12.5 Smoke test

`bin/install-fabric-agent --check` against a disposable tmp target must pass, including `python bin/build-graph.py --validate --strict` after install.

## 13. Phased Implementation

| Phase | Scope | Deliverable | Gate |
|---|---|---|---|
| P0 | Create branch (`graph-driven-profile`); scaffold `tool/graph/` (schema + store + builder + lock). | Builds a graph from the current repo and dumps stats. No MCP server yet. | `python bin/build-graph.py --root .` runs against the source repo and produces `memory/.graph/graph.json`. |
| P1 | Auto-edge extraction (path mentions only — no wiki-links) + BM25 + edge-aware re-rank. | `tool/graph/search.py` returns sensible results for 10 hand-picked queries. | `test_graph_search.py` passes; `test_extract.py` passes. |
| P2 | MCP `fabric-graph` server, read-only tools. | `tool/mcp/graph-server.py` exposes `get_entry`, `get_node`, `get_linked`, `search`, `list_kinds`. | Manual Claude Code session calls `mcp__fabric-graph__*` and navigates the existing repo's md tree. |
| P3 | Split CLAUDE.md / AGENTS.md content into `profiles/shared/graph-content/` domain tree (13 nodes) with curated `links:` frontmatter. Add curated `templates/*` ← `rules/*` edges (resolved §4 #15). | 13 content nodes + edges to templates. | Reading from `graph-content/entry` to any leaf skill or template is ≤ 3 hops; orphan count = 0; templates have ≥ 1 inbound edge each. |
| P4 | Hard-minimal profile rewrite + validator rewrite (in one commit). | `profiles/claude/CLAUDE.md` + `profiles/codex/AGENTS.md` shrunk to ≤ 50 lines; `bin/validate-agent-guidance.py` checks moved per §12.1. | All three validators pass: `validate-install-package`, `validate-agent-guidance`, `pytest`. |
| P5 | Write tools (`create_node`, `update_node`, `delete_node`, `add_edge`, `remove_edge`) + atomic file-lock. | Full CRUD surface. | `test_graph_mcp.py` passes; manual: agent creates a new skill-fix node via the tool end-to-end. |
| **P5.5** | **TDD baseline for skill splitting (resolved §4 #13).** Write `tests/fixtures/skill-baselines/*.txt` + `tests/fixtures/skill-queries/*.yaml` for each skill > 150 lines. Write `test_skill_split_coverage.py` + `test_skill_split_traversal.py`. Tests fail initially (they target post-split structure that doesn't exist yet). | Failing tests committed; baseline fixtures pinned. | Tests run; they fail with a clear "skill not split yet" assertion message. |
| **P5.6** | **Split skills > 150 lines by H2** (`fabric-notebook-loop`, `fabric-ingest`, `fabric-transform`, `fabric-validate`, `prd`, `semantic-model`). Each H2 section becomes a child node under `profiles/skills/<skill>/sections/<slug>.md`; the parent `SKILL.md` becomes an index node linking to sections. | Split skills + index pages. | `test_skill_split_coverage.py` and `test_skill_split_traversal.py` pass. Existing workflows (e.g. invoking `fabric-transform` for a Silver MERGE) reach the relevant section in ≤ 2 hops with ≤ 60% of the original token cost. |
| P6 | Installer integration. | `bin/install-fabric-agent` copies `graph-content/`, `tool/graph/`, `tool/mcp/graph-server.py`; runs builder; registers both MCP servers. `fabric_skills_settings/_installer.py` mirrored. | `bin/install-fabric-agent --check` against a disposable tmp target passes; round-trip install + Claude Code session works. |
| P7 | Frontmatter migration on remaining files (rules, skill-fixes, memory, templates). Add `links:` frontmatter where curated edges add value. | Curated edges on key cross-references. | `python bin/build-graph.py --validate --strict` exits 0 with orphan count = 0. |
| P8 | Documentation + observability. Update repo `README.md` and source-repo `CLAUDE.md`; surface `graph_stats`; doc the node-ID citation convention. | PR-ready branch. | All validators + `pytest` pass; manual review. |

Each phase is a separate commit on `graph-driven-profile`. Final PR may squash on request.

## 14. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Agent calls `Read` on a project markdown file anyway, bypassing the graph. | `validate-agent-guidance.py` checks that no project file paths appear in the profile. Profile prose forbids it. We cannot enforce at the harness level, but absence-of-cue is the main lever. |
| Setup gate is skipped because it's no longer the first thing in the profile. | The profile's #1 instruction is `mcp__fabric-graph__get_entry` first; the entry node's #1 instruction is the gate. Same number of layers as today (profile → gate); the gate is just one tool call away instead of inline. |
| `graph.json` and the `.md` files drift (someone edits a file without rebuilding). | Builder records mtime per node; `graph_stats` reports stale nodes. `bin/install-fabric-agent --check` rebuilds + diffs. Optional: hook `graph_get_node` to re-parse on mtime drift. (Initial release: report-only.) |
| BM25 misses semantic matches. | Acceptable for v1 — curated `links:` carry the structural retrieval load. Document that authors should add explicit `links:` for important cross-references. |
| Two agents concurrently call `graph_update_node`. | OS-level file lock around `graph.json`; updates are serialized. |
| Splitting CLAUDE.md churns git blame on the 215 lines. | Verbatim copy-paste into split files (no rewrite). One commit per phase. Original commit history preserved via `git log --follow` on the new files after a `git mv` where possible (though splits aren't a single rename — accept this cost). |
| Existing skill-fix workflow (memory/skill-fixes/) breaks. | Skill-fix files become regular nodes. The format in shared MEMORY.md still applies. New nodes are added via `graph_create_node` or normal Write + rebuild. |
| MCP server startup cost on every session. | `graph.json` + BM25 pickle load in <100ms for the current corpus (~30 files). Acceptable. |

## 15. Resolved Decisions Log

All seven questions originally posed here have been resolved. Each is recorded in §4 (Locked Decisions) at the row indicated. This section preserves the rationale for traceability.

| # | Question | Resolution | §4 row |
|---|---|---|---|
| 1 | Commit graph artifacts or gitignore? | **Gitignored** (`memory/.graph/`). Builder runs at install + refresh. | #10 |
| 2 | Keep `[[wiki-link]]` syntax? | **Dropped.** Curated edges via frontmatter `links:` only; auto-extraction reads raw path mentions in prose. | #11 |
| 3 | `graph_undo` operation? | **No.** Git is the undo mechanism. No `.md.bak` shadow files. | #12 |
| 4 | Split existing skill files? | **Yes**, but gated on a TDD baseline (Phase P5.5 + P5.6). Pre-split fixtures pin current behavior; split nodes must cover the fixture and traverse in ≤ 2 hops with ≤ 60% token cost. | #13 |
| 5 | Codex `AGENTS.md` compatibility under hard-minimal rewrite? | **Validator rewrite required in Phase P4.** See §12.1 — existing per-profile phrase/skill checks move to node-presence checks against `entry.md`, `session/session-start.md`, `session/operating-rules.md`, `indexes/skills-index.md`. New profile checks: ≤ 50 lines, must reference `mcp__fabric-graph__get_entry`, must NOT contain operational section names. | #14 |
| 6 | Templates as nodes? | **Yes**, kind=`template`. Curated edges from `rules/security` → `templates/security-review`, `templates/access-review`; `rules/data-engineering` → `templates/data-quality-checklist`, `templates/pipeline-brief`; `rules/fabric-platform` → `templates/runbook`, `templates/incident-report`, `templates/release-checklist`. Authored in Phase P3. | #15 |
| 7 | MCP server name? | **`fabric-graph`.** Tools exposed as `mcp__fabric-graph__*`. | #16 |

No remaining open questions. Ready to branch on approval of this plan.

## 16. Files Added / Modified / Deleted

### Added (source package)

```
tool/graph/__init__.py
tool/graph/schema.py
tool/graph/store.py
tool/graph/builder.py
tool/graph/search.py
tool/graph/extract.py
tool/graph/lock.py
tool/mcp/graph-server.py
bin/build-graph.py
profiles/shared/graph-content/entry.md
profiles/shared/graph-content/session/session-start.md
profiles/shared/graph-content/session/operating-rules.md
profiles/shared/graph-content/layout/directory-layout.md
profiles/shared/graph-content/layout/tool-layout.md
profiles/shared/graph-content/workflow/notebook-workflow.md
profiles/shared/graph-content/workflow/pipeline-structure.md
profiles/shared/graph-content/workflow/workspace-management.md
profiles/shared/graph-content/diagnostics/smoke-test-diagnostics.md
profiles/shared/graph-content/semantic/semantic-models.md
profiles/shared/graph-content/indexes/skills-index.md
profiles/shared/graph-content/indexes/agents-index.md
profiles/shared/graph-content/integrations/rtk.md
profiles/shared/project-layout/tool/graph/  (mirror of tool/graph/)
profiles/shared/project-layout/tool/mcp/graph-server.py
profiles/skills/<skill>/sections/<slug>.md  (Phase P5.6 — split skills > 150 lines)
tests/test_graph_builder.py
tests/test_graph_store.py
tests/test_graph_search.py
tests/test_graph_mcp.py
tests/test_extract.py
tests/test_validator_profile_minimal.py        (Phase P4)
tests/test_skill_split_coverage.py             (Phase P5.5)
tests/test_skill_split_traversal.py            (Phase P5.5)
tests/fixtures/skill-baselines/<skill>.txt     (Phase P5.5 — one per skill > 150 lines)
tests/fixtures/skill-queries/<skill>.yaml      (Phase P5.5 — one per skill > 150 lines)
```

### Modified

```
profiles/claude/CLAUDE.md            (215 → ~30 lines, hard-minimal; Phase P4)
profiles/codex/AGENTS.md             (221 → ~30 lines, hard-minimal; Phase P4)
profiles/claude/settings.local.json  (register `fabric-graph` MCP server)
profiles/codex/config.toml           (register `fabric-graph` MCP server)
profiles/skills/<skill>/SKILL.md     (Phase P5.6 — become index pages linking to sections/ for split skills; Phase P7 — add `links:` frontmatter for the rest)
memory/rules/*.md                    (Phase P3 — add curated `links:` to templates/; Phase P7 — frontmatter on remaining edges)
memory/MEMORY.md                     (Phase P7 — add `links:` frontmatter)
templates/*.md                       (Phase P3 — add frontmatter `name`, `description`, `kind: template`)
bin/install-fabric-agent             (copy graph-content + tool/graph; run builder; register `fabric-graph` MCP server; extend REFRESHABLE_SCAFFOLD_MARKERS; add `memory/.graph/` to installed `.gitignore`)
fabric_skills_settings/_installer.py (mirror of above)
bin/validate-install-package.py      (graph-content + tool/graph mirror checks; tree-depth check)
bin/validate-agent-guidance.py       (rewrite per §12.1 — move per-profile phrase checks to node-presence checks; new profile checks: ≤ 50 lines, references `mcp__fabric-graph__get_entry`, anti-drift anchor sentence, anti-bypass section-name blocklist)
pyproject.toml                       (add `networkx`, `rank_bm25` to runtime deps)
CLAUDE.md                            (this source repo: doc the new layout — last in Phase P8)
```

### Deleted

```
(none in v1 — every line of the old profiles is preserved as a node)
```

## 17. Rough Token / Effort Estimate

- Code: ~1700 LoC Python (graph + MCP + validator rewrite + tests; +200 over original estimate for skill-split TDD harness).
- Content split (Phase P3): mechanical copy-paste into domain tree; ~30 minutes.
- Skill split (Phase P5.6): ~2 hours including TDD harness setup in P5.5.
- Templates frontmatter + curated edges (Phase P3): ~30 minutes.
- Frontmatter migration on remaining files (Phase P7): ~1 hour.
- Total: 2–3 days of implementation work across the 10 phases (P0 → P8 + P5.5 + P5.6).

## 18. What I need from you

All seven open questions are now resolved and recorded in §4 + §15. The remaining ask is:

- **Review the domain tree grouping in §7** (`session/`, `layout/`, `workflow/`, `diagnostics/`, `semantic/`, `indexes/`, `integrations/`). Different groupings are fine — change before Phase P3 to keep the split mechanical.
- **Approve to branch.** On approval I create `graph-driven-profile` and execute Phase P0 → P1 first, stopping for a check-in before touching the profiles (Phase P4) or the validator.
