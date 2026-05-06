# Project Memory

This file is the index. **Read it at the start of every session.**
Update the relevant file whenever you make a decision, build something, or change platform state.
Memory persists across sessions — future agents depend on what you write here.

## How to Use

| When | What to update |
|---|---|
| Session start | Read this file. Check `project.md` for active context. |
| Target repo confirmed | Add row to `memory/platform.md` → Target Repository table |
| Target repo modified | Update `memory/project.md` with files changed, branch, purpose |
| New Fabric item created | Add entry to `memory/platform.md` |
| Pipeline built or changed | Update `memory/project.md` + add/update `memory/runbooks/<pipeline>.md` |
| Architecture decision made | Append to `memory/decisions.md` |
| Security review completed | Add entry to `memory/security/<scope>.md` |
| Validation run | Update pipeline status in `memory/project.md` |

## Memory Files

- [Project State](memory/project.md) — active pipelines, known issues, current focus
- [Platform Inventory](memory/platform.md) — Fabric workspaces, lakehouses, warehouses, notebooks
- [Decisions](memory/decisions.md) — architecture and design decisions with rationale
- [Runbooks](memory/runbooks/) — one `.md` per scheduled pipeline
- [Security](memory/security/) — Key Vault refs, access decisions, sensitive field registry

## Format for New Entries

Keep entries dated and short. Lead with the fact, not the explanation.

```markdown
<!-- YYYY-MM-DD -->
**Pipeline**: orders-bronze
**Status**: PASS — 14,832 rows, 0 null PKs, 0.3% quarantine rate
```
