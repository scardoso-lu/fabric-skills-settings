---
name: fabric-notebook-loop
description: Develop Fabric notebooks using a local closed-loop cycle — author in .py locally, build to .Notebook format, deploy via REST API, execute, monitor, diagnose errors, fix, and redeploy. Use for iterative notebook development without portal interaction. Typically converges in 1–3 iterations. Cold-start time varies by capacity tier (≈3 min on F64, up to 8–12 min on F2/F4).
---

# fabric-notebook-loop

## MUST

- Use `# %%` cell markers in local `.py` files
- Build notebooks with `python bin/notebook/build.py`
- Deploy and run via `bin/notebook/deploy.py` — NOT `fab import` or `fab job run` (both require an interactive Windows console and fail in Git Bash / sandboxed environments)
- Monitor via `bin/notebook/deploy.py monitor` or by checking job instance status through the Fabric REST API
- Never pipe full driver logs into agent context — summarise to STATUS + error message only
- Use HighConcurrency pool for initial cold start (≈3 min on F64; F2/F4 can reach 8–12 min); subsequent runs within 20 min are fast on any capacity tier

## PREFER

- One logical operation per cell for easier debugging
- Parameterized cells at top of notebook for environment configuration
- `try/except` on every cell that performs IO

## AVOID

- Using `fab import` — requires an interactive Windows console; use `bin/notebook/deploy.py deploy` instead
- Using `fab job run` — same console issue; use `bin/notebook/deploy.py run` instead
- Jupyter kernel for Delta Lake writes (Spark kernel required)
- Reading from HTTP/HTTPS URLs in Spark (stage to Files/ first via Data Factory)
- Using `df.show()` or `print()` in production cells

## The Loop

```bash
# 1. Author locally
# Edit workspace/my_notebook.py with # %% markers.

# 2. Build, deploy, run, and monitor in one command.
bin/notebook/smoke-test.sh --notebook my_notebook

# 3. Fix and repeat.
```

The smoke test script reads `FABRIC_WORKSPACE_ID` from `.env` automatically.

### Step by step (if you need finer control)

```bash
# Build
python bin/notebook/build.py

# Deploy only
python bin/notebook/deploy.py deploy my_notebook "$FABRIC_WORKSPACE_ID"

# Deploy + run + monitor
python bin/notebook/deploy.py run my_notebook "$FABRIC_WORKSPACE_ID"

# Monitor an existing job instance
python bin/notebook/deploy.py monitor "$FABRIC_WORKSPACE_ID" <item_id> <job_instance_id>
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

Act on `STATUS` + `failureReason`. If the notebook fails, fix only the failing cell, rebuild, redeploy, rerun.

## Full Example: CSV to Bronze

Create a local notebook source at `workspace/orders_bronze.py`:

```python
# %% [parameters]
from pyspark.sql import functions as F

SOURCE_PATH = "/lakehouse/default/Files/orders.csv"
source_path = SOURCE_PATH or "/lakehouse/default/Files/orders.csv"
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

Run the complete loop:

```bash
bin/notebook/smoke-test.sh --notebook orders_bronze
```

If the run fails, check the STATUS output, fix only the failing cell, rebuild, redeploy, rerun.
