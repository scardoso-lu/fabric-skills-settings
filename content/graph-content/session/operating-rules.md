---
name: operating-rules
description: Non-negotiable per-session rules covering secrets, commits, packaging, file boundaries, and silver-bronze trust.
kind: content
links:
  - rules/security
  - rules/data-engineering
  - rules/fabric-platform
---

# Operating rules

These rules apply to every Fabric session, regardless of topic.

- Never ask for, echo, store, or commit credentials, tokens, connection strings, or real Fabric IDs.
- Never commit `.env`, `workspaces.json`, data files, logs, `fabric_notebooks/`, or generated build intermediates.
- Humans must create the Fabric workspace and any lakehouses first. Resource IDs are discovered automatically via `python tool/workspace/init.py`.
- Agents may create or update notebook items and workspace folders automatically via `tool/notebook/deploy.py`.
- Agents must not run `tool/setup/setup.ps1` or `tool/setup/setup.sh`; they verify setup state and report blockers.
- All Fabric CLI/API access must route through `tool/setup/fab-sandbox.ps1` on Windows or `bash tool/setup/fab-sandbox` on Linux/Mac, or through a repo helper that uses that wrapper.
- Use `memory/rules/fabric-platform.md` ([[rules/fabric-platform]]), `memory/rules/data-engineering.md` ([[rules/data-engineering]]), and `memory/rules/security.md` ([[rules/security]]) as active runtime rules.
- Source contracts belong in notebook `# %% [contract]` cells as Python dataclasses, not YAML files.
- Thresholds belong in notebook `# %% [parameters]` cells so Fabric pipeline parameters can override them.
- Keep every layer in its own notebook: `download_<source>.py`, `bronze_<source>.py`, `dq_bronze_<source>.py`, then optionally `silver_<source>.py`, `dq_silver_<source>.py`, `features_<source>.py`, `dq_features_<source>.py`, `train_<source>.py`, `predict_<source>.py`. Never collapse two layers into one notebook.
- If no source files exist for a new or demo topic, use the `mock-data` skill and `python tool/data/mock-data-generator.py`. Always pass `--schema '<json>'` or `--schema-file <path>` derived from the target table.
- Silver and downstream notebooks must NOT trust bronze column types — bronze tables drift via `mergeSchema=true`. Verify with `DESCRIBE TABLE bronze_<source>` before authoring, and derive computable columns (date, hour, quarter) from authoritative timestamps rather than casting bronze. See `memory/skill-fixes/silver-do-not-trust-bronze-types.md`.
