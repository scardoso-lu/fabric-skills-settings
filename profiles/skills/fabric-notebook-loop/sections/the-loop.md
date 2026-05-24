---
name: fabric-notebook-loop-the-loop
description: The author -> build -> deploy -> smoke -> fetch -> report cycle with the per-step commands, run-status interpretation, and cell-structure template.
kind: content
links:
  - skills/fabric-notebook-loop
  - skills/fabric-notebook-loop/diagnosing-opaque-failures
  - skills/fabric-notebook-loop/full-example
---

# The Loop

Deploy and smoke test are **separate steps**. The smoke test never deploys.

```bash
# 0. Confirm active workspace (every session, before any build or deploy)
python tool/workspace/switch.py list
# Stop. Ask: "Active workspace is '<displayName>'. Confirm to proceed?"
# Do not run build.py or deploy.py until the human confirms.
# To deploy to a different workspace instead, use transfer.py:
#   python tool/workspace/transfer.py --notebook <name> --to <displayName>

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
# Before reporting complete, run pre-commit validation:
# Windows:   tool\pre-commit-check.ps1
# Linux/Mac: bash tool/pre-commit-check.sh
# Report to orchestrator: fetch complete. Human commits via Fabric UI.
```

`FABRIC_WORKSPACE_ID` is read from `.env` automatically. The intermediate build in `fabric_notebooks/` is gitignored.

## Individual commands

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

If the failure message is just `System cancelled the Spark session due to statement execution failures`, follow [[skills/fabric-notebook-loop/diagnosing-opaque-failures]] before guessing at fixes.
