# Fabric Agent Pack - Codex Contributor Guidance

This repository is the source package and installer for Microsoft Fabric agent profiles. It is not the runtime workspace for Fabric projects. Install a profile into a target repository with `bin/install-fabric-agent`, then run Codex from that target repository root.

## Session Start

1. Read `memory/MEMORY.md`.
2. Read `memory/project.md` if it exists.
3. Mention relevant context briefly, then address the request.

## Source Package Layout

| Path | Purpose |
|---|---|
| `profiles/codex/` | Codex-native install assets: `AGENTS.md`, `.agents/skills`, `.codex/agents`, `.codex/config.toml`. |
| `profiles/claude/` | Claude-native install assets: `CLAUDE.md`, `.claude/skills`, `.claude/agents`, `.claude/settings.json`. |
| `profiles/shared/project-layout/` | Shared target scaffolding installed into target repositories. Target tooling lives under `tool/`. |
| `profiles/shared/memory/` | Shared installed memory seed files. Runtime profile sharing is limited to `memory/`. |
| `tool/` | Source-package mirror of installable target tooling. Must stay byte-for-byte aligned with `profiles/shared/project-layout/tool/`. |
| `bin/` | Source-package-only installer and validators. These files are not installed into target repositories. |
| `rules/` and `templates/` | Source material for Fabric safety, data engineering, runbooks, and human-facing templates. |

## Installed Target Tooling

The installer copies `profiles/shared/project-layout/tool/` into target repositories as `tool/`:

| Target path | Purpose |
|---|---|
| `tool/setup/` | Human one-time setup, Fabric CLI sandbox wrappers, and read-only inventory helpers. |
| `tool/data/` | Deterministic synthetic CSV generator for sandbox topics; `--schema` or `--schema-file` always required. |
| `tool/notebook/` | Notebook build, deploy, smoke-test, fetch, run, and monitor helpers. |
| `tool/pipeline/` | Data Factory pipeline create, update, run, status, list, and test helper. |
| `tool/lakehouse/` | Lakehouse table and schema inspection helper. |
| `tool/semantic-model/` | Fabric Semantic Model inspection via sempy.fabric — lists models and shows tables, DAX measures, relationships. |
| `tool/validate/` | Local source-contract and pipeline-lineage validators. |
| `tool/mcp/` | Fabric MCP server used by installed agent profiles. |

## File Scanning

When searching or globbing files in this repository, always exclude `.venv/`. It contains third-party packages and will produce irrelevant matches and slow scans.

## Development Rules

- Keep vendor-specific runtime assets inside their profile folders; do not put runtime Claude assets at repository root `.claude/` or runtime Codex assets outside `profiles/codex/`.
- Profiles own agents, skills, entrypoint guidance, and settings. Shared runtime state is `memory/` only.
- Do not reintroduce the wrapper runtime model or external-wrapper path operation into installed profile guidance.
- Add or change installable helper files in both `tool/<area>/...` and `profiles/shared/project-layout/tool/<area>/...`; `bin/validate-install-package.py` enforces mirror parity.
- If installer refresh behavior must recognize a helper, update `REFRESHABLE_SCAFFOLD_MARKERS` in `bin/install-fabric-agent` with the `tool/...` target path.
- Never commit `.env`, credentials, tokens, connection strings, data files, logs, generated Fabric notebook bundles, or `__pycache__/`.
- Use placeholders only in `.env.example` files.
- Fabric CLI wrappers and helpers must not execute caller-controlled binaries. Do not reintroduce `FAB_BIN`, `PATH`-based `fab` discovery, or arbitrary `fab` command resolution. Use the expected user-local Fabric CLI path and keep credentials out of command-line arguments.
- RTK setup must stay pinned to a specific release and verify downloaded assets against the release checksum before execution or extraction.

## Required Checks

After changing profiles, installer logic, guidance, validation, or installable tooling, run from this source package repo:

```bash
uv run bin/validate-install-package.py
uv run bin/validate-agent-guidance.py
uv run --group dev pytest
```

Run the unit tests after any change to `tool/notebook/build.py` or `tool/pipeline/manage.py`.

For installer or profile-file changes, also check an installed target or run a disposable-target smoke test:

```bash
python bin/install-fabric-agent --profile all --target <target-repo> --check
```

## Commit / PR Handoff

Summarize what changed, which validations were run, whether a target-repo smoke test was performed, and any environment-limited validation failures.
