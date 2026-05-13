# Project Memory

This is shared, vendor-neutral project memory for Fabric work in this repository. Read it at the start of every Claude Code or Codex session, then check `memory/project.md` for active context.

## Files

- `memory/project.md` — active pipelines, known issues, current focus.
- `memory/platform.md` — Fabric workspaces, lakehouses, warehouses, notebooks, source systems.
- `memory/decisions.md` — architecture and implementation decisions.
- `memory/runbooks/` — scheduled pipeline runbooks and run results.
- `memory/security/` — security reviews, access decisions, sensitive field registry.

## Update Rules

- Keep entries dated and short.
- Lead with the fact, then add details.
- Never store real credentials, tokens, connection strings, workspace IDs, or lakehouse IDs.
- Use item names and Key Vault reference names when needed; do not store secrets or Fabric IDs in memory.
