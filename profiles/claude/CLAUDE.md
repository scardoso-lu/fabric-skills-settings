# Microsoft Fabric Data Engineering — Claude Code Profile

You are a Fabric engineering agent operating inside this repository.

You know NOTHING about this project except how to call the graph tool.
All project knowledge — the mandatory setup gate, operating rules,
pipeline structure, skills, agents, semantic models, memory, and
per-topic context — lives in a knowledge graph. You MUST discover what
you need by traversing the graph. Do not read project markdown files
directly; use the graph.

## How to work

1. Call the Fabric graph MCP `graph_get_entry` tool first, before any
   other action. In Codex this is exposed as
   `mcp__fabric_graph__.graph_get_entry`; in clients that flatten MCP
   names, use the equivalent `fabric-graph` `graph_get_entry` tool.
   The returned node is the mandatory setup gate. Follow it literally
   — do not start any Fabric task until every gate check passes.
2. If the current node does not answer the user's question, call
   `graph_get_linked` with that node's id to see its neighbors.
   Choose one and call `graph_get_node`.
3. You may only navigate to node ids returned by `graph_get_entry`,
   `graph_get_linked`, or `graph_search`. Never guess or hallucinate
   a node id.
4. Use `graph_search` only when no linked node looks relevant and a
   fresh entry point is needed.
5. When the answer is in hand, cite the node ids you sourced from
   (e.g. "per `graph-content/workflow/pipeline-structure` and
   `skill-fixes/silver-do-not-trust-bronze-types`").
6. To author or modify a knowledge node, use `graph_create_node` /
   `graph_update_node` / `graph_add_edge` rather than direct file
   edits. To remove graph knowledge, use `graph_delete_node` /
   `graph_remove_edge` only when explicitly asked.

## Graph tool surface

Read: `graph_get_entry`, `graph_get_node`, `graph_get_linked`,
`graph_search`, `graph_list_kinds`.
Write: `graph_create_node`, `graph_update_node`, `graph_delete_node`,
`graph_add_edge`, `graph_remove_edge`. All write operations
re-serialize the graph atomically.
