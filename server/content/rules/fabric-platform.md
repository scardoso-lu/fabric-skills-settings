---
name: fabric-platform
description: Fabric API, auth wrapper, notebook, lakehouse, warehouse, and Delta maintenance rules.
kind: rule
---

# Fabric Platform Rules

Microsoft Fabric-specific technical patterns and constraints.

## FP-01: Async API Pattern (202 + Poll)

All Fabric creation and job APIs return HTTP 202 immediately. You MUST poll:
```python
response = requests.post(url, json=payload, headers=headers)
# response.status_code == 202
operation_url = response.headers['Location']
while True:
    status = requests.get(operation_url, headers=headers).json()
    if status['status'] == 'Succeeded':
        break
    elif status['status'] == 'Failed':
        raise RuntimeError(status['error'])
    time.sleep(5)
```
Never assume a 202 means the operation completed.

## FP-02: Authentication

Authentication is a one-time human step performed by `tool/setup/setup.ps1`
(Windows) or `tool/setup/setup.sh` (Linux/Mac), which logs the service
principal in and writes credentials to `.env` + the OS environment. Agents
**never** run login/token commands or pass credentials on the command line —
they only verify the setup gate (see [[graph-content/entry]]).

For workspace and item operations, go through the `fabric-cli` proxy and the
`fabric-server` MCP tools — never call the Fabric CLI directly from rules:

- Workspace / resource discovery: `fabric-cli workspace init`
- Active workspace + resource IDs: `fabric-cli workspace switch <displayName>`
- Notebook / pipeline / lakehouse operations: the matching `fabric-cli` subcommands (FP-03, FP-04)

## FP-03: Notebook Authoring

- Author in local `.py` files using `# %%` cell markers
- Build to `.Notebook` format with `fabric-cli notebook build`
- Deploy via REST API: `fabric-cli notebook deploy deploy <name> <workspace_id>`
- Full loop: `fabric-cli notebook smoke-test --notebook <name>` (reads `FABRIC_WORKSPACE_ID` from `.env`)
- Raw `fab import` and `fab job run` require an interactive Windows console — do not use them in automated or non-interactive environments. Use `fabric-cli notebook deploy` and `fabric-cli notebook smoke-test`.
- `tags` metadata is stripped by the REST API — do not rely on tags for parameter injection
- Notebook cells must end with `\n` to prevent visual merge issues

## FP-04: Debugging Job Runs

Use `fabric-cli notebook deploy monitor` for real-time status polling:

```bash
fabric-cli notebook deploy monitor <workspace_id> <item_id> <job_instance_id>
```

For detailed error traces, open the Fabric portal: Activities → Notebook runs → select the failed run.

Raw `fab job run-status` and `nbmon status` require an interactive Windows console — do not use them in Git Bash or non-interactive environments.

## FP-05: Spark vs SQL Endpoint

| Use Case | Use |
|---|---|
| Delta Lake writes | Spark kernel (Spark notebook or pipeline) |
| Read-only analytics | SQL endpoint (serverless, fast startup) |
| Interactive debugging | Livy session (read-only, cannot write to lakehouses) |

Spark kernel required for all Delta Lake writes. Jupyter kernel cannot write to lakehouses.

## FP-06: Lakehouse Separation

Separate lakehouse per medallion layer:
- `<project>_bronze_lh`
- `<project>_silver_lh`
- `<project>_gold_lh`

Reason: independent access control, cleaner governance, prevents Silver processes from accidentally reading unmasked Bronze data.

## FP-07: File Ingestion

Fabric Spark cannot read from arbitrary HTTP/HTTPS URLs. Stage files first:
1. Use Data Factory Copy activity → `Files/landing/` in Lakehouse
2. Then read from `Files/landing/` in Spark notebook

## FP-08: Gold Layer Optimization

Every Gold table write must include:
```python
# After writing
spark.sql(f"OPTIMIZE {table_name} ZORDER BY ({', '.join(filter_columns)})")
```
Also enable on write:
```python
spark.conf.set("spark.sql.parquet.vorder.enabled", "true")
spark.conf.set("spark.microsoft.delta.optimizeWrite.enabled", "true")
```

Use the `fabric-model` skill when designing Gold facts, dimensions, KPIs, and semantic-model-aligned outputs.

## FP-09: Warehouse Patterns

- Use `sqlcmd (Go)` with `-G` flag for Entra auth — no ODBC driver required
- Use `COPY INTO` for file ingestion (highest throughput)
- Avoid MERGE in Fabric Warehouse (still preview) — use DELETE + INSERT instead
- Target ~2M rows / ~400MB per file: `maxRecordsPerFile=2000000`

## FP-10: Delta Maintenance

```python
# Weekly vacuum — always specify retention
delta_table.vacuum(retention_hours=168)  # 7 days

# Never run retention=0 except for explicit toxic data purge
# Always run OPTIMIZE after bulk writes
spark.sql(f"OPTIMIZE {table_name}")
```
