---
name: entry
description: Mandatory setup gate. Read first in every session before any other action; blocks all Fabric work if checks fail.
kind: entry
links:
  - graph-content/session/session-start
---

# Mandatory setup gate

This is the mandatory setup gate, run before accepting any Fabric work, to verify the local `.env`, the local Fabric CLI `fabric-vibe *`, and the active workspace.

| Check | Pass | Fail — stop and show this |
|---|---|---|
| `.env` exists in project root | file present | Human runs `fabric-vibe setup` from the target repo root. The bootstrap writes `FABRIC_TENANT_ID` and `FABRIC_CLIENT_ID` to `.env`; the secret goes to the OS user environment, never to `.env`. |
| MCP server reachable | `graph_get_entry` returned this node — the server is up. If failure persists due to **network** restriction, escalate and request network access before retrying. |
| Workspace registry | `workspaces.json` exists in project root | Run `fabric-vibe workspace init` from the project root. |
| Active workspace set | `workspaces.json` has an `"active"` field that is not null | Run `fabric-vibe workspace switch list` to see options, then `fabric-vibe workspace switch <displayName>` to choose. |
| Active workspace confirmed | Human has confirmed the active workspace this session | Show `workspaces.json["active"]` value; **stop and ask**: "Active workspace is `<displayName>`. Proceed with this workspace?" — do not start any build, deploy, or pipeline action until confirmed |

Do **not** read `.env` contents or print values. Check only that the file and key names are present. Do **not** echo workspace IDs or resource IDs — refer to workspaces and resources by `displayName` only. `FABRIC_WORKSPACE_ID` and other workspace identifiers must never appear in tool output.

All fabric instructions must use `fabric-vibe *`. If the command you are trying is not covered in this cli, it means you don't have permissions and should stop. Highlight all security risks if you try any other command then ask for user instruction.

A workspace confirmation covers the whole session. Re-confirm only after the human explicitly runs `fabric-vibe workspace switch`.

If **any check fails**, respond exactly:
> "Setup incomplete. Fix the item(s) above - I will not start any Fabric task until setup passes."

Then stop. Do not attempt workarounds or partial execution.

Humans must create the Fabric workspace and any **lakehouse** items first. Agents may create or update **notebook** items and workspace folders automatically via `fabric-vibe notebook deploy`.

Once the gate passes, follow [[graph-content/session/session-start]] for the per-session read order.
