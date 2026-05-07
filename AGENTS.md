# Fabric Agent Pack — Codex Contributor Guidance

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
| `profiles/shared/` | Shared target scaffolding. Runtime sharing is limited to `memory/`; neutral project tooling/scaffolding may also be installed. |
| `bin/install-fabric-agent` | Profile-aware installer for target git repositories. |
| `bin/validate-install-package.py` | Validates the vendor-native profile package layout. |
| `rules/` and `templates/` | Source material for Fabric safety, data engineering, and human-facing templates. |

## Development Rules

- Keep vendor-specific runtime assets inside their profile folders; do not put runtime Claude assets at repository root `.claude/` or runtime Codex assets outside `profiles/codex/`.
- Profiles own agents, skills, entrypoint guidance, and settings. Shared runtime state is `memory/` only.
- Do not reintroduce the wrapper runtime model or external-wrapper path operation into installed profile guidance.
- Never commit `.env`, credentials, tokens, connection strings, data files, logs, or generated Fabric notebook bundles.
- Use placeholders only in `.env.example` files.
- After changing profiles, installer logic, guidance, or validation, run:
  - `python3 bin/validate-install-package.py`
  - `python3 bin/validate-agent-guidance.py`
  - an installer smoke test against a disposable git repo.

## Commit / PR Handoff

Summarize what changed, which validations were run, and whether a target-repo smoke test was performed.
