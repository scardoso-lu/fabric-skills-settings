---
name: fabric-notebook-loop
description: Develop Fabric notebooks using a local closed-loop cycle — author in .py locally, build to .Notebook format, deploy via REST API, execute, monitor, diagnose errors, fix, and redeploy. Use for iterative notebook development without portal interaction. Typically converges in 1–3 iterations. Cold-start time varies by capacity tier (≈3 min on F64, up to 8–12 min on F2/F4).
links:
  - skills/fabric-notebook-loop/must
  - skills/fabric-notebook-loop/prefer-avoid
  - skills/fabric-notebook-loop/the-loop
  - skills/fabric-notebook-loop/diagnosing-opaque-failures
  - skills/fabric-notebook-loop/mlflow-platform-limits
  - skills/fabric-notebook-loop/full-example
---

# fabric-notebook-loop

Iterative Fabric notebook development without portal interaction. The skill is split into focused sections — traverse the linked nodes to pick up only what you need:

- [[skills/fabric-notebook-loop/must]] — non-negotiable rules (cell markers, build/deploy/monitor, fetch-then-stop, kernel + sentinel rules)
- [[skills/fabric-notebook-loop/prefer-avoid]] — recommended preferences and the explicit anti-patterns
- [[skills/fabric-notebook-loop/the-loop]] — the author → build → deploy → smoke → fetch cycle, individual commands, cell structure, run-status interpretation
- [[skills/fabric-notebook-loop/diagnosing-opaque-failures]] — three diagnostic paths for `System cancelled the Spark session` and the catalogue of common silent causes
- [[skills/fabric-notebook-loop/mlflow-platform-limits]] — Fabric MLflow experiment-name validation and the SPN `MwcTokenValidationException` that blocks closed-loop MLflow
- [[skills/fabric-notebook-loop/full-example]] — end-to-end CSV-to-Bronze example

For diagnosing opaque smoke-test failures, also see `memory/skill-fixes/smoke-test-cell-errors.md`. For MLflow specifics: `memory/skill-fixes/fabric-mlflow-spn-blocked.md`, `memory/skill-fixes/fabric-mlflow-experiment-name.md`.
