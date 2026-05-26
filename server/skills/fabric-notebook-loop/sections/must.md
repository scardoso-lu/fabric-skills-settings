---
name: fabric-notebook-loop-must
description: Non-negotiable rules for the fabric-notebook-loop closed-loop development cycle — cell markers, build/deploy/monitor commands, fetch-then-stop, never-commit-fetched-artifacts.
kind: content
links:
  - skills/fabric-notebook-loop
  - skills/fabric-notebook-loop/the-loop
---

# MUST

- Use `# %%` cell markers in local `.py` files
- Build notebooks with `fabric-cli notebook build`
- Deploy and run via `fabric-cli notebook deploy` — NOT `fab import` or `fab job run` (both require an interactive Windows console and fail in Git Bash / non-interactive environments)
- Monitor via `fabric-cli notebook deploy monitor` or by checking job instance status through the Fabric REST API
- After a successful run, `fabric-cli notebook deploy run` automatically fetches the notebook definition back from Fabric into `workspace/<topic>/<name>.Notebook/` (synced with Fabric UI)
- After fetch, report to orchestrator and stop — the human commits via the Fabric UI Git integration
- Never run `git add`, `git rm`, or `git commit` — all git commits are the human's responsibility via Fabric UI
- `fabric_notebooks/<topic>/<name>.Notebook/` is the build intermediate (gitignored) — never commit it
- Never pipe full driver logs into agent context — summarise to STATUS + error message only
- Use HighConcurrency pool for initial cold start (≈3 min on F64; F2/F4 can reach 8–12 min); subsequent runs within 20 min are fast on any capacity tier
- Default to Python kernel (`# FABRIC_KERNEL: python`) for any notebook that does not write Delta tables via Spark — it starts faster (≈30 s vs ≈3–8 min) and supports warehouse + lakehouse dependencies simultaneously
- Use `# FABRIC_LAKEHOUSE: <NAME>` and `# FABRIC_WAREHOUSE: <NAME>` sentinels to declare notebook dependencies — one sentinel per artifact, first lakehouse = default
- Ensure `.env` has a matching `FABRIC_LAKEHOUSE_<NAME>=<uuid>` entry for each sentinel
- PySpark notebooks: lakehouses only (no warehouse sentinel — Fabric rejects warehouse metadata in PySpark format)
- Python notebooks: lakehouses + up to one warehouse sentinel
