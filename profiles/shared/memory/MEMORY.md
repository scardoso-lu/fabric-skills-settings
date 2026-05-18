# Project Memory

This is shared, vendor-neutral project memory for Fabric work in this repository. Read it at the start of every Claude Code or Codex session.

## Global files (read every session)

- `memory/notebook-authoring.md` — mandatory notebook authoring rules: file paths, packages, pipeline structure, mssparkutils detection.
- `memory/rules/fabric-platform.md` — Fabric API, auth wrapper, notebook, lakehouse, warehouse, and Delta maintenance rules.
- `memory/rules/data-engineering.md` — pipeline idempotency, lineage, schema evolution, quality, and DAG rules.
- `memory/rules/security.md` — credential, PII, logging, dependency, inventory, and compliance rules.
- `memory/RTK.md` — mandatory project init rule: any file that needs to be read, must use this proxy

## Per-topic files (read when working on a specific topic)

Each data source or business domain gets its own subfolder matching the `workspace/<topic>/` folder name:

- `memory/<topic>/project.md` — active pipelines, known issues, current focus for that topic.
- `memory/<topic>/decisions.md` — topic-specific architecture and implementation decisions.

Example:
```
memory/
  lux_energy_price/
    project.md
    decisions.md
  lux_residence/
    project.md
```

## Supporting directories

- `memory/runbooks/` — scheduled pipeline runbooks and run results.
- `memory/security/` — security reviews, access decisions, sensitive field registry.
- `memory/skill-fixes/` — recorded gaps and workarounds discovered in skills or tools during real work. Read all files here at session start; they take precedence over skill SKILL.md defaults. Write a new entry whenever a skill or tool behaves incorrectly and a fix or workaround is applied.

### skill-fixes entry format

```markdown
---
name: <skill-name>-<issue-slug>
description: <one-line summary of the gap and the fix>
metadata:
  type: feedback
  date: YYYY-MM-DD
---

# Gap: <short title>

## What happened

## Root cause

## Fix applied

## Rule going forward
**Why:** ...
**How to apply:** ...
```

## Update Rules

- Keep entries dated and short.
- Lead with the fact, then add details.
- Never store real credentials, tokens, connection strings, workspace IDs, or lakehouse IDs.
- Use item names and Key Vault reference names when needed; do not store secrets or Fabric IDs in memory.
