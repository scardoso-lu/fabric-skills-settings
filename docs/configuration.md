# Project Configuration Guide

This guide explains what a target Fabric project needs after `bin/install-fabric-agent` has installed the Codex or Claude profile.

Think of configuration in three layers:

1. **Access**: the workspace and service principal used by local tools.
2. **Fabric items**: lakehouses, warehouses, and endpoints notebooks attach to.
3. **Runtime behavior**: notebook kernels, pipeline parameters, deployment, and validation.

## First Run

From the target repository root, run the installed setup script:

```powershell
.\tool\setup\setup.ps1
```

```bash
bash tool/setup/setup.sh
```

Setup checks local tools, installs `ms-fabric-cli` when needed, initializes RTK when possible, asks for Fabric service-principal settings, and verifies that the Fabric API is reachable.

| Value | Stored where | Why |
|---|---|---|
| `FABRIC_WORKSPACE_ID` | `.env` | Selects the Fabric workspace. |
| `FABRIC_TENANT_ID` | `.env` | Identifies the Azure tenant. |
| `FABRIC_CLIENT_ID` | `.env` | Identifies the service principal. |
| `FABRIC_CLIENT_SECRET` | OS user environment | Authenticates the service principal without writing secrets to `.env`. |

Agents should not read `.env` secrets directly. The installed helper scripts load `.env` inside their own process when they need configuration.

## The `.env` Contract

The installer creates `.env.example`. Setup creates or updates `.env`. Start with workspace and service-principal values, then add item selectors only when notebooks need them.

```dotenv
FABRIC_WORKSPACE_ID=<workspace-uuid>
FABRIC_TENANT_ID=<tenant-uuid>
FABRIC_CLIENT_ID=<app-client-uuid>
```

`FABRIC_CLIENT_SECRET` is intentionally not shown here because it belongs in the OS user environment, not in the repository.

### Lakehouses

Notebook lakehouse sentinels map to `.env` keys.

```python
# FABRIC_LAKEHOUSE: bronze
```

```dotenv
FABRIC_LAKEHOUSE_BRONZE=<lakehouse-uuid>
```

The suffix after `FABRIC_LAKEHOUSE_` is the sentinel name uppercased, with spaces and hyphens converted to underscores. For example, `# FABRIC_LAKEHOUSE: Data Lake` maps to `FABRIC_LAKEHOUSE_DATA_LAKE`.

Find the lakehouse UUID in the Fabric portal URL for the lakehouse: `/lakehouses/<uuid>`.

### Warehouses

Warehouse sentinels follow the same pattern:

```python
# FABRIC_WAREHOUSE: data_warehouse
```

```dotenv
FABRIC_WAREHOUSE_DATA_WAREHOUSE=<warehouse-uuid>
FABRIC_WAREHOUSE_HOST=<prefix>.datawarehouse.fabric.microsoft.com
```

`FABRIC_WAREHOUSE_HOST` cannot be derived from the workspace or warehouse ID. Copy the server portion from Fabric portal -> Data Warehouse -> Settings -> Connection strings -> SQL connection string.

### Legacy Fallbacks

These still work for simple notebooks without sentinels, but new projects should prefer named sentinels:

```dotenv
FABRIC_LAKEHOUSE_ID=<lakehouse-uuid>
FABRIC_LAKEHOUSE_NAME=<display-name>
FABRIC_WAREHOUSE_ID=<warehouse-uuid>
```

## Notebook Metadata

Notebook source files live under:

```text
workspace/<topic>/<name>.py
```

`tool/notebook/build.py` reads simple sentinel comments near the top of each source file and turns them into Fabric notebook metadata.

| Need | Sentinel | Notes |
|---|---|---|
| Python kernel | `# FABRIC_KERNEL: python` | Omit for default PySpark. |
| Attach lakehouse | `# FABRIC_LAKEHOUSE: bronze` | First lakehouse becomes the default. |
| Attach warehouse | `# FABRIC_WAREHOUSE: data_warehouse` | Valid for Python kernel notebooks. |
| Parameters cell | `# %% [parameters]` | Used by Fabric pipeline parameter injection. |

Example:

```python
# FABRIC_KERNEL: python
# FABRIC_LAKEHOUSE: bronze
# FABRIC_WAREHOUSE: data_warehouse

# %% [parameters]
SCHEMA = "dbo"

# %% [markdown]
# ## Load reference data
```

Use Python kernel for download notebooks, dbt-fabric notebooks, API calls, and light transforms. Keep PySpark for Bronze/Silver/Gold notebooks that write Delta tables or need Spark-native lakehouse operations.

## Warehouse Authentication

Fabric Python notebooks cannot rely on Azure IMDS, so `DefaultAzureCredential` and `ManagedIdentityCredential` are the wrong default inside Fabric notebooks. Use Fabric notebook credentials:

```python
import notebookutils

token = notebookutils.credentials.getToken("https://database.windows.net/")
```

Pass the token to dbt-fabric:

```python
profile = {
    "type": "fabric",
    "server": os.environ["FABRIC_WAREHOUSE_HOST"],
    "database": "<warehouse_name>",
    "authentication": "token",
    "access_token": token,
    "access_token_expires_on": "",
}
```

Keep `FABRIC_WAREHOUSE_HOST` in configuration. Do not hard-code it in notebook source.

## Pipeline Parameters

A topic can define pipeline defaults in:

```text
workspace/<topic>/pipeline_params.json
```

```json
{
  "parameters": {
    "HOST": "db.example.com",
    "SCHEMA": "dbo",
    "BATCH_SIZE": "500"
  }
}
```

All values must be strings. CLI overrides win over file defaults:

```bash
python tool/pipeline/manage.py create --topic orders --params HOST=override.host
```

Notebook parameters should be declared in a parameters cell:

```python
# %% [parameters]
HOST = ""
SCHEMA = "dbo"
```

The pipeline helper embeds concrete parameter values in each `TridentNotebook` activity. Do not rely on `@pipeline().parameters.X` for notebook activities.

## Daily Workflow Commands

Build and deploy notebooks from the target repository root:

```bash
python tool/data/mock-data-generator.py --schema '[{"name":"id","type":"id"},{"name":"amount","type":"decimal"}]' --topic <topic> --rows 1000
python tool/data/mock-data-generator.py --engine faker --topic <topic> --rows 1000 --schema '[{"name":"id","type":"id"},{"name":"name","type":"name"},{"name":"email","type":"email"}]'
python tool/data/mock-data-generator.py --schema-file schemas/<topic>.json --rows 1000  # schema from file
python tool/validate/pipeline-lineage.py
python tool/notebook/build.py
python tool/notebook/deploy.py deploy <name> <workspace_id>
```

Smoke test an already-deployed notebook:

```powershell
powershell -ExecutionPolicy Bypass -File tool/notebook/smoke-test.ps1 -Notebook <name>
```

```bash
bash tool/notebook/smoke-test.sh --notebook <name>
```

Fetch after a passing run:

```bash
python tool/notebook/deploy.py fetch <name> <workspace_id>
```

Deploy uploads from `fabric_notebooks/<topic>/<name>.Notebook`. Fetch writes the Fabric definition back under `workspace/<topic>/<name>.Notebook/`.

## Pipeline Commands

`tool/pipeline/manage.py` reads `FABRIC_WORKSPACE_ID` from `.env` unless `--workspace` is supplied.

```bash
python tool/pipeline/manage.py create --topic <topic>
python tool/pipeline/manage.py test --topic <topic>
python tool/pipeline/manage.py run --pipeline pipeline_<topic>
python tool/pipeline/manage.py status --pipeline pipeline_<topic> --instance <job-instance-id>
python tool/pipeline/manage.py list
```

By default, notebooks are ordered by prefix:

```text
download_ -> bronze_ -> dq_bronze_ -> silver_ -> dq_silver_ -> gold_ -> dq_gold_
```

Use `--notebooks name1,name2` when a topic needs a custom order.

## Configuration Checklist

Before asking an agent to run Fabric work in a target repository, check:

- `.env` exists.
- `FABRIC_WORKSPACE_ID`, `FABRIC_TENANT_ID`, and `FABRIC_CLIENT_ID` are configured.
- `FABRIC_CLIENT_SECRET` exists in the OS user environment.
- Lakehouse and warehouse IDs exist for any notebook sentinels.
- `FABRIC_WAREHOUSE_HOST` is configured for warehouse/dbt notebooks.
- `tool/setup/fab-sandbox` or `tool/setup/fab-sandbox.ps1` can call `api workspaces`.
- Notebook source uses `Files/...` paths, not `/lakehouse/default/Files/...`.

## Maintainer Checks

Run these from the `fabric-skills-settings` source package, not from an installed target repository:

```bash
uv run bin/validate-install-package.py
uv run bin/validate-agent-guidance.py
uv run --group dev pytest
```

To check alignment of an installed target:

```bash
python bin/install-fabric-agent --profile all --target /path/to/project-repo --check
```
