# Fabric Agent Pack — Claude Contributor Guidance

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

## Source package `bin/` layout

Scripts at the **root of `bin/`** are source-package-only — they validate and install profiles; they are never copied to target repositories:

| Script | Purpose |
|---|---|
| `bin/install-fabric-agent` | Installs profiles into a target repository |
| `bin/validate-install-package.py` | Validates the installer package layout |
| `bin/validate-agent-guidance.py` | Validates profile guidance content |
| `bin/pre-commit-check.ps1/.sh` | Runs both validators as a pre-commit gate |

Scripts under **subdirectories of `bin/`** mirror `profiles/shared/project-layout/bin/` exactly and are installed into every target repository. `bin/validate-install-package.py` enforces that mirror parity. Add new installed scripts to the project-layout subdirectory **and** the matching `bin/` subdirectory, then register them in `MIRRORED_HELPERS` and `REFRESHABLE_SCAFFOLD_MARKERS` in the installer:

| Subdirectory | Who uses it in target repo | Contains |
|---|---|---|
| `bin/setup/` | Human (one-time) | `setup.ps1/sh`, `fab-sandbox`, `fabric-inventory-readonly` |
| `bin/notebook/` | Developer agent | `build.py`, `deploy.py`, `smoke-test.ps1/sh` |
| `bin/validate/` | Developer agent | `pipeline-lineage.py`, `source-contract.py` |
| `bin/mcp/` | Infrastructure | `server.py` |

## Required Checks

Run these from this source package repo after guidance, profile, installer, or validation changes:

```bash
python3 bin/validate-install-package.py
python3 bin/validate-agent-guidance.py
```

Also smoke-test `bin/install-fabric-agent` against a disposable git repo when installer mappings or profile files change.

Do not run these validators from an installed target repository; they are not installed there. To check an installed target repository, run this from the source package repo:

```bash
python3 bin/install-fabric-agent --profile all --target /path/to/project-repo --check
```
