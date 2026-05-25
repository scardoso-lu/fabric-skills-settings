---
name: entry
description: Mandatory setup gate. Read first in every session before any other action; blocks all Fabric work if checks fail.
kind: entry
links:
  - graph-content/session/session-start
---

# Mandatory setup gate

This is the mandatory setup gate, run before accepting any Fabric work, to verify `.env`, `fab`, and `fab auth`, and confirm the active workspace.

| Check | Pass | Fail — stop and show this |
|---|---|---|
| `.env` exists | file present | Human runs setup: Windows `.\tool\setup\setup.ps1` or Linux/Mac `bash tool/setup/setup.sh` |
| `fab` reachable | Windows: `tool\setup\fab-sandbox.ps1 --version` exits 0; Linux/Mac: `bash tool/setup/fab-sandbox --version` exits 0 | Human runs setup; it installs `ms-fabric-cli` via `uv tool install ms-fabric-cli` |
| `fab` authenticated | Windows: `tool\setup\fab-sandbox.ps1 api workspaces --output_format json` exits 0; Linux/Mac: `bash tool/setup/fab-sandbox api workspaces --output_format json` exits 0 | Windows: `tool\setup\fab-sandbox.ps1 auth login`; Linux/Mac: `bash tool/setup/fab-sandbox auth login`. If the check fails due to **network** restriction, escalate and request network access before retrying. |
| Workspace registry | `workspaces.json` present in project root | Run `python tool/workspace/init.py` — queries the Fabric API and writes the complete workspace and resource registry |
| Active workspace set | `workspaces.json` has `"active"` field that is not null | Run `python tool/workspace/switch.py list`, then `python tool/workspace/switch.py <displayName>` |
| Active workspace confirmed | Human has confirmed the active workspace this session | Show `workspaces.json["active"]` value; **stop and ask**: "Active workspace is `<displayName>`. Proceed with this workspace?" — do not start any build, deploy, or pipeline action until confirmed |

Do **not** read `.env` contents or print values. Check only that the file and key names are present. Do **not** echo workspace IDs or resource IDs — refer to workspaces and resources by `displayName` only. `FABRIC_WORKSPACE_ID` and other workspace identifiers must never appear in tool output.

A workspace confirmation covers the whole session. Re-confirm only after the human explicitly runs `switch.py`.

If **any check fails**, respond exactly:
> "Setup incomplete. Fix the item(s) above - I will not start any Fabric task until setup passes."

Then stop. Do not attempt workarounds or partial execution.

Humans must create the Fabric workspace and any **lakehouse** items first. Agents may create or update **notebook** items and workspace folders automatically via `tool/notebook/deploy.py`.

Once the gate passes, follow [[graph-content/session/session-start]] for the per-session read order.
