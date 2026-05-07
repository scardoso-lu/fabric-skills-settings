# Microsoft Fabric Data Engineering — Codex Profile

This repository is the runtime workspace. Work from this repo root; do not use an external wrapper path as the runtime root.

## Session Start

1. Read `memory/MEMORY.md`.
2. Read `memory/project.md`.
3. Mention relevant context briefly, then address the request.

## Repository Layout

- Source notebooks: `src/notebooks/*.py`
- Generated Fabric notebook bundles: `fabric_notebooks/`
- Sandbox data: `data/sandbox/`
- Filled contracts and project docs: `contracts/`, `runbooks/`, `docs/`
- Shared project memory: `memory/`

## Operating Rules

- Sandbox Fabric work only unless an operator explicitly approves production handoff.
- Never ask for, echo, store, or commit credentials, tokens, connection strings, or real Fabric IDs.
- Never commit `.env`, data files, logs, generated notebook bundles, or local notebook outputs.
- Humans create Fabric items first; agents may update code/configuration for existing sandbox items after the human provides item names.
- Source contracts belong in notebook `# %% [contract]` cells as Python dataclasses, not YAML files.
- Thresholds belong in notebook `# %% [parameters]` cells so Fabric pipeline parameters can override them.
- Keep ingestion and data quality separate: `bronze_<source>.py` ingests, `dq_bronze_<source>.py` validates.

## Skills

Use repo skills in `.agents/skills/`:

- `fabric-ingest` for source-to-Bronze ingestion.
- `fabric-transform` for Silver transformations and MERGE patterns.
- `fabric-model` for Gold facts, dimensions, KPIs, and semantic models.
- `fabric-validate` for independent DQ checks.
- `fabric-notebook-loop` for local `.py` to Fabric notebook iteration.
- `fabric-ops` for orchestration, VACUUM, inventory, and platform operations.

## Agents

Project-scoped Codex custom agents live in `.codex/agents/*.toml`. Use the role that matches the work:

- `orchestrator` scopes and routes.
- `developer` implements.
- `tester` validates independently.
- `operator` reviews security, PII, access, and production handoff.
