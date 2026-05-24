---
name: fabric-notebook-loop-prefer-avoid
description: Recommended cell-structure preferences and the explicit list of anti-patterns that break the closed-loop cycle.
kind: content
links:
  - skills/fabric-notebook-loop
  - skills/fabric-notebook-loop/diagnosing-opaque-failures
  - skills/fabric-notebook-loop/mlflow-platform-limits
---

# PREFER

- One logical operation per cell for easier debugging
- Parameterized cells at top of notebook for environment configuration
- `try/except` on every cell that performs IO

# AVOID

- Using `fab import` — requires an interactive Windows console; use `tool/notebook/deploy.py deploy` instead
- Using `fab job run` — same console issue; use `tool/notebook/deploy.py run` instead
- Using PySpark kernel for dbt, API calls, or CLI tools — Python kernel is always faster and supports more dependency types
- Adding warehouse dependencies to PySpark notebooks — Fabric returns "Unsupported content"
- Using `DefaultAzureCredential` / `authentication: auto` for dbt-fabric subprocesses in Python kernel — IMDS is unreachable; use `notebookutils.credentials.getToken("https://database.windows.net/")` instead
- Hard-coding the DWH TDS hostname — always read `FABRIC_WAREHOUSE_HOST` from `.env`; the prefix is NOT derived from workspace_id
- Reading from HTTP/HTTPS URLs in Spark (stage to Files/ first via Data Factory)
- Using `df.show()` or `print()` in production cells
- Guessing at the failing cell when the smoke test reports `System cancelled the Spark session due to statement execution failures` — `deploy.py monitor` does NOT return the cell-level traceback; see [[skills/fabric-notebook-loop/diagnosing-opaque-failures]]
- Authoring ML notebooks that call `mlflow.set_experiment`, `mlflow.start_run`, or `mlflow.log_*` when the notebook will be smoke-tested via the closed loop — SPN-triggered runs fail with `MwcTokenValidationException`; persist to `Files/models/<topic>/*.pkl` via `joblib` instead. See [[skills/fabric-notebook-loop/mlflow-platform-limits]].
