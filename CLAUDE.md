# Fabric Agent Pack — Claude Contributor Guidance

This repository is the source package and installer for Microsoft Fabric agent profiles. It is not the day-to-day Fabric project workspace. Install a profile into a target repo with `packaging/install-fabric-agent` (or `pip install fabric-skills-settings`), then run Claude Code from that target repo root.

## Architecture at a glance

Two MCP servers ship with every install:

- **`fabric`** (`mcp/server.py`) — wraps the Fabric CLI: list/get items and authenticated REST API calls.
- **`fabric-graph`** (`mcp/graph-server.py`) — RAG knowledge graph: BM25 + 1-hop edge-aware read tools plus full CRUD over nodes and edges.

The installed target's `CLAUDE.md` is ~30 lines and points agents at `graph_get_entry` first. All operational knowledge — setup gate, session-start order, workflow, skills, tools, rules — lives in graph nodes. There is no static `memory/project.md`, `memory/runbooks/`, `memory/security/`, or `templates/`; those are now graph nodes accessed and updated via `graph_*` MCP tools.

See [`docs/architecture.md`](docs/architecture.md) for diagrams.

## Source package layout

| Path | Purpose |
|---|---|
| `packaging/` | Source-package internals (NOT installed into targets). |
| `packaging/fabric_agent_installer/` | Pip-installable wheel (published on PyPI as `fabric-skills-settings`). Imported as `fabric_agent_installer`. Profiles bundled as `_profiles/`, content as `_content/`, tool/ as `_tool/`, mcp/ as `_mcp/`, graph artifacts as `_graph/` by hatchling. |
| `packaging/install-fabric-agent` | The CLI shim (mirrors `_installer.py`). |
| `packaging/builders/` | Source-package-only graph builders: `build-graph.py`, `build-agent-capability-graph.py`, and the `graph_build/` build-time modules they import. |
| `packaging/validators/` | Source-package-only validators: `validate-install-package.py`, `validate-agent-guidance.py`. |
| `tool/` | Fabric runtime helpers. Single source of truth — installer copies to target's `tool/`. |
| `tool/graph/` | Runtime graph package: `schema`, `store`, `search` (BM25 + 1-hop), `writes` (CRUD), `lock`, `builder`, `extract`. |
| `mcp/` | MCP servers, **top-level and parallel to `tool/`**: `server.py` (`fabric`), `graph-server.py` (`fabric-graph`). Installer copies to target's `mcp/`. |
| `content/` | Installable content sources. |
| `content/rules/` | Security / data-engineering / fabric-platform / notebook-authoring rules. Installer copies to target's `memory/rules/`. |
| `content/graph-content/` | Knowledge-graph content tree (`entry.md`, `session/`, `workflow/`, `layout/`, `indexes/`, `integrations/`, `diagnostics/`, `semantic/`). Installer copies to target's `memory/graph-content/`. |
| `profiles/skills/` | Skill source. Installer copies to `.claude/skills/` and `.agents/skills/`. |
| `profiles/codex/` | Codex-native install assets: `AGENTS.md`, `.codex/agents`, `.codex/config.toml`. |
| `profiles/claude/` | Claude-native install assets: `CLAUDE.md`, `.claude/agents`, `.claude/settings.local.json`. |
| `profiles/shared/memory/` | Placeholder (just `.gitkeep`). Installed to target as `memory/` so the `fabric-graph` MCP server has a writable graph root. |
| `profiles/shared/scaffold/` | Target scaffolding installed verbatim: `.mcp.json`, `data/sandbox/`, `workspace/`, target-side overrides for `tool/setup/setup.{ps1,sh}` (which omit the source-side graph-build step). |
| `dist/` | Build outputs — both the wheel (`*.whl`, `*.tar.gz`) and `dist/.graph/` (source-side knowledge graph artifacts; the installer ships these to target's `memory/.graph/`). |
| `setup.ps1` / `setup.sh` | Root post-clone entry points for source-package maintainers; forward to `packaging/validators/` and document `packaging/install-fabric-agent`. |

## Knowledge graph

- **Sources**: `content/graph-content/**/*.md`, `content/rules/*.md`, `profiles/skills/*/SKILL.md` (+ `sections/`), `profiles/shared/memory/*.md`, `memory/skill-fixes/*.md` (target-side runtime). Curated edges come from frontmatter `links:`; auto edges from raw `path/to/file.md` mentions in prose.
- **Build**: `packaging/builders/build-graph.py` writes `dist/.graph/{graph.json, graph-bm25.pkl, materialized-graph.html, materialized-graph.svg}` in the source repo. Source-package `tool/setup/setup.{ps1,sh}` invokes it via `uv run --group dev python packaging/builders/build-graph.py --target . --stats`.
- **Derived capability graph**: `packaging/builders/build-agent-capability-graph.py` writes `dist/.graph/agent-capabilities.json` + `agent-capabilities.html` + `agent-capabilities.svg`. Groups knowledge nodes under the 4 subagents (orchestrator, developer, tester, operator) using their native frontmatter `links:` + `skills:` as the source of truth.
- **Shipped pre-built to target**: `install-fabric-agent` copies `dist/.graph/*` (graph.json, BM25 pickle, HTML/SVG visualizations, agent-capabilities) into the target's `memory/.graph/`. Wheel installs source these from the bundled `fabric_agent_installer/_graph/`; source-checkout installs source from `<repo>/dist/.graph/`. Lock files are not shipped. Existing target artifacts are kept unless `--force` is passed.
- **CRUD at runtime**: every `graph_create_node` / `graph_update_node` / `graph_delete_node` / `graph_add_edge` / `graph_remove_edge` call in a target repo triggers an atomic rebuild via `tool/graph/writes.py`, writing to the target's `memory/.graph/`. Target setup scripts therefore no longer rebuild the graph from scratch — they only verify the shipped artifact is present.
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
| `tool/workspace/` | Workspace registry helpers (`init.py`, `switch.py`, `transfer.py`). |
| `tool/pre-commit-check.{ps1,sh}` | Completion check used before reporting done. |
| `mcp/` | `fabric` and `fabric-graph` MCP servers (top-level, parallel to `tool/`). |
| `memory/` | Target runtime persistence root: `memory/.graph/` (graph artifacts), `memory/rules/` (installed rules), `memory/graph-content/` (installed graph content nodes), `memory/skill-fixes/`. |

## File scanning

Always exclude `.venv/` when searching — it contains third-party packages and produces noisy matches.

## Development rules

- Keep vendor-specific runtime assets inside their profile folders. No root `.claude/` or `.codex/` directories.
- Skill source is single-source under `profiles/skills/`. Do not duplicate elsewhere.
- Profiles own agents, skills, entrypoints, and settings. Runtime state shared between Codex and Claude is `memory/` only.
- Build-time graph code (`packaging/builders/graph_build/`) is NOT installed into target repos; only runtime code (`tool/graph/`) is. Don't reintroduce build modules under `tool/`.
- `tool/` is the single source of truth for installable helpers. The scaffold only carries target-side OVERRIDES (currently just `profiles/shared/scaffold/tool/setup/setup.{ps1,sh}`, which omit the source-side graph-build invocation because the target receives the graph pre-built via the installer).
- When changing installer logic, keep `packaging/install-fabric-agent` (CLI shim) and `packaging/fabric_agent_installer/_installer.py` in sync. Run `uv build` to verify the wheel content.
- If installer refresh must recognize a helper, update `REFRESHABLE_SCAFFOLD_MARKERS` in both installer scripts.
- Never commit `.env`, credentials, tokens, connection strings, data files, logs, generated notebook bundles, or `__pycache__/`.
- Use placeholders only in `.env.example`.
- Fabric CLI wrappers must not execute caller-controlled binaries. Do not reintroduce `FAB_BIN`, PATH-based `fab` discovery, or arbitrary `fab` command resolution.
- Fabric credentials pass through environment variables or approved secret stores only — never command-line arguments.
- RTK setup stays pinned to a specific release and verifies downloaded assets against the release checksum.

## Required checks

`./setup.sh` (or `.\setup.ps1`) is the single-shot CLI for the source clone. With no args it runs the maintainer sanity check + both validators. With `--profile X --target Y` it validates, installs, and runs the target's `tool/setup/setup.{ps1,sh}` bootstrap (`.venv` + Fabric auth prompts + `workspaces.json`) **in one command**. After `pip install fabric-skills-settings`, the same end-to-end install runs as `install-fabric-agent --profile X --target Y`. Pass `--no-bootstrap` when you only want files copied (CI / dry-run flows).

After changing profiles, installer logic, guidance, validation, or installable tooling:

```bash
./setup.sh                                            # validators + sanity check (no install)
uv run --group dev pytest                             # tests
./setup.sh --profile all --target <target-repo> --dry-run  # disposable-target smoke test
./setup.sh --profile all --target <target-repo> --check    # idempotency check
```

Run the unit tests after any change to `tool/notebook/build.py` or `tool/pipeline/manage.py`. The validators are also runnable directly (`uv run packaging/validators/validate-install-package.py`, `uv run packaging/validators/validate-agent-guidance.py`) when you want to skip the wrapper.

Do not run source-package validators from an installed target repo; they are not installed there.

## Commit / PR handoff

State what changed, which validations were run, whether a target-repo smoke test was performed, and any failures or limitations encountered.
