---
name: smoke-test-diagnostics
description: How to interpret opaque Spark cancellation messages from tool/notebook/deploy.py monitor. Required reading before guessing at smoke-test failures.
kind: content
links:
  - skills/fabric-notebook-loop
---

# Smoke-test diagnostics

`tool/notebook/deploy.py monitor` reports only the generic Spark failure message; it does **not** surface cell-level tracebacks. When a smoke test prints `System cancelled the Spark session due to statement execution failures`, do not guess at fixes.

Choose one of these diagnostic paths instead:

1. **Open the failed run in the Fabric UI** for the cell-level traceback (fastest, no code change).
2. **Instrument the source `.py`** with `try/except` + `traceback.format_exc()` around the suspect cell, re-deploy, re-run.
3. **Bisect by commenting cells** — comment out the back half, deploy, smoke-test; if it passes the bug is in the commented half; binary-search to the cell.

Common silent causes:

- Missing `%pip install` for a new import — Spark error is generic but the kernel never reached the cell that imports.
- Bronze schema drift — a column the silver MERGE expects is gone; see `memory/skill-fixes/silver-do-not-trust-bronze-types.md`.
- MLflow run inside an SPN-triggered notebook — fails with `MwcTokenValidationException`; see `memory/skill-fixes/fabric-mlflow-spn-blocked.md`.
- MLflow experiment name with `/` prefix (Databricks style) — Fabric rejects; see `memory/skill-fixes/fabric-mlflow-experiment-name.md`.

See `memory/skill-fixes/smoke-test-cell-errors.md` for the incident this rule comes from.
