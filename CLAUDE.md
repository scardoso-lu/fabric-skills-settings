# Fabric Agent Pack — Claude Contributor Guidance

This repository is the source package and installer for Microsoft Fabric agent profiles. It is not the day-to-day Fabric project workspace. Install a profile into a target repo with `cli/install-fabric-agent` (or `pip install fabric-skills-settings`), then run Claude Code from that target repo root.

## Architecture at a glance

The repo has three top-level packages:

- **`cli/`** — everything installed on the user's laptop: the wheel installer, profile entrypoints + 4 subagents (Claude + Codex), setup scripts, and the target-side tools shipped to `tool/` in the target repo. Tools in `cli/tools/` are invoked via Bash, not MCP.
- **`server/`** — FastMCP HTTP server (Docker). Serves graph knowledge tools plus fabric helpers that run without ms-fabric-cli. Start it with `docker compose up` from `server/`.
- **`packaging/validators/`** — source-repo-only validators (`validate-install-package.py`, `validate-agent-guidance.py`). Not installed into target repos.

See [`docs/architecture.md`](docs/architecture.md) for diagrams.

## MCP server capabilities (`server/`)

The `fabric-server` MCP container exposes:

| Tool | Description |
|---|---|
| `graph_get_entry`, `graph_get_node`, `graph_get_linked`, `graph_search`, `graph_list_kinds` | Knowledge graph read tools |
| `graph_create_node`, `graph_update_node`, `graph_delete_node`, `graph_add_edge`, `graph_remove_edge` | Knowledge graph write tools (atomic rebuild) |
| `pipeline_lineage_check` | Upload notebooks as `{rel_path: content}`, validates staging-path consistency |
| `data_mock_generate` | Generate deterministic synthetic CSV test data |
| `semantic_model_list`, `semantic_model_show` | Inspect Fabric semantic model measures and relationships via `sempy.fabric` |

The server has **no filesystem access** to the user's project. `pipeline_lineage_check` accepts uploaded file contents; `data_mock_generate` requires a `target_dir` mounted into the container.

## CLI / Bash tool capabilities (`cli/tools/` → installed as `tool/`)

Tools shipped to the target repo's `tool/` dir and invoked via Bash. Fabric-CLI-dependent helpers require `ms-fabric-cli` (`uv tool install ms-fabric-cli`) and SPN credentials in `.env`:

| Path | Description |
|---|---|
| `tool/notebook/build.py` | Build `.Notebook` bundles from `workspace/<topic>/<name>.py` |
| `tool/notebook/deploy.py` | Deploy, run, monitor, fetch notebooks |
| `tool/pipeline/manage.py` | Create, run, list, test Data Factory pipelines |
| `tool/lakehouse/list-tables.py` | Inspect lakehouse tables and schemas |
| `tool/workspace/{init,switch,transfer}.py` | Manage `workspaces.json`, switch workspace, transfer items |
| `tool/lint/` (`python -m tool.lint`) | Deterministic lints: SEC-01 hardcoded secrets, DE-09 Faker seed. Pure Python, no fab. |
| `tool/precommit/pre-commit-check.{sh,ps1}` | Aggregate pre-commit check: runs lints locally. Pipeline lineage check is via the `pipeline_lineage_check` MCP tool. |
| `tool/setup/setup.{ps1,sh}` | One-time target bootstrap: install fab, prompt for SPN creds, populate workspaces.json |

## Source package layout

| Path | Purpose |
|---|---|
| `cli/fabric_agent_installer/` | Pip-installable wheel (`fabric-skills-settings`). Profiles in `_profiles/`, setup in `_setup/`, tools in `_tools/`. |
| `cli/install-fabric-agent` | CLI shim (mirrors `_installer.py`). |
| `cli/profiles/claude/` | Claude-native install assets: `CLAUDE.md`, `.claude/agents/`, `settings.local.json`. |
| `cli/profiles/codex/` | Codex-native install assets: `AGENTS.md`, `.codex/agents/`, `config.toml`. |
| `cli/profiles/shared/` | Shared scaffold (`.mcp.json`, `data/sandbox/`, `workspace/`, `.env.example`, `.gitignore.fragment`). |
| `cli/setup/` | `setup.{ps1,sh}` — target bootstrap scripts (shipped to `tool/setup/`). |
| `cli/tools/` | Target-side tools (shipped to `tool/`): `notebook/`, `pipeline/`, `lakehouse/`, `workspace/`, `lint/`, `precommit/`. |
| `server/app.py` | FastMCP app — builds and registers all server-side tools. |
| `server/tools/` | MCP tool wrappers: `graph/`, `validate/`, `data/`, `semantic_model/`. |
| `server/graph/` | Graph runtime: `store`, `search` (BM25 + 1-hop), `writes` (CRUD), `schema`, `lock`, `builder`, `extract`. |
| `server/content/` | Knowledge-graph content tree (`entry.md`, `session/`, `workflow/`, `rules/`, `indexes/`, …) and rules. |
| `server/skills/` | Skill definitions served via the graph. NOT shipped to target repos. |
| `server/builders/` | Source-only graph builders: `build-graph.py`, `build-agent-capability-graph.py`. |
| `server/Dockerfile`, `server/docker-compose.yml` | Container definition for local dev. |
| `packaging/validators/` | Source-repo maintainer validators (not installed in targets). |
| `tests/` | Unit + integration tests. Run with `uv run --group dev pytest`. |

## Knowledge graph

- **Sources**: `server/content/**/*.md`, `server/skills/*/SKILL.md` (+ `sections/`). Curated edges from frontmatter `links:`; auto edges from path mentions in prose.
- **Build**: `server/builders/build-graph.py` writes `dist/.graph/{graph.json, graph-bm25.pkl, *.html, *.svg}`. Run via `uv run --group dev python server/builders/build-graph.py --target . --stats`.
- **Served live**: the running Docker container loads `dist/.graph/` on startup and serves all graph tools. CRUD calls (`graph_create_node` etc.) trigger an atomic in-memory rebuild — no restart needed.

## Skills

Skill source files live only under `server/skills/`. They are served via the graph (`graph_get_node('skills/<name>')`) — **not shipped** to target repos.

Installed skills: `rtk`, `fabric-ingest`, `fabric-transform`, `fabric-model`, `fabric-validate`, `fabric-notebook-loop`, `fabric-ops`, `fabric-pipeline`, `semantic-model`, `mock-data`, `prd`, `grill-me`, `git-commit`, `caveman`.

Long skills (> 150 lines) are split into `sections/` under the skill folder. Gated by `SPLIT_SKILLS` in `tests/test_skill_split_coverage.py`.

## File scanning

Always exclude `.venv/` when searching.

## Development rules

- Keep vendor-specific runtime assets inside their profile folders. No root `.claude/` or `.codex/` directories.
- Skill source is single-source under `server/skills/`. Do not duplicate elsewhere.
- Build-time graph code (`server/builders/`) is NOT installed into target repos; only runtime code in `server/graph/` and `server/tools/` runs in Docker.
- `cli/tools/` is the single source of truth for installable target helpers. `cli/profiles/shared/scaffold/` only carries verbatim scaffold files (`.mcp.json`, `data/sandbox/`, `workspace/`).
- When changing installer logic, keep `cli/install-fabric-agent` (CLI shim) and `cli/fabric_agent_installer/_installer.py` in sync. Run `uv build` to verify wheel content.
- If installer refresh must recognize a helper, update `REFRESHABLE_SCAFFOLD_MARKERS` in both installer scripts.
- Never commit `.env`, credentials, tokens, connection strings, data files, logs, generated notebook bundles, or `__pycache__/`.
- Use placeholders only in `.env.example`.
- Fabric CLI wrappers must not execute caller-controlled binaries.
- Fabric credentials pass through environment variables or approved secret stores only — never command-line arguments.
- RTK setup stays pinned to a specific release and verifies downloaded assets against the release checksum.
- Profile entrypoints (`cli/profiles/claude/CLAUDE.md`, `cli/profiles/codex/AGENTS.md`) must stay ≤ 50 lines with no operational section headings. Enforced by `packaging/validators/validate-agent-guidance.py`.

## Required checks

After changing profiles, installer logic, guidance, validation, or installable tooling:

```bash
uv run packaging/validators/validate-install-package.py   # layout check
uv run packaging/validators/validate-agent-guidance.py    # profile line-limit + anchor check
uv run --group dev pytest                                  # unit tests
```

For an end-to-end install smoke test against a real target repo:
```bash
python cli/install-fabric-agent --profile all --target <target-repo> --dry-run
python cli/install-fabric-agent --profile all --target <target-repo> --check
```

## Commit / PR handoff

State what changed, which validations were run, whether a target-repo smoke test was performed, and any failures or limitations encountered.
