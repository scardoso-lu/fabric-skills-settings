# Fabric Platform Rules

Microsoft Fabric-specific technical patterns and constraints. These encode hard-won knowledge about how Fabric actually behaves.

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

Single auth flow for all Fabric CLI tools:
```bash
fab auth login    # device-code; token cached at ~/.config/fab/cache.bin
```
All `fab`, `nbmon`, and notebook scripts share this cache. Do not re-authenticate per tool.

For REST API calls, extract the bearer token:
```bash
fab auth token    # prints current bearer token
```
Use this when `fab api` fails on non-JSON endpoints (text/plain responses).

## FP-03: Notebook Authoring

- Author in local `.py` files using `# %%` cell markers
- Build to `.Notebook` format with `bin/build-notebooks.py`
- Deploy with `fab import <path>`
- `fab import` strips `tags` metadata — do not rely on tags for parameter injection
- Notebook cells must end with `\n` to prevent visual merge issues

## FP-04: Debugging (nbmon Only)

`nbmon status <run-id>` is the ONLY reliable debugging path for Spark job failures.
`fab job run-status` gives generic errors only — do not rely on it for diagnosis.

```bash
nbmon status <run-id>    # 7-line diagnostic banner + traceback + Spark Advise category
```

Never pipe full driver logs (~800 KB) into agent context. Use nbmon's summary.

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
