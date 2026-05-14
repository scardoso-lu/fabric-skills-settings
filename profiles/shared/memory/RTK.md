# RTK Token Optimizer

RTK reduces token consumption 60–90% by filtering and compressing shell output before it reaches the AI. The Claude Code hook intercepts Bash commands automatically — no manual prefix needed.

## Golden Rule

Prefix every shell command with `rtk`. RTK applies its filter if one exists; otherwise the command runs unchanged.

## Key Commands for This Project

| Workflow | Command |
|---|---|
| Git | `rtk git status` · `rtk git log` · `rtk git diff` |
| Python / ruff | `rtk pytest` · `rtk ruff check` · `rtk pip` |
| Fabric CLI | `rtk fab` |
| Files | `rtk ls` · `rtk find` · `rtk grep` |
| Build | `rtk tsc` · `rtk cargo build` |

## Analytics

- `rtk gain` — token savings summary for this session
- `rtk discover` — scan shell history to find new optimization opportunities
- `rtk session` — adoption tracking
