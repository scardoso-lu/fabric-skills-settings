---
name: fabric-notebook-loop
description: Develop Fabric notebooks using a local closed-loop cycle — author in .py locally, build to .Notebook format, deploy via REST API, execute, monitor, diagnose errors, fix, and redeploy. Use for iterative notebook development without portal interaction. Typically converges in 1–3 iterations. Cold-start time varies by capacity tier (≈3 min on F64, up to 8–12 min on F2/F4).
---

# fabric-notebook-loop

## MUST

- Use `# %%` cell markers in local `.py` files
- Build notebooks with `python tool/notebook/build.py`
- Deploy and run via `tool/notebook/deploy.py` — NOT `fab import` or `fab job run` (both require an interactive Windows console and fail in Git Bash / sandboxed environments)
- Monitor via `tool/notebook/deploy.py monitor` or by checking job instance status through the Fabric REST API
- After a successful run, `deploy.py run` automatically fetches the notebook definition back from Fabric into `workspace/<topic>/<name>.Notebook/` (synced with Fabric UI)
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

## PREFER

- One logical operation per cell for easier debugging
- Parameterized cells at top of notebook for environment configuration
- `try/except` on every cell that performs IO

## AVOID

- Using `fab import` — requires an interactive Windows console; use `tool/notebook/deploy.py deploy` instead
- Using `fab job run` — same console issue; use `tool/notebook/deploy.py run` instead
- Using PySpark kernel for dbt, API calls, or CLI tools — Python kernel is always faster and supports more dependency types
- Adding warehouse dependencies to PySpark notebooks — Fabric returns "Unsupported content"
- Using `DefaultAzureCredential` / `authentication: auto` for dbt-fabric subprocesses in Python kernel — IMDS is unreachable; use `notebookutils.credentials.getToken("https://database.windows.net/")` instead
- Hard-coding the DWH TDS hostname — always read `FABRIC_WAREHOUSE_HOST` from `.env`; the prefix is NOT derived from workspace_id
- Reading from HTTP/HTTPS URLs in Spark (stage to Files/ first via Data Factory)
- Using `df.show()` or `print()` in production cells

## The Loop

Deploy and smoke test are **separate steps**. The smoke test never deploys.

```bash
# 1. Author locally
# Edit workspace/<topic>/my_notebook.py with # %% markers.

# 2. Build and deploy (run whenever the source changes).
python tool/notebook/build.py
python tool/notebook/deploy.py deploy my_notebook "$FABRIC_WORKSPACE_ID"

# 3. Smoke test — triggers a job execution on the already-deployed notebook and monitors it.
#    Never builds or deploys. Always runs against whatever is currently in Fabric.
#    Windows:   tool\notebook\smoke-test.ps1 -Notebook my_notebook
#    Linux/Mac: tool/notebook/smoke-test.sh --notebook my_notebook

# 4. Report STATUS to orchestrator and STOP.
#    - STATUS: Completed → PASS. Proceed to step 5.
#    - STATUS: Failed    → report FAIL + failureReason. Do NOT re-run. Await human approval.
#    - STATUS missing or unclear → ask human for validation. Do NOT re-run.
#    Never re-run the smoke test autonomously — each run consumes Fabric capacity.

# 5. After PASS — fetch the Fabric bundle and report. Do NOT commit.
#    The human commits via the Fabric UI Git integration.
python tool/notebook/deploy.py fetch my_notebook "$FABRIC_WORKSPACE_ID"
# Report to orchestrator: fetch complete. Human commits via Fabric UI.
```

`FABRIC_WORKSPACE_ID` is read from `.env` automatically. The intermediate build in `fabric_notebooks/` is gitignored.

### Individual commands

```bash
# Build: workspace/<topic>/name.py → fabric_notebooks/<topic>/name.Notebook/
python tool/notebook/build.py

# Deploy built artifact to Fabric (no run)
python tool/notebook/deploy.py deploy my_notebook "$FABRIC_WORKSPACE_ID"

# Execute already-deployed notebook (trigger + monitor, no build/deploy) — used by smoke-test.sh
python tool/notebook/deploy.py exec my_notebook "$FABRIC_WORKSPACE_ID"

# Fetch current Fabric definition → workspace/<topic>/<name>.Notebook/ (standalone sync)
python tool/notebook/deploy.py fetch my_notebook "$FABRIC_WORKSPACE_ID"

# Monitor an existing job instance (debugging)
python tool/notebook/deploy.py monitor "$FABRIC_WORKSPACE_ID" <item_id> <job_instance_id>

# One-shot full cycle (deploy + exec + fetch) — for initial bring-up only, not for repeated testing
python tool/notebook/deploy.py run my_notebook "$FABRIC_WORKSPACE_ID"
```

## Cell Structure

```python
# %% [parameters]
lakehouse_id = ""  # set at runtime via Fabric UI or pipeline parameter

# %% [markdown]
# ## Step 1: Load from Bronze

# %%
from pyspark.sql import functions as F
import os

bronze_path = f"abfss://bronze@onelake.dfs.fabric.microsoft.com/{lakehouse_id}/Tables/raw_orders"

try:
    df = spark.read.format("delta").load(bronze_path)
    print(f"✓ Loaded {df.count():,} rows from Bronze")
except Exception as e:
    print(f"✗ Load failed: {e}")
    raise
```

## Run Status Interpretation

```
STATUS: InProgress   ← still running, keep polling
STATUS: Completed    ← success
STATUS: Failed       ← check failureReason in the job instance response
STATUS: Cancelled    ← manually stopped
```

Act on `STATUS` + `failureReason`:
- `Completed` → report PASS to orchestrator.
- `Failed` → report FAIL + `failureReason` to orchestrator and **STOP**. Fix the failing cell locally, then await human approval before the next run.
- No clear STATUS in output → ask human for validation. Do **not** re-run.

Never trigger a second smoke-test run autonomously — each run consumes Fabric capacity.

## Full Example: CSV to Bronze

Create a local notebook source at `workspace/<topic>/orders_bronze.py`:

```python
# %% [parameters]
from pyspark.sql import functions as F

SOURCE_PATH = "Files/data/sandbox/orders.csv"
source_path = SOURCE_PATH or "Files/data/sandbox/orders.csv"
source_system = "ORDERS"
batch_id = "manual-dev"

# %%
try:
    raw_df = spark.read.option("header", True).csv(source_path)
    bronze_df = (
        raw_df
        .withColumn("_ingest_timestamp", F.current_timestamp())
        .withColumn("_source_system", F.lit(source_system))
        .withColumn("_batch_id", F.lit(batch_id))
    )
except Exception as exc:
    print(f"Load failed for {source_system}: {exc}")
    raise

# %%
try:
    (
        bronze_df.write
        .format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
        .saveAsTable("bronze_orders")
    )
    print(f"Wrote {bronze_df.count()} rows to bronze_orders")
except Exception as exc:
    print(f"Bronze write failed for {source_system}: {exc}")
    raise
```

Build, deploy, then smoke test:

```bash
python tool/notebook/build.py
python tool/notebook/deploy.py deploy orders_bronze "$FABRIC_WORKSPACE_ID"
tool\notebook\smoke-test.ps1 -Notebook orders_bronze     # Windows
tool/notebook/smoke-test.sh --notebook orders_bronze      # Linux/Mac
```

If the run fails, check the STATUS output, fix only the failing cell, then report to the orchestrator and await human approval before the next run.
