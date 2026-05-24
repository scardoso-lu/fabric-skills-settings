---
name: agents-index
description: Subagent catalogue with routing guidance. Use to pick which agent should own the next step.
kind: content
links:
  - agents/orchestrator
  - agents/developer
  - agents/tester
  - agents/operator
---

# Agents index

Use project subagents via `.claude/agents/` (Claude) or `.codex/agents/` (Codex):

- `orchestrator` scopes the request and routes it to developer/tester/operator. Owns hand-off back to the human. See [[agents/orchestrator]].
- `developer` implements notebooks, transforms, models, and DQ scaffolds. See [[agents/developer]].
- `tester` writes and runs independent DQ validation; owns the final PASS/FAIL gate before release. See [[agents/tester]].
- `operator` reviews security, PII handling, and access; gates anything touching credentials, sensitive fields, or external sharing. See [[agents/operator]].

Routing rules: never hand off developer → tester or developer → operator directly. All routing goes through the orchestrator.
