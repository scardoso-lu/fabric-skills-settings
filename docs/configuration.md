# Project Configuration Guide

How to configure a Fabric project repository after running `bin/install-fabric-agent`.

---

## 1. Environment Variables (`.env`)

Copy `.env.example` to `.env` at the project root and fill in each variable. Agents never read `.env` directly — they check for its presence and specific key names only.

### Required

| Variable | Where to find it | Example |
|---|---|---|
| `FABRIC_WORKSPACE_ID` | Fabric portal → Workspace settings → Details → ID | `3f1a2b4c-...` |

### Lakehouse IDs

One entry per lakehouse the project uses. The suffix after `FABRIC_LAKEHOUSE_` must match the **display name** of the lakehouse, uppercased, with spaces and hyphens converted to underscores.

```
FABRIC_LAKEHOUSE_DATALAKE=<uuid>      # lakehouse named "datalake" or "DataLake"
FABRIC_LAKEHOUSE_BRONZE=<uuid>        # lakehouse named "bronze" or "Bronze"
FABRIC_LAKEHOUSE_SILVER=<uuid>        # lakehouse named "silver"
FABRIC_LAKEHOUSE_GOLD=<uuid>          # lakehouse named "gold"
```

Where to find each UUID: Fabric portal → select the Lakehouse → URL contains `/lakehouses/<uuid>`.

### Warehouse IDs and Host

```
FABRIC_WAREHOUSE_DATA_WAREHOUSE=<uuid>     # warehouse named "Data Warehouse"
FABRIC_WAREHOUSE_HOST=<prefix>.datawarehouse.fabric.microsoft.com
```

The `FABRIC_WAREHOUSE_HOST` value **cannot be derived** from the workspace ID or warehouse ID. Retrieve it from: Fabric portal → Data Warehouse → Settings → Connection strings → SQL connection string. Copy the server portion only (everything before the first comma or after `Server=`).

### Legacy Variables (backward compat — prefer the named form above)

```
FABRIC_LAKEHOUSE_ID=<uuid>     # single-lakehouse projects only
FABRIC_LAKEHOUSE_NAME=<name>   # single-lakehouse projects only
FABRIC_WAREHOUSE_ID=<uuid>     # single-warehouse projects only
```

---

## 2. Notebook Sentinel Declarations

Every notebook source file (`workspace/<topic>/<name>.py`) must declare its kernel and dependencies in sentinel comment lines **before the first `# %%` cell marker**. `build.py` reads these to construct the correct Fabric notebook metadata.

### Kernel selection

```python
# FABRIC_KERNEL: python
```

Omit this line (or write any other value) to get **PySpark** (the default). Add it to get the **Python** kernel.

**When to choose Python:**
- Download notebooks (call an API, save files — no Spark needed)
- dbt-fabric notebooks
- Any notebook where a ~30 s cold start matters more than native Delta Lake writes

**When to keep PySpark:**
- Bronze / Silver ingestion writing Delta tables
- Silver MERGE operations
- Gold aggregations on large Delta tables
- Any notebook using `mssparkutils` for Delta-native operations

### Lakehouse declarations

```python
# FABRIC_LAKEHOUSE: bronze
# FABRIC_LAKEHOUSE: silver
```

Each line attaches one lakehouse to the notebook. The name after the colon must match the corresponding `FABRIC_LAKEHOUSE_<NAME>` environment variable (case-insensitive; the build script normalises it). Omit for notebooks that use no lakehouse (e.g., a download notebook that only writes files).

For PySpark notebooks with no lakehouse declarations, `build.py` emits no default lakehouse — Spark still starts but has no mounted lakehouse. Attach at least one lakehouse if the notebook reads or writes Delta tables.

### Warehouse declarations

```python
# FABRIC_WAREHOUSE: data_warehouse
```

Valid only in **Python** kernel notebooks. A PySpark notebook with a warehouse sentinel will raise an error at build time. Attach at most one warehouse per notebook.

### Full example header

```python
# Fabric notebook source

# FABRIC_KERNEL: python
# FABRIC_LAKEHOUSE: bronze
# FABRIC_WAREHOUSE: data_warehouse

# %% [markdown]
# ## My notebook title
```

---

## 3. Connecting to Fabric Data Warehouse (dbt-fabric)

The Fabric Python kernel runs in a container that **cannot reach the Azure IMDS endpoint**, so `DefaultAzureCredential` and `ManagedIdentityCredential` always fail. The only working auth pattern is:

```python
import notebookutils
token = notebookutils.credentials.getToken("https://database.windows.net/")
```

Pass the result to dbt-fabric using the `access_token` / `access_token_expires_on` profile fields:

```python
profile = {
    "type": "fabric",
    "server": os.environ["FABRIC_WAREHOUSE_HOST"],
    "database": "<warehouse_name>",
    "authentication": "token",
    "access_token": token,
    "access_token_expires_on": "",   # dbt-fabric reads the live token; expiry is informational
}
```

Do **not** hard-code the warehouse host. Always read it from `FABRIC_WAREHOUSE_HOST`.

---

## 4. Pipeline Parameters (`pipeline_params.json`)

Each topic can supply default pipeline parameter values in:

```
workspace/<topic>/pipeline_params.json
```

Schema:

```json
{
  "parameters": {
    "HOST": "db.example.com",
    "SCHEMA": "dbo",
    "BATCH_SIZE": "500"
  }
}
```

All values must be strings. `manage.py` reads this file automatically when creating or testing a pipeline. CLI `--params` overrides take precedence:

```bash
python tool/pipeline/manage.py create --workspace <ws_id> --topic orders --params HOST=override.host
```

The merge order is: file values → CLI values (CLI wins).

Parameters are embedded as concrete values in each TridentNotebook activity's `typeProperties.parameters`. Do not use `@pipeline().parameters.X` — that syntax does not work for TridentNotebook activities and fails silently.

Inside a notebook, read injected parameters from the parameters cell (the cell containing `# PARAMETERS CELL ********************`):

```python
# PARAMETERS CELL ********************
HOST = ""       # injected by pipeline at runtime
SCHEMA = "dbo"  # default used during local/smoke-test runs
```

---

## 5. Notebook Kernel Cold Starts

| Kernel | Typical cold start | Notes |
|---|---|---|
| PySpark | 3–8 min (F2/F4), ~3 min F64 | Required for native Delta Lake writes |
| Python | ~30 s | Use for download, dbt-fabric, and light transforms |

Choose Python where possible to reduce overall pipeline runtime. Smoke tests block until the run completes, so kernel selection directly affects iteration speed.

---

## 6. Build → Deploy Reference

```bash
# 1. Validate staging paths
python tool/validate/pipeline-lineage.py

# 2. Build all notebooks
python tool/notebook/build.py

# 3. Deploy a single notebook
python tool/notebook/deploy.py deploy <name> <workspace_id>

# 4. Smoke test (triggers existing notebook — does not deploy)
# Windows:
powershell -ExecutionPolicy Bypass -File tool/notebook/smoke-test.ps1 -Notebook <name>
# Linux/Mac:
bash tool/notebook/smoke-test.sh --notebook <name>

# 5. Fetch after a passing run
python tool/notebook/deploy.py fetch <name> <workspace_id>
```

After fetch, stop and report to the orchestrator. The human commits via Fabric UI Git integration.

---

## 7. Pipeline Management Reference

```bash
# Create or update the pipeline for a topic
python tool/pipeline/manage.py create --workspace <ws_id> --topic <topic>

# Run the pipeline
python tool/pipeline/manage.py run --workspace <ws_id> --pipeline pipeline_<topic>

# Check run status
python tool/pipeline/manage.py status --workspace <ws_id> --pipeline pipeline_<topic>

# List pipelines
python tool/pipeline/manage.py list --workspace <ws_id>

# Test pipeline locally (creates, runs once, reports)
python tool/pipeline/manage.py test --workspace <ws_id> --topic <topic>
```

---

## 8. Source Package Validation (maintainers only)

Run from the `fabric-skills-settings` source package — not from an installed target repo:

```bash
uv run bin/validate-install-package.py
uv run bin/validate-agent-guidance.py
uv run --group dev pytest
```

To check alignment of an installed target:

```bash
python bin/install-fabric-agent --profile all --target /path/to/project-repo --check
```
