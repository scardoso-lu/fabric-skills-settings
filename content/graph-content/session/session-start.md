---
name: session-start
description: Per-session read order after the setup gate passes. Lists what to traverse before touching any topic.
kind: content
links:
  - graph-content/session/operating-rules
  - graph-content/layout/directory-layout
  - graph-content/layout/tool-layout
  - graph-content/workflow/notebook-workflow
  - graph-content/indexes/skills-index
  - graph-content/integrations/rtk
---

# Session start — traversal order

After the setup gate ([[graph-content/entry]]) passes, use the graph MCP server as the project knowledge interface. Do not read project markdown files under `memory/` directly just to discover context; those files are graph backing storage.

Use the graph tools with their full MCP names as exposed by the client, for example Codex `mcp__fabric_graph__.graph_get_entry` / `graph_get_node` / `graph_get_linked` / `graph_search`, or the equivalent `fabric-graph` MCP tool names in other clients.

Traversal order before addressing the user's request:

1. Call `graph_get_linked` for the current node and read relevant neighbors with `graph_get_node`.
2. Start from [[graph-content/session/operating-rules]], then follow nodes for workflow, layout, tools, skills, rule files, skill-fixes, and topic context as needed.
3. Use `graph_search` only when no linked node looks relevant or when a fresh entry point is needed for a named topic, rule, skill-fix, or source.
4. If the request concerns a specific topic, discover topic nodes through graph links or `graph_search`; do not guess node ids. Per-topic state lives only as graph nodes, not as `memory/<topic>/...` files.
5. Mention relevant context briefly, then address the request and cite the graph node ids used.

Graph write rules:

- To author graph knowledge, use `graph_create_node` and then `graph_add_edge` to link it.
- To modify graph knowledge, use `graph_update_node` rather than editing markdown backing files directly.
- To remove graph knowledge, use `graph_delete_node` or `graph_remove_edge` only when the user explicitly asks for deletion/removal.
- All graph write operations re-serialize the graph atomically; direct file edits are for non-graph project artifacts only.

From here, the next traversal step depends on the request:

- Authoring or modifying notebooks → [[graph-content/workflow/notebook-workflow]]
- Where things live on disk → [[graph-content/layout/directory-layout]]
- Which tool to invoke for what → [[graph-content/layout/tool-layout]]
- Picking the right skill → [[graph-content/indexes/skills-index]]
- Shell tooling expectations → [[graph-content/integrations/rtk]]
