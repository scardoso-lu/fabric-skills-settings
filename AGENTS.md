# Fabric Agent Pack - Codex Contributor Guidance

This repository is the source package and installer for Microsoft Fabric agent profiles. It is not the runtime workspace for Fabric projects. Install a profile into a target repository with `bin/install-fabric-agent`, then run Codex from that target repository root.

## Session Start

1. Read `memory/MEMORY.md`.
2. Read `memory/project.md` if it exists.
3. Mention relevant context briefly, then address the request.

## Source Package Layout

| Path | Purpose |
|---|---|
| `profiles/skills/` | Vendor-neutral skill source installed to `.agents/skills/` for Codex and `.claude/skills/` for Claude. |
| `profiles/codex/` | Codex-native install assets: `AGENTS.md`, `.codex/agents`, and `.codex/config.toml`. |
| `profiles/claude/` | Claude-native install assets: `CLAUDE.md`, `.claude/agents`, and `.claude/settings.local.json`. |
| `profiles/shared/project-layout/` | Shared target scaffolding installed into target repositories. Target tooling lives under `tool/`. |
| `profiles/shared/memory/` | Shared installed memory seed files. Runtime profile sharing is limited to `memory/`. |
| `tool/` | Source-package mirror of installable target tooling. Must stay byte-for-byte aligned with `profiles/shared/project-layout/tool/`. |
| `bin/` | Source-package-only installer and validators. These files are not installed into target repositories. |
| `fabric_skills_settings/` | Pip-installable Python package. `_installer.py` mirrors `bin/install-fabric-agent`; `profiles/` is bundled into the wheel as `_profiles/` by hatchling. |
| `rules/` and `templates/` | Source material for Fabric safety, data engineering, runbooks, and human-facing templates. Rules are mirrored into installed target repos under `memory/rules/`. |

## Skill Source

Skill source files live only under `profiles/skills/`. The installer copies that same tree to `.agents/skills/` for Codex and `.claude/skills/` for Claude.

Installed skills:

- `fabric-ingest`
- `fabric-transform`
- `fabric-model`
- `fabric-validate`
- `fabric-notebook-loop`
- `fabric-ops`
- `fabric-pipeline`
- `mock-data`
- `semantic-model`
- `prd`
- `grill-me`
- `git-commit`
- `caveman`

## Installed Target Tooling

The installer copies `profiles/shared/project-layout/tool/` into target repositories as `tool/`:

| Target path | Purpose |
|---|---|
| `tool/setup/` | Human one-time setup, Fabric CLI sandbox wrappers, and read-only inventory helpers. Agents verify setup state; they do not run setup repair. |
| `tool/data/` | Deterministic synthetic CSV generator for staged topics. |
| `tool/notebook/` | Notebook build, deploy, smoke-test, fetch, run, and monitor helpers. |
| `tool/pipeline/` | Data Factory pipeline create, update, run, status, list, and test helper. |
| `tool/lakehouse/` | Lakehouse table and schema inspection helper. |
| `tool/semantic-model/` | Fabric Semantic Model inspection via sempy.fabric: lists models and shows tables, DAX measures, and relationships. |
| `tool/validate/` | Local pipeline-lineage validators. |
| `tool/mcp/` | Fabric MCP server used by installed agent profiles. |
| `tool/pre-commit-check.ps1` / `tool/pre-commit-check.sh` | Completion check used by developer guidance before reporting done. |

## File Scanning

When searching or globbing files in this repository, always exclude `.venv/`. It contains third-party packages and will produce irrelevant matches and slow scans.

## Development Rules

- Keep vendor-specific runtime assets inside their profile folders; do not put runtime Claude assets at repository root `.claude/` or runtime Codex assets outside `profiles/codex/`.
- Keep skill source files only under `profiles/skills/`; this is the single source copied to both `.claude/skills/` and `.agents/skills/`.
- Profiles own agents, skills, entrypoint guidance, and settings. Shared runtime state is `memory/` only.
- Do not reintroduce the wrapper runtime model or external-wrapper path operation into installed profile guidance.
- Add or change installable helper files in both `tool/<area>/...` and `profiles/shared/project-layout/tool/<area>/...`; `bin/validate-install-package.py` enforces mirror parity.
- If installer refresh behavior must recognize a helper, update `REFRESHABLE_SCAFFOLD_MARKERS` in both `bin/install-fabric-agent` and `fabric_skills_settings/_installer.py`.
- When modifying installer logic, keep `bin/install-fabric-agent` and `fabric_skills_settings/_installer.py` in sync. Run `uv build` to verify the wheel bundles the correct content.
- Never commit `.env`, credentials, tokens, connection strings, data files, logs, generated Fabric notebook bundles, or `__pycache__/`.
- Use placeholders only in `.env.example` files.
- Fabric CLI wrappers and helpers must not execute caller-controlled binaries. Do not reintroduce `FAB_BIN`, PATH-based `fab` discovery, or arbitrary `fab` command resolution.
- Fabric credentials must be passed through environment variables or approved secret stores, never command-line arguments.
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

Do not run source-package validators from an installed target repository; they are not installed there.

## Commit / PR Handoff

Summarize what changed, which validations were run, whether a target-repo smoke test was performed, and any validation failures or limitations encountered.
