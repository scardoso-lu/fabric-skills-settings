---
name: skills-index
description: Catalogue of installed skills with one-liner descriptions. Use to pick the right skill before starting work.
kind: content
links:
  - skills/rtk
  - skills/fabric-ingest
  - skills/fabric-transform
  - skills/fabric-model
  - skills/fabric-validate
  - skills/fabric-notebook-loop
  - skills/fabric-ops
  - skills/fabric-pipeline
  - skills/mock-data
  - skills/semantic-model
  - skills/prd
  - skills/grill-me
  - skills/git-commit
  - skills/caveman
---

# Skills index

Use these skills via the Claude Code skill machinery (`.claude/skills/<name>/SKILL.md`) or the Codex skill loader (`.agents/skills/<name>/SKILL.md`).

- `rtk` — token-optimizing shell proxy. Prefix every shell command with `rtk` (Claude Code applies it automatically via the Bash hook). See [[skills/rtk]].
- `fabric-ingest` — source-to-Bronze ingestion. See [[skills/fabric-ingest]].
- `fabric-transform` — developer-owned Silver/Gold Spark transformations and MERGE patterns; rule anchor: DE-06. See [[skills/fabric-transform]].
- `fabric-model` — developer-owned Gold facts, dimensions, KPIs, and semantic-model-aligned outputs; rule anchor: FP-08. See [[skills/fabric-model]].
- `fabric-validate` — tester-owned independent DQ checks; rule anchor: DE-04. See [[skills/fabric-validate]].
- `fabric-notebook-loop` — local `.py` to Fabric notebook iteration. See [[skills/fabric-notebook-loop]].
- `fabric-ops` — orchestration, VACUUM, inventory, and platform operations. See [[skills/fabric-ops]].
- `fabric-pipeline` — creating, deploying, and testing the Data Factory pipeline that chains topic notebooks end-to-end. See [[skills/fabric-pipeline]].
- `mock-data` — deterministic synthetic sandbox CSV files when no real source exists. See [[skills/mock-data]].
- `semantic-model` — listing and inspecting Fabric Semantic Models before writing DAX or mapping Gold outputs to KPIs. See [[skills/semantic-model]].
- `prd` — implementation-ready requirements documents. See [[skills/prd]].
- `grill-me` — stress-testing a plan or design through one-question-at-a-time interrogation. See [[skills/grill-me]].
- `git-commit` — focused conventional commits when the human explicitly asks for a git commit. See [[skills/git-commit]].
- `caveman` — ultra-compressed responses when the user asks for caveman mode or lower token usage. See [[skills/caveman]].
