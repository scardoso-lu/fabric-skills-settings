---
name: fabric-notebook-loop
description: Develop Fabric notebooks using a local closed-loop cycle — author in .py locally, build to .Notebook format, deploy via fab import, execute, monitor with nbmon, diagnose errors, fix, and redeploy. Use for iterative notebook development without portal interaction. Typically converges in 1–3 iterations.
---

# fabric-notebook-loop

## MUST

- Use `# %%` cell markers in local `.py` files
- Monitor runs with `nbmon status` — never use `fab job run-status` for error diagnosis
- Never pipe full driver logs into agent context — use nbmon's 7-line summary
- Use HighConcurrency pool for initial cold start (~3 min); subsequent runs within 20 min are fast

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
# Edit src/notebooks/my_notebook.py with # %% markers

# 2. Build to .Notebook format
python bin/build-notebooks.py src/notebooks/my_notebook.py

# 3. Deploy to Fabric
fab import fabric_notebooks/my_notebook.Notebook --workspace-id $WORKSPACE_ID

# 4. Run
fab job run --item-id $NOTEBOOK_ITEM_ID --workspace-id $WORKSPACE_ID

# 5. Monitor
nbmon status $RUN_ID

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
