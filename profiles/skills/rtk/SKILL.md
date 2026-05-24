---
name: rtk
description: Prefix shell commands with rtk to apply the token-optimizing proxy (60–90% savings on Git, pytest, ruff, Fabric CLI, file ops).
---

# RTK Token Optimizer

RTK reduces token consumption 60–90% by filtering and compressing shell output before it reaches the AI.

- **Claude Code:** The Bash hook intercepts commands automatically — no manual prefix needed.
- **Codex:** No hook is available — prefix commands manually with `rtk`.

## Golden Rule

Prefix every shell command with `rtk`. RTK applies its filter if one exists; otherwise the command runs unchanged.

## Key Commands for This Project

| Workflow | Command |
|---|---|
| Git | `rtk git status` · `rtk git log` · `rtk git diff` |
| Python / ruff | `rtk pytest` · `rtk ruff check` · `rtk pip` |
| Fabric CLI | `rtk bash tool/setup/fab-sandbox ...` or `rtk powershell -File tool/setup/fab-sandbox.ps1 ...` |
| Files | `rtk ls` · `rtk find` · `rtk grep` |
| Build | `rtk tsc` · `rtk cargo build` |

## Analytics

- `rtk gain` — token savings summary for this session
- `rtk discover` — scan shell history to find new optimization opportunities
- `rtk session` — adoption tracking
