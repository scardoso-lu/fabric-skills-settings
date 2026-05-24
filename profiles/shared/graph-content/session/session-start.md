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
  - graph-content/indexes/agents-index
  - graph-content/integrations/rtk
---

# Session start — traversal order

After the setup gate ([[graph-content/entry]]) passes, traverse the graph in this order before addressing the user's request:

1. Read `memory/MEMORY.md` and each global file it lists.
2. Read all files in `memory/skill-fixes/` (skill-fix nodes); they take precedence over `SKILL.md` defaults where they conflict.
3. If the request concerns a specific topic, read `memory/<topic>/project.md` (topic nodes).
4. Mention relevant context briefly, then address the request.

Use [[graph-content/session/operating-rules]] for non-negotiable per-session rules.

From here, the next traversal step depends on the request:

- Authoring or modifying notebooks → [[graph-content/workflow/notebook-workflow]]
- Where things live on disk → [[graph-content/layout/directory-layout]]
- Which tool to invoke for what → [[graph-content/layout/tool-layout]]
- Picking the right skill → [[graph-content/indexes/skills-index]]
- Picking the right subagent → [[graph-content/indexes/agents-index]]
- Shell tooling expectations → [[graph-content/integrations/rtk]]
