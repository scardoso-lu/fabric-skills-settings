---
name: notebook-workflow
description: End-to-end notebook flow author -> build -> deploy -> smoke -> fetch. Use before any notebook modification.
kind: content
links:
  - graph-content/workflow/pipeline-structure
  - graph-content/workflow/workspace-management
  - graph-content/diagnostics/smoke-test-diagnostics
  - skills/fabric-notebook-loop
  - rules/notebook-authoring
---

# Notebook workflow

```text
author -> build -> deploy REST -> smoke test -> fetch -> human commits via Fabric UI
.py       fabric_notebooks/  Fabric      exec+monitor  workspace/<topic>/<name>.Notebook/
```

Deploy and smoke test are separate steps:

- Deploy on source change: `fabric-cli notebook deploy deploy <name> <workspace_id>`.
- Smoke test an existing deployed notebook: `fabric-cli notebook smoke-test --notebook <name>` (cross-platform).
- Fetch after a passing run: `fabric-cli notebook deploy fetch <name> <workspace_id>`.

The smoke test never deploys. It triggers a job on whatever is already in Fabric and reports status. After fetch, stop and report to the orchestrator. Do not run `git add`, `git rm`, or `git commit` for fetched Fabric notebook artifacts unless the human explicitly asks for a repository commit.

When smoke tests fail with a generic Spark cancellation message, see [[graph-content/diagnostics/smoke-test-diagnostics]] before guessing at fixes.
