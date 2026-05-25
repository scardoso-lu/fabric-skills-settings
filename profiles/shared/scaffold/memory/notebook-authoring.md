# Notebook Authoring — Conventions and Gotchas

## Kernel selection

Default to **Python kernel** unless Spark is explicitly required.

Add `# FABRIC_KERNEL: python` as the **first line** of any source `.py` file that doesn't need Spark.

| Notebook type | Kernel |
|---|---|
| Delta Lake writes (`spark.write`) | PySpark |
| Large-scale Spark transformations | PySpark |
| dbt subprocess | Python |
| `notebookutils.data.connect_to_artifact()` SQL | Python |
| API calls, file download, CLI tools | Python |
| Great Expectations checks | Python |

**PySpark kernel cannot have a warehouse in its dependency metadata** — Fabric rejects it.
**Python kernel** supports both lakehouse and warehouse dependencies simultaneously.

Cold-start times:
- Python kernel: ≈30 seconds
- PySpark kernel: ≈3–8 minutes (F2/F4 capacity)

## Notebook dependency sentinels

Declare lakehouse and warehouse dependencies as sentinels near the top of the source `.py` file.

```python
# FABRIC_KERNEL: python         ← first line, if using Python kernel
# FABRIC_LAKEHOUSE: DATALAKE    ← first listed = default_lakehouse
# FABRIC_LAKEHOUSE: BRONZE      ← additional known_lakehouses
# FABRIC_WAREHOUSE: DATA_WAREHOUSE  ← Python kernel only; max one
```

Each sentinel name is resolved from `.env`:
- `FABRIC_LAKEHOUSE_DATALAKE=<uuid>`
- `FABRIC_WAREHOUSE_DATA_WAREHOUSE=<uuid>`

Name normalization: uppercase, spaces and hyphens → underscores.

Valid Fabric kernel/dependency combinations:
- PySpark: 0-N lakehouses, **no warehouse**
- Python: 0-N lakehouses, 0-1 warehouse

Notebooks without any sentinels fall back to legacy `FABRIC_LAKEHOUSE_ID` / `FABRIC_LAKEHOUSE_NAME`
/ `FABRIC_WAREHOUSE_ID` env vars (backward compatible).

## Parameters cell

Mark a cell as a pipeline parameters cell using `# %% [parameters]` in the source `.py` file.
`build.py` converts this to `# PARAMETERS CELL ********************` — the separator string
that Fabric recognises for runtime parameter injection from pipeline activities.

Do NOT use `"tags": ["parameters"]` in cell metadata — Fabric ignores it.
Do NOT use `# %% [parameters]` on more than one cell per notebook.

## dbt-fabric notebooks

Any notebook that runs dbt as a subprocess requires:

- `# FABRIC_KERNEL: python` as the **first line** (Python kernel only — IMDS fails in PySpark).
- `%pip install "dbt-fabric>=1.8,<2.0" pyodbc "protobuf>=3.12.0,<6"` in the install cell.
- Token from `notebookutils.credentials.getToken("https://database.windows.net/")`.
- profiles.yml written at runtime with `authentication: ActiveDirectoryAccessToken`,
  `access_token: <token>`, `access_token_expires_on: <unix_ts>`.
- ODBC driver detected via `pyodbc.drivers()` — prefer Driver 18, fall back to Driver 17.
- Warehouse TDS host read from `FABRIC_WAREHOUSE_HOST` in `.env` — never constructed from workspace_id.

`DefaultAzureCredential` / IMDS does **not** work in any Fabric Python kernel subprocess.

## Fabric Data Warehouse connection

Read `FABRIC_WAREHOUSE_HOST` from `.env` — never construct it from `FABRIC_WORKSPACE_ID`.

The DWH TDS host has the form `<random_prefix>.datawarehouse.fabric.microsoft.com`.
The prefix is assigned at warehouse creation and is only found in:
- Fabric UI → Data Warehouse → Settings → Connection strings → SQL connection string

In notebook Config cell:

```python
WAREHOUSE_HOST = os.environ.get("FABRIC_WAREHOUSE_HOST", "")
if not WAREHOUSE_HOST:
    raise RuntimeError("FABRIC_WAREHOUSE_HOST is not set in .env")
```

## Non-standard packages

Use `%pip install` in a dedicated install cell. Pin versions for packages with known conflicts
(e.g., `"protobuf>=3.12.0,<6"` when using dbt-fabric alongside mlflow-skinny).
