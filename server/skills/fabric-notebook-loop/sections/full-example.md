---
name: fabric-notebook-loop-full-example
description: End-to-end CSV-to-Bronze example showing the cell markers, ingest timestamps, lineage columns, and the build/deploy/smoke-test invocation.
kind: content
links:
  - skills/fabric-notebook-loop
  - skills/fabric-notebook-loop/the-loop
---

# Full Example: CSV to Bronze

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
fabric-cli notebook build
fabric-cli notebook deploy deploy orders_bronze "$FABRIC_WORKSPACE_ID"
fabric-cli notebook smoke-test --notebook orders_bronze   # cross-platform
```

If the run fails, check the STATUS output, fix only the failing cell, then report to the orchestrator and await human approval before the next run.
