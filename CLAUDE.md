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
