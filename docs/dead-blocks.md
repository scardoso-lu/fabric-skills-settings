# Dead Blocks

Files and directories in this source package that are **never directly read by agents** in a target repository. Derived from the installed-file mapping in `bin/install-fabric-agent` and the auto-load sequences in `docs/setup-autoload.md`.

## Category 1 — Source-only: not installed to target repos

These files exist in the source package for maintainers and documentation purposes. No installed agent file references their paths, and they are never copied to target repos by the installer.

| Path | Why it exists | Why agents can't reach it |
|---|---|---|
| `rules/data-engineering.md` | Canonical reference for DE-* rule codes | Not installed; rule codes are embedded inline in skill/agent guidance |
| `rules/fabric-platform.md` | Canonical reference for FP-* rule codes | Not installed; FP-* codes embedded inline |
| `rules/security.md` | Canonical reference for SEC-*/DATA* codes | Not installed; operator.md duplicates the full OWASP checklist inline |
| `templates/runbook.md` | Runbook format reference | Not installed; fabric-ops SKILL.md says "use runbook.md format" but the file is absent in target repos |
| `templates/security-review.md` | Security audit template | Not installed; operator.md has the checklist embedded |
| `templates/data-quality-checklist.md` | DQ handoff template | Not installed |
| `templates/access-review.md` | Access control audit template | Not installed |
| `templates/incident-report.md` | Incident documentation template | Not installed |
| `templates/pipeline-brief.md` | Pipeline design brief template | Not installed |
| `templates/release-checklist.md` | Release validation template | Not installed |
| `memory/MEMORY.md` (root) | Source-repo operational memory | Not installed; target repos get `profiles/shared/memory/MEMORY.md` instead |
| `memory/project.md` (root) | Source-repo project state | Not installed |

## Category 2 — Installed but never invoked by any skill

These files are installed to target repos (agents can read them), but no skill or agent SKILL.md currently instructs an agent to call them.

| Path in target repo | Source path | Gap |
|---|---|---|
| `tool/validate/source-contract.py` | `profiles/shared/project-layout/tool/validate/source-contract.py` | No skill references this tool. Validates `contracts/*.yaml` shape but no skill triggers it. |
| `tool/setup/setup.ps1` / `setup.sh` | `profiles/shared/project-layout/tool/setup/setup.ps1/sh` | Human-run once; agents are told to check `.env` and `fab` state but not to re-run setup themselves. |
| `tool/setup/fabric-inventory-readonly` / `.ps1` | `profiles/shared/project-layout/tool/setup/fabric-inventory-readonly*` | Human-run discovery helper; no skill invokes it. |
| `tool/pre-commit-check.ps1` / `.sh` | `profiles/shared/project-layout/tool/pre-commit-check.ps1/sh` | Pre-commit runner; no skill or agent guidance currently references it. |

## Category 3 — Broken reference in an installed file

These are references inside installed files that point to paths that do not exist in target repos.

| File | Reference | Issue |
|---|---|---|
| `.claude/agents/developer.md` (line 37) | `python bin/validate/pipeline-lineage.py` | `bin/` is a source-package-only directory. In target repos the correct path is `python tool/validate/pipeline-lineage.py`. The skill file (`fabric-ingest/SKILL.md`) already uses the correct path. |

## Category 4 — Codex skills: duplicate of Claude skills

The `profiles/codex/skills/*/SKILL.md` files are identical in content to `profiles/claude/skills/*/SKILL.md`. They are installed to different paths (`.agents/skills/` vs `.claude/skills/`), so the duplication is intentional — but any change to a skill must be made in both locations.

| Source (Claude) | Source (Codex) | Target (Claude) | Target (Codex) |
|---|---|---|---|
| `profiles/claude/skills/<s>/SKILL.md` | `profiles/codex/skills/<s>/SKILL.md` | `.claude/skills/<s>/SKILL.md` | `.agents/skills/<s>/SKILL.md` |

The validator (`bin/validate-install-package.py`) should enforce parity between the two source trees.

## Summary

| Category | Count | Severity |
|---|---|---|
| Source-only, not installed | 12 files | Informational — by design for maintainer reference |
| Installed but no skill trigger | 4 tools | Low — tools exist but have no automated entry point |
| Broken reference in installed file | 1 (`bin/` path in developer.md) | Medium — will cause `command not found` if the developer agent follows it literally |
| Duplicate skill trees (codex/claude) | 13 × 2 = 26 files | Informational — intentional, but requires dual maintenance |
