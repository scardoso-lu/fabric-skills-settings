# Dead Blocks

Action register for installed files or guidance paths that still need a decision, wiring, or periodic review. Keep this file limited to open work only; remove entries once fixed or explicitly accepted as design.

## Open Items

None.

## Accepted Boundaries

| Item | Decision |
|---|---|
| `tool/setup/setup.ps1` / `tool/setup/setup.sh` | Always human-triggered. Agents verify setup state only and must not invoke setup repair or re-run setup scripts. |

## Recently Cleared

No follow-up required for the cleared items below unless they regress:

- Broken `bin/validate/pipeline-lineage.py` reference: fixed to `tool/validate/pipeline-lineage.py`.
- YAML `source-contract.py`: removed in favor of notebook `@dataclass` contracts.
- `pre-commit-check.ps1/sh`: wired into developer and notebook-loop guidance.
- `fabric-inventory-readonly`: wired into operator DATA2 and DATA9 review guidance.
- Skill source duplication: removed; `profiles/skills/` is the single source copied to Claude and Codex target skill paths.
- Direct `fab` examples in `fabric-ops` and `fabric-platform` rules: replaced with `tool/setup/fab-sandbox` examples.
