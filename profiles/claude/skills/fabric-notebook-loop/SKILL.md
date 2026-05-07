---
name: fabric-notebook-loop
description: Develop Fabric notebooks using a local closed-loop cycle — author in .py locally, build to .Notebook format, deploy via fab import, execute, capture the run ID, monitor with nbmon, diagnose errors, fix, and redeploy. Use for iterative notebook development without portal interaction. Typically converges in 1–3 iterations. Cold-start time varies by capacity tier (≈3 min on F64, up to 8–12 min on F2/F4).
---

# fabric-notebook-loop

## MUST

- Use `# %%` cell markers in local `.py` files
- Build notebooks with `python3 bin/build_fabric_notebooks.py`
- Capture the run ID from `fab job run` before monitoring
- Monitor runs with `nbmon status` — never use `fab job run-status` for error diagnosis
- Never pipe full driver logs into agent context — use nbmon's 7-line summary
- Use HighConcurrency pool for initial cold start (≈3 min on F64; F2/F4 can reach 8–12 min); subsequent runs within 20 min are fast on any capacity tier

## PREFER

- One logical operation per cell for easier debugging
- Parameterized cells at top of notebook for environment configuration
- `try/except` on every cell that performs IO

## AVOID

- Relying on `tags` metadata — `fab import` strips tags
- Jupyter kernel for Delta Lake writes (Spark kernel required)
- Reading from HTTP/HTTPS URLs in Spark (stage to Files/ first via Data Factory)
- Using `df.show()` or `print()` in production cells

## The Loop

```bash
# 1. Author locally
# Edit workspace/my_notebook.py with # %% markers.

# 2. Build all local .py notebooks to Fabric .Notebook folders
python3 bin/build_fabric_notebooks.py

# 3. Deploy to Fabric
fab import fabric_notebooks/my_notebook.Notebook --workspace-id "$WORKSPACE_ID"

# 4. Run and capture the run ID
RUN_OUTPUT=$(fab job run --item-id "$NOTEBOOK_ITEM_ID" --workspace-id "$WORKSPACE_ID")
RUN_ID=$(printf '%s\n' "$RUN_OUTPUT" | sed -nE 's/.*(runId|Run ID|run_id)[" :_=]+([A-Za-z0-9-]+).*/\2/p' | head -1)
test -n "$RUN_ID" || { echo "Could not parse run ID from fab output:"; printf '%s\n' "$RUN_OUTPUT"; exit 1; }
echo "Run ID: $RUN_ID"

# 5. Monitor
nbmon status "$RUN_ID"

# 6. Fix and repeat
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

## nbmon Output Interpretation

```
RUN ID   : abc-123
STATUS   : Failed
DURATION : 4m 32s
CATEGORY : PySpark — AnalysisException
TRACEBACK: AnalysisException: Table not found: bronze.raw_orders
ADVISE   : Verify lakehouse_id and table name. Check that the table exists in the specified lakehouse.
CELL     : Cell 3 (line 12)
```

Act on `CATEGORY` + `TRACEBACK` + `ADVISE`. Do not ask for more context — nbmon gives you enough.

## Full Example: CSV to Bronze

Create a local notebook source at `workspace/orders_bronze.py`:

```python
# %% [parameters]
import os
from pyspark.sql import functions as F

source_path = os.environ.get("SRC_ORDERS_PATH", "data/sandbox/orders.csv")
source_system = "ORDERS"
batch_id = os.environ.get("BATCH_ID", "manual-dev")

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
python3 bin/build_fabric_notebooks.py
fab import fabric_notebooks/orders_bronze.Notebook --workspace-id "$WORKSPACE_ID"
RUN_OUTPUT=$(fab job run --item-id "$NOTEBOOK_ITEM_ID" --workspace-id "$WORKSPACE_ID")
RUN_ID=$(printf '%s\n' "$RUN_OUTPUT" | sed -nE 's/.*(runId|Run ID|run_id)[" :_=]+([A-Za-z0-9-]+).*/\2/p' | head -1)
test -n "$RUN_ID" || { echo "Could not parse run ID from fab output:"; printf '%s\n' "$RUN_OUTPUT"; exit 1; }
nbmon status "$RUN_ID"
```

If `nbmon` reports failure, fix only the failing cell, rebuild, redeploy, rerun, and monitor again.
