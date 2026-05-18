# Fabric Agent Pack - Claude Contributor Guidance

This repository maintains and installs Microsoft Fabric agent profiles. It is not the runtime workspace for Fabric projects. Install `profiles/claude` and/or `profiles/codex` into a target repository, then run Claude Code or Codex from the target repository root.

## Session Start

1. Read `memory/MEMORY.md`.
2. Read `memory/project.md` if it exists.
3. Mention relevant context briefly, then address the request.

## Maintainer Focus

- Keep Claude runtime assets under `profiles/claude/`.
- Keep Codex runtime assets under `profiles/codex/`.
- Keep shared target memory and neutral scaffolding under `profiles/shared/`.
- Do not add root `.claude/agents`, root `skills/`, or wrapper-style target repo instructions.
- Do not reintroduce external-wrapper runtime guidance.

## Source Package Layout

Scripts at the root of `bin/` are source-package-only. They validate and install profiles; they are not copied to target repositories.

| Script | Purpose |
|---|---|
| `bin/install-fabric-agent` | Installs profiles into a target repository. |
| `bin/validate-install-package.py` | Validates the installer package layout and `tool/` mirror parity. |
| `bin/validate-agent-guidance.py` | Validates profile guidance content. |

The package is also distributed via pip as `fabric-skills-settings`. The pip-installable entry point is `fabric_skills_settings/_installer.py`, which mirrors `bin/install-fabric-agent` but resolves bundled profiles from `Path(__file__).parent / "_profiles"` instead of the source tree. `profiles/` is bundled into the wheel automatically by hatchling's `force-include` — no extra steps are needed when updating profile files.

**When modifying installer logic, update both `bin/install-fabric-agent` and `fabric_skills_settings/_installer.py` together.** Build and inspect the wheel with `uv build` to verify bundled content.

Installable target tooling lives under `tool/` in this source repo and must mirror `profiles/shared/project-layout/tool/` exactly. The installer copies the `profiles/shared/project-layout/tool/` tree into target repositories as `tool/`.

| Tool path | Who uses it in target repo | Contains |
|---|---|---|
| `tool/setup/` | Human once, agents for checks | `setup.ps1/sh`, `fab-sandbox`, `fabric-inventory-readonly`. |
| `tool/data/` | Developer agent | `mock-data-generator.py` for deterministic synthetic CSV; `--schema` or `--schema-file` required. |
| `tool/notebook/` | Developer agent | `build.py`, `deploy.py`, `smoke-test.ps1/sh`. |
| `tool/pipeline/` | Developer agent | `manage.py` for Data Factory pipeline create, update, run, status, list, and test. |
| `tool/lakehouse/` | Developer agent | `list-tables.py` for table/schema discovery. |
| `tool/semantic-model/` | Developer and tester agents | `inspect.py` for listing and inspecting Fabric Semantic Models via sempy.fabric. |
| `tool/validate/` | Developer agent | `pipeline-lineage.py`, `source-contract.py`. |
| `tool/mcp/` | Infrastructure | `server.py`. |

When adding or changing an installed helper:

1. Edit both `tool/<area>/...` and `profiles/shared/project-layout/tool/<area>/...`.
2. Add new helpers to `MIRRORED_HELPERS` in `bin/validate-install-package.py`.
3. If existing target files should refresh without `--force`, add a `tool/...` marker to `REFRESHABLE_SCAFFOLD_MARKERS` in `bin/install-fabric-agent`.

## Security Rules

- Never commit `.env`, credentials, tokens, connection strings, data files, logs, generated Fabric notebook bundles, or `__pycache__/`.
- Fabric CLI execution must not be caller-controlled. Do not reintroduce `FAB_BIN`, `PATH`-based `fab` discovery, or arbitrary `fab` command resolution.
- Fabric credentials must be passed through environment variables or approved secret stores, never command-line arguments.
- `FABRIC_CLIENT_SECRET` must not be written to `.env`.
- RTK installation must stay pinned to a specific release and verify downloaded assets against that release's checksum before execution or extraction.

## File Scanning

When searching or globbing files in this repository, always exclude `.venv/`. It contains third-party packages and will produce irrelevant matches and slow scans.

## Required Checks

Run these from this source package repo after guidance, profile, installer, validation, or installable tooling changes:

```bash
uv run bin/validate-install-package.py
uv run bin/validate-agent-guidance.py
uv run --group dev pytest
```

Run the unit tests after any change to `tool/notebook/build.py` or `tool/pipeline/manage.py`.

Also smoke-test `bin/install-fabric-agent` against a disposable git repo when installer mappings or profile files change.

Do not run these validators from an installed target repository; they are not installed there. To check an installed target repository, run this from the source package repo:

```bash
python bin/install-fabric-agent --profile all --target /path/to/project-repo --check
```
