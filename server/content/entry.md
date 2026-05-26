---
name: entry
description: Mandatory setup gate. Read first in every session before any other action; blocks all Fabric work if checks fail.
kind: entry
links:
  - graph-content/session/session-start
---

# Mandatory setup gate

This is the mandatory setup gate, run before accepting any Fabric work, to verify the local `.env`, the local Fabric CLI, and the active workspace.

| Check | Pass | Fail — stop and show this |
|---|---|---|
| `.env` exists in project root | file present | Human runs setup: Windows `.\tool\setup\setup.ps1` or Linux/Mac `bash tool/setup/setup.sh`. The script writes `FABRIC_TENANT_ID`, `FABRIC_CLIENT_ID`, and `FABRIC_SERVER_URL` to `.env`; the secret goes to the OS user environment, never to `.env`. |
| MCP server reachable | `graph_get_entry` returned this node — the server is up. If `graph_get_entry` fails: the human starts `docker compose up --build` from the source repo's `server/` directory. If failure persists due to **network** restriction, escalate and request network access before retrying. |
| `fab` installed locally | Run `fab --version` via Bash from the project root. Exit code 0. | Human installs the Fabric CLI: `uv tool install ms-fabric-cli`. |
| `fab` authenticated | Run `fab api workspaces --output_format json` via Bash. Exit code 0 with a workspaces array. | Verify `FABRIC_TENANT_ID`, `FABRIC_CLIENT_ID`, and `FABRIC_CLIENT_SECRET` are set in `.env` / OS environment; re-run `tool/setup/setup.{ps1,sh}`. |
| Workspace registry | `workspaces.json` exists in project root | Run `fabric-cli workspace init` from the project root — queries the Fabric API with the local SPN and writes the complete workspace and resource registry. |
| Active workspace set | `workspaces.json` has an `"active"` field that is not null | Run `fabric-cli workspace switch list` to see options, then `fabric-cli workspace switch <displayName>` to choose. |
| Active workspace confirmed | Human has confirmed the active workspace this session | Show `workspaces.json["active"]` value; **stop and ask**: "Active workspace is `<displayName>`. Proceed with this workspace?" — do not start any build, deploy, or pipeline action until confirmed |

Do **not** read `.env` contents or print values. Check only that the file and key names are present. Do **not** echo workspace IDs or resource IDs — refer to workspaces and resources by `displayName` only. `FABRIC_WORKSPACE_ID` and other workspace identifiers must never appear in tool output.

A workspace confirmation covers the whole session. Re-confirm only after the human explicitly runs `fabric-cli workspace switch`.

If **any check fails**, respond exactly:
> "Setup incomplete. Fix the item(s) above - I will not start any Fabric task until setup passes."

Then stop. Do not attempt workarounds or partial execution.

Humans must create the Fabric workspace and any **lakehouse** items first. Agents may create or update **notebook** items and workspace folders automatically via `fabric-cli notebook deploy`.

Once the gate passes, follow [[graph-content/session/session-start]] for the per-session read order.
