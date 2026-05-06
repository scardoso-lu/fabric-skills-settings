# Fabric MCP Read-only Discovery Workflow

Use this workflow when an MCP-capable client is configured for Microsoft Fabric discovery. It is read-only by default and keeps humans in control of environment-specific IDs.

## Scope

Allowed read-only discovery:

- List workspaces visible to the authenticated human.
- List Fabric items in a confirmed sandbox workspace.
- Inspect item metadata needed to fill `.env` placeholders manually.
- Compare discovered item names with `memory/platform.md`.
- Fetch notebook or pipeline IDs **after the human has confirmed the item exists**.

Not allowed in this workflow:

- Creating, updating, or deleting Fabric items.
- Granting permissions or changing roles.
- Writing `.env` automatically.
- Asking the user to paste bearer tokens, tenant IDs, or workspace IDs into chat.
- Production handoff or production workspace operations.

## Item creation rule

**Agents cannot create Fabric items** (notebooks, pipelines, lakehouses, warehouses, etc.).
The human must create items in the Fabric portal or via `fab` CLI before an agent fetches their IDs.

Agents **can** update configuration derived from existing items they have access to — for example, writing the discovered item ID into `.env.example` or into `memory/platform.md` after the human confirms the item name.

## Fetching Fabric IDs — human/agent sequence

Use this pattern any time you need a notebook ID, pipeline ID, or lakehouse ID:

1. **Human creates the item** in the Fabric portal (or confirms it already exists).
2. Human tells the agent: *"The notebook [name] is ready in workspace [name]."*
3. Agent uses the Fabric MCP tool to list items in the confirmed workspace:
   ```
   Use Fabric MCP read-only tools to list notebooks in workspace "[workspace-name]".
   ```
4. Agent finds the item by the name the human provided and surfaces the ID.
5. **Human copies the ID** into `.env` locally (`NOTEBOOK_ITEM_ID=...`).
6. Agent may update `memory/platform.md` with the item name and a placeholder reference (never the real ID).

> Agent must wait for the human to confirm the item exists before attempting to fetch its ID.
> Do not guess IDs or fabricate them from display names.

## Human/agent sequence (general discovery)

1. Human configures the MCP client locally.
2. Agent reads `memory/MEMORY.md`, `memory/project.md`, and `memory/platform.md`.
3. Agent requests read-only discovery only: list workspaces and list items.
4. Human confirms which discovered workspace is the sandbox workspace.
5. Human copies approved IDs into `.env` locally if needed.
6. Agent updates memory only with non-sensitive names/purpose and placeholder references, not real credentials or tokens.

## Prompt examples

- "Use Fabric MCP read-only tools to list sandbox workspaces; do not create or update anything."
- "Use Fabric MCP read-only tools to list lakehouses in the confirmed sandbox workspace."
- "Compare discovered sandbox item names with `memory/platform.md` and tell me what memory rows are missing."
- "The notebook 'orders_bronze' is ready in my sandbox workspace. Fetch its item ID so I can add it to .env."

## Fallback without MCP

If MCP is unavailable, the human can run:

```bash
bin/fabric-inventory-readonly
bin/fabric-inventory-readonly --workspace-id "$FABRIC_WORKSPACE_ID" --items
```

The fallback is also read-only and never writes `.env`, memory, or Fabric resources.
