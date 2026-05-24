---
name: workspace-management
description: Workspace discovery, switching, and artifact transfer via tool/workspace/{init,switch,transfer}.py. workspaces.json is the only source of IDs.
kind: content
links:
  - graph-content/layout/tool-layout
---

# Workspace management

All workspace and resource IDs come exclusively from `workspaces.json` — never from manually entered values or `.env` edits.

## Discovery (once per session, after auth)

```bash
python tool/workspace/init.py
```

Queries the Fabric API for every accessible workspace and its Lakehouses, Warehouses, Notebooks, and DataPipelines. Writes the full API response to `workspaces.json`. Run this if `workspaces.json` is missing or stale.

## Listing and switching

```bash
python tool/workspace/switch.py list           # show all discovered workspaces; marks active
python tool/workspace/switch.py <displayName>  # set active workspace; writes resource IDs to .env
```

`switch.py` writes `FABRIC_WORKSPACE_ID`, `FABRIC_LAKEHOUSE_<NAME>`, `FABRIC_WAREHOUSE_<NAME>`, and `FABRIC_WAREHOUSE_HOST` into the auto-generated section of `.env`. Do not edit these values manually.

After switching, remind the human to reload their Claude Code session — the MCP server reads `.env` only at startup.

## Transferring artifacts between workspaces

Transfer does **not** change the active workspace. Lakehouses and warehouses are matched by `displayName` (e.g. "Bronze", "Silver", "Gold", "DataWarehouse"). If a name is not found in the target workspace, the tool prompts the user for the ID — never abort silently.

```bash
# Transfer a single notebook to another workspace
python tool/workspace/transfer.py --notebook <name>  --to <displayName>

# Transfer all notebooks for a topic
python tool/workspace/transfer.py --topic    <topic> --to <displayName>

# Transfer a pipeline (notebooks must already be deployed in the target workspace)
python tool/workspace/transfer.py --pipeline <topic> --to <displayName>
```
