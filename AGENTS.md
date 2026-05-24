# Fabric Agent Pack — Codex Contributor Guidance

This repository is the source package and installer for Microsoft Fabric agent profiles. It is not the day-to-day Fabric project workspace. Install a profile into a target repo with `bin/install-fabric-agent` (or `pip install fabric-skills-settings`), then run Codex from that target repo root.

## Architecture at a glance

Two MCP servers ship with every install:

- **`fabric`** (`tool/mcp/server.py`) — wraps the Fabric CLI: list/get items and authenticated REST API calls.
- **`fabric-graph`** (`tool/mcp/graph-server.py`) — RAG knowledge graph: BM25 + 1-hop edge-aware read tools plus full CRUD over nodes and edges.

The installed target's `AGENTS.md` is ~30 lines and points agents at `graph_get_entry` first. All operational knowledge — setup gate, session-start order, workflow, skills, tools, rules — lives in graph nodes. There is no static `memory/project.md`, `memory/runbooks/`, `memory/security/`, or `templates/`; those are now graph nodes accessed and updated via `graph_*` MCP tools.

See [`docs/architecture.md`](docs/architecture.md) for diagrams.

## Source package layout

| Path | Purpose |
|---|---|
| `profiles/skills/` | Skill source. Single source of truth — installer copies to `.claude/skills/` and `.agents/skills/`. |
| `profiles/codex/` | Codex-native install assets: `AGENTS.md`, `.codex/agents`, `.codex/config.toml`. |
| `profiles/claude/` | Claude-native install assets: `CLAUDE.md`, `.claude/agents`, `.claude/settings.local.json`. |
| `profiles/shared/graph-content/` | Knowledge-graph content tree (`entry.md`, `session/`, `workflow/`, `layout/`, `indexes/`, `integrations/`, `diagnostics/`, `semantic/`). Copied to `memory/graph-content/` at install. |
| `profiles/shared/memory/` | Empty placeholder (just `.gitkeep`). Installed to target as `memory/` so the `fabric-graph` MCP server has a writable graph root. |
| `profiles/shared/project-layout/` | Target scaffolding (`tool/`, `memory/rules/`, `.mcp.json`). |
| `tool/` | **Runtime** tooling. Source-package mirror of `profiles/shared/project-layout/tool/`; parity is enforced. |
| `tool/graph/` | Runtime graph package: `schema`, `store`, `search` (BM25 + 1-hop), `writes` (CRUD), `lock`, `builder`, `extract`. |
| `tool/mcp/` | The two MCP servers: `server.py` (`fabric`), `graph-server.py` (`fabric-graph`). |
| `build/graph_build/` | **Build-time only** modules used by `bin/build-*.py`. NOT installed into target repos. |
| `rules/` | Source for security / data-engineering / fabric-platform rules. Mirrored to `memory/rules/` at install. |
| `bin/` | Source-package-only: installer, validators, graph builders. Not installed. |
| `fabric_skills_settings/` | Pip-installable wheel. `_installer.py` mirrors `bin/install-fabric-agent`; profiles bundled as `_profiles/` by hatchling. |

## Knowledge graph

- **Sources**: `profiles/shared/graph-content/**/*.md`, `profiles/shared/memory/*.md`, `profiles/skills/*/SKILL.md` (+ `sections/`), `rules/*.md`, `memory/skill-fixes/*.md`. Curated edges come from frontmatter `links:`; auto edges from raw `path/to/file.md` mentions in prose.
- **Build**: `bin/build-graph.py` writes `memory/.graph/graph.json` + `memory/.graph/graph-bm25.pkl` + `memory/.graph/materialized-graph.svg`.
- **Derived capability graph**: `bin/build-agent-capability-graph.py` writes `agent-capabilities.json` + `agent-capabilities.svg`. Groups knowledge nodes under the 4 subagents (orchestrator, developer, tester, operator) using their native frontmatter `links:` + `skills:` as the source of truth.
- **CRUD at runtime**: every `graph_create_node` / `graph_update_node` / `graph_delete_node` / `graph_add_edge` / `graph_remove_edge` call triggers an atomic rebuild via `tool/graph/writes.py`.
- **Entrypoint limits**: `profiles/claude/CLAUDE.md` and `profiles/codex/AGENTS.md` must stay ≤ 50 lines and contain no operational section headings. Enforced by `bin/validate-agent-guidance.py`.

## Skills

Skill source files live only under `profiles/skills/`. Installed skills:

`rtk`, `fabric-ingest`, `fabric-transform`, `fabric-model`, `fabric-validate`, `fabric-notebook-loop`, `fabric-ops`, `fabric-pipeline`, `semantic-model`, `mock-data`, `prd`, `grill-me`, `git-commit`, `caveman`.

Long skills (> 150 lines) are split into `sections/` under the skill folder with a thin parent `SKILL.md` index. The split is gated by the `SPLIT_SKILLS` table in `tests/test_skill_split_coverage.py`.

## Installed target tooling

| Path | Purpose |
|---|---|
| `tool/setup/` | One-time human setup, Fabric CLI sandbox wrappers, read-only inventory. |
| `tool/data/` | Deterministic synthetic CSV generator. |
| `tool/notebook/` | Notebook build, deploy, smoke-test, fetch, run, monitor. |
| `tool/pipeline/` | Data Factory pipeline create / update / run / status / list / test. |
| `tool/lakehouse/` | Lakehouse table and schema inspection. |
| `tool/semantic-model/` | Semantic Model inspection via `sempy.fabric`. |
| `tool/validate/` | Local pipeline-lineage validators. |
| `tool/graph/` | Graph runtime (schema, store, search, writes, lock). |
| `tool/mcp/` | `fabric` and `fabric-graph` MCP servers. |
| `tool/pre-commit-check.{ps1,sh}` | Completion check used before reporting done. |

## File scanning

Always exclude `.venv/` when searching — it contains third-party packages and produces noisy matches.

## Development rules

- Keep vendor-specific runtime assets inside their profile folders. No root `.claude/` or `.codex/` directories.
- Skill source is single-source under `profiles/skills/`. Do not duplicate elsewhere.
- Profiles own agents, skills, entrypoints, and settings. Runtime state shared between Codex and Claude is `memory/` only.
- Build-time graph code (`build/graph_build/`) is NOT installed into target repos; only runtime code (`tool/graph/`) is. Don't reintroduce build modules under `tool/`.
- When changing installable helpers, edit both `tool/<area>/...` and `profiles/shared/project-layout/tool/<area>/...`; `bin/validate-install-package.py` enforces parity.
- When changing installer logic, keep `bin/install-fabric-agent` and `fabric_skills_settings/_installer.py` in sync. Run `uv build` to verify the wheel content.
- If installer refresh must recognize a helper, update `REFRESHABLE_SCAFFOLD_MARKERS` in both installer scripts.
- Never commit `.env`, credentials, tokens, connection strings, data files, logs, generated notebook bundles, or `__pycache__/`.
- Use placeholders only in `.env.example`.
- Fabric CLI wrappers must not execute caller-controlled binaries. Do not reintroduce `FAB_BIN`, PATH-based `fab` discovery, or arbitrary `fab` command resolution.
- Fabric credentials pass through environment variables or approved secret stores only — never command-line arguments.
- RTK setup stays pinned to a specific release and verifies downloaded assets against the release checksum.

## Required checks

After changing profiles, installer logic, guidance, validation, or installable tooling:

```bash
uv run bin/validate-install-package.py
uv run bin/validate-agent-guidance.py
uv run --group dev pytest
```

Run the unit tests after any change to `tool/notebook/build.py` or `tool/pipeline/manage.py`.

For installer or profile changes, also run a disposable-target smoke test:

```bash
python bin/install-fabric-agent --profile all --target <target-repo> --check
```

Do not run source-package validators from an installed target repo; they are not installed there.

## Commit / PR handoff

State what changed, which validations were run, whether a target-repo smoke test was performed, and any failures or limitations encountered.
