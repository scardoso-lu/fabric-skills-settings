# Microsoft Fabric Data Engineering — Claude Code Profile

This repository is the runtime workspace. Work from this repo root; do not use an external wrapper path as the runtime root.

## Session Start

1. Read `memory/MEMORY.md`.
2. Read `memory/project.md`.
3. If `bin/setup/setup.ps1`, `bin/setup/setup.sh`, or `.env` is missing, report:
   "Configuration is missing in this repo to work correctly. Here is how to fix:"
   Then show Windows commands first: `.\bin\setup\setup.ps1`, edit `.env` to set `FABRIC_WORKSPACE_ID`, and rerun `.\bin\setup\setup.ps1`.
   Also show the bash alternative: `bash bin/setup/setup.sh`, edit `.env`, and rerun `bash bin/setup/setup.sh`.
   Do not read `.env`; checking that the file exists is enough.
4. Mention relevant context briefly, then address the request.

## Role Agents

Use project subagents in `.claude/agents/`:

- `orchestrator` scopes and routes.
- `developer` implements.
- `tester` validates independently.
- `operator` reviews security, PII, access, and production handoff.

## Skills

Use project skills in `.claude/skills/` for Fabric ingestion, transformation, modeling, validation, notebook iteration, and operations.

## Safety

Never ask for, echo, store, or commit credentials, tokens, connection strings, source data extracts, local `.env` files, generated notebook bundles, logs, or real Fabric IDs. Humans create Fabric items first; agents work only with existing sandbox items unless operator approval explicitly covers a handoff review.
