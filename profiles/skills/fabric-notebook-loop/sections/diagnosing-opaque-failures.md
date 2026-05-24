---
name: fabric-notebook-loop-diagnosing-opaque-failures
description: Three diagnostic paths for the generic "System cancelled the Spark session" smoke-test failure plus a catalogue of common silent causes.
kind: content
links:
  - skills/fabric-notebook-loop
  - skills/fabric-notebook-loop/the-loop
---

# Diagnosing Opaque Smoke-test Failures

`deploy.py monitor` reads `failureReason.message` from the Fabric job-instance API. For Spark notebook failures, that field returns a generic wrapper — **never** the cell-level exception or traceback:

```
-- Run FAILED: System cancelled the Spark session due to statement execution failures
```

When you see this message, do not guess at fixes. A full build + deploy + execute cycle is 3–8 min cold start on F2/F4; guessing wastes capacity. Pick one of these three diagnostic options:

1. **Fabric UI snapshot (authoritative).** Open the notebook in the workspace, click the failed job from the run history; the snapshot view shows the per-cell traceback.
2. **Instrument the source `.py` (fastest in the closed loop).** Wrap each `# %%` cell body in `try/except` that prints `traceback.format_exc()` before re-raising. Rebuild + redeploy + rerun; the cell-level error shows up under the job stdout. Remove the instrumentation once the bug is fixed.
3. **Bisect by cells.** Comment out the cells after the first heavy one, redeploy, rerun. Add cells back one at a time until the failure reappears.

Common silent causes of the generic message:
- `spark.sql("OPTIMIZE <table> ZORDER BY ...")` immediately after creating a managed table in the same session (lakehouse default catalog quirk)
- `spark.catalog.tableExists("<name>")` returning a stale result when the default catalog hasn't refreshed
- Missing schema/catalog qualifier when the lakehouse `defaultSchema` is `dbo` and SQL uses an unqualified name
- A `%pip install` cell on a PySpark kernel that takes too long and the system cancels the session
- Any uncaught Python exception in a cell whose stdout was never flushed

See `memory/skill-fixes/smoke-test-cell-errors.md` for the incident this rule comes from.
