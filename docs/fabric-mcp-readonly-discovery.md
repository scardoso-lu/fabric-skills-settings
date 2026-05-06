# Fabric MCP Read-only Discovery Workflow

Use this workflow when an MCP-capable client is configured for Microsoft Fabric discovery. It is read-only by default and keeps humans in control of environment-specific IDs.

## Scope

Allowed read-only discovery:

- List workspaces visible to the authenticated human.
- List Fabric items in a confirmed sandbox workspace.
- Inspect item metadata needed to fill `.env` placeholders manually.
- Compare discovered item names with `.codex-fabric/memory/platform.md`.

Not allowed in this workflow:

- Creating, updating, or deleting Fabric items.
- Granting permissions or changing roles.
- Writing `.env` automatically.
- Asking the user to paste bearer tokens, tenant IDs, or workspace IDs into chat.
- Production handoff or production workspace operations.

## Human/agent sequence

1. Human configures the MCP client locally.
2. Agent reads `.codex-fabric/MEMORY.md`, `.codex-fabric/memory/project.md`, and `.codex-fabric/memory/platform.md`.
3. Agent requests read-only discovery only: list workspaces and list items.
4. Human confirms which discovered workspace is the sandbox workspace.
5. Human copies approved IDs into `.env` locally if needed.
6. Agent updates memory only with non-sensitive names/purpose and placeholder references, not real credentials or tokens.

## Prompt examples

- "Use Fabric MCP read-only tools to list sandbox workspaces; do not create or update anything."
- "Use Fabric MCP read-only tools to list lakehouses in the confirmed sandbox workspace."
- "Compare discovered sandbox item names with `.codex-fabric/memory/platform.md` and tell me what memory rows are missing."

## Fallback without MCP

If MCP is unavailable, the human can run:

```bash
bin/fabric-inventory-readonly
bin/fabric-inventory-readonly --workspace-id "$FABRIC_WORKSPACE_ID" --items
```

The fallback is also read-only and never writes `.env`, memory, or Fabric resources.
