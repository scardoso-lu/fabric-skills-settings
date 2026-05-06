# Agent Guidance Map

This file is the single navigation map for agent runtime guidance. It does not replace the authoritative files; it explains which file owns each kind of instruction and how to check for drift.

## Canonical sources

| Scope | Canonical file(s) | Notes |
|---|---|---|
| Codex runtime behavior | `AGENTS.md` | Self-contained Codex instruction set. Keep aligned with Claude-facing files. |
| Claude runtime behavior | `CLAUDE.md`, `.claude/agents/*.md` | Claude Code entrypoint plus sub-agent specs. |
| Security boundaries | `rules/security.md` | Credential, token, PII, sandbox, audit, and MCP hygiene rules. |
| Data engineering rules | `rules/data-engineering.md` | Idempotency, lineage, DQ gates, schema evolution, and MERGE expectations. |
| Fabric platform rules | `rules/fabric-platform.md` | Fabric auth, async operations, notebook debugging, Spark/SQL patterns. |
| Task skills | `skills/*.md` | Read the relevant skill before implementation or validation. |
| Persistent state | `memory/MEMORY.md`, `memory/*.md` | Read at session start; update after significant work. |
| Human templates | `templates/` | Use instead of inventing new formats. |
| Roadmap scope | *(removed — see git history)* | Completed and in-scope future improvements only. |

## Drift check

Run this before PR handoff when instructions, skills, rules, or docs change:

```bash
python3 bin/validate-agent-guidance.py
```

The check verifies that root runtime docs reference every bundled core skill and that canonical guidance files exist. It is local-only and does not call Fabric or external services.

## Update protocol

1. Update the canonical owner file first.
2. Mirror short references in the other runtime docs if behavior changes.
3. Add or update sub-agent guidance only when the agent role changes.
4. Update memory with a dated note for significant guidance changes.
5. Run `python3 bin/validate-agent-guidance.py` before committing.
