---
name: fabric-ops
description: Operate and maintain a Fabric data platform — orchestrate pipeline DAGs, run VACUUM, update platform inventory, manage workspace items, and execute operational routines. Use for day-to-day platform operations, maintenance windows, GDPR purges, or environment setup.
---

# fabric-ops

## MUST

- Run VACUUM weekly on all Delta tables (retention_hours=168)
- Document every scheduled pipeline in a runbook
- Update platform inventory after creating or deleting Fabric items
- Never run `VACUUM RETAIN 0 HOURS` unless explicitly purging toxic or GDPR-flagged data

## PREFER

- `fab` CLI over REST API for item management
- Idempotent setup scripts (running twice causes no harm)
- Runbooks in `templates/runbook.md` format

## AVOID

- Manual portal-only operations without a corresponding CLI command (creates undocumented state)
- Running Gold jobs before Silver is confirmed successful (violates DAG ordering)
- VACUUM with retention <168 hours in normal operations

## Maintenance Routine

**Daily**: Check pipeline run status, triage failures, review DQ notebook results  
**Weekly**: Run VACUUM, check for schema drift, review slow jobs, review DQ trend reports  
**Monthly**: Capacity review, access review, Key Vault secret rotation check, stale item audit

## Lakehouse Inspection

```bash
# List all lakehouses in the workspace with their tables and column schemas
python tool/lakehouse/list-tables.py

# Scope to a specific lakehouse
python tool/lakehouse/list-tables.py --lakehouse bronze_lh

# Inspect one table
python tool/lakehouse/list-tables.py --lakehouse bronze_lh --table raw_orders

# Machine-readable JSON (pipe to jq for filtering)
python tool/lakehouse/list-tables.py --json
```

Column schema is read from each table's Delta transaction log via the OneLake DFS
endpoint using the `fab auth token` credential. If the token is unavailable, table
names and types are still listed without schema.

## Daily Checks

```bash
# List items in the workspace (shows notebooks, lakehouses, etc.)
fab api "workspaces/$FABRIC_WORKSPACE_ID/items" --output_format json

# Check recent job runs for a specific notebook item
fab api "workspaces/$FABRIC_WORKSPACE_ID/items/<item_id>/jobs/instances" --output_format json

# Monitor a specific job instance
python tool/notebook/deploy.py monitor "$FABRIC_WORKSPACE_ID" <item_id> <job_instance_id>
```

Check DQ notebook run results in the Fabric portal (Activities → Notebook runs).

## VACUUM Pattern

```python
from delta.tables import DeltaTable

tables_to_vacuum = [
    f"abfss://bronze@onelake.dfs.fabric.microsoft.com/{lakehouse_id}/Tables/raw_orders",
    f"abfss://silver@onelake.dfs.fabric.microsoft.com/{lakehouse_id}/Tables/silver_orders",
]

for path in tables_to_vacuum:
    dt = DeltaTable.forPath(spark, path)
    dt.vacuum(retention_hours=168)
    print(f"✓ VACUUM complete: {path}")
```

## DAG Orchestration (Data Factory)

1. Bronze notebook → Silver notebook (trigger on success only)
2. Silver notebook → Gold notebook (trigger on success only)
3. On failure: send alert, do NOT cascade to next layer

## Environment Setup

```bash
# Create folder structure for local development
mkdir -p workspace data/sandbox logs

# Copy environment template
cp .env.example .env
# Fill only FABRIC_WORKSPACE_ID for the common sandbox loop.

# Install Fabric CLI
uv tool install ms-fabric-cli

# Authenticate
fab auth login
```

## Platform Inventory Update

After creating a new Fabric item, add it to `memory/platform.md`:
```markdown
## Lakehouses
| Name | Workspace | Layer | Created | Notes |
|---|---|---|---|---|
| bronze_lh | fabric-sandbox | Bronze | 2026-05-06 | Raw + masked ingest tables |

## Source Systems
| Name | Type | Env Var Prefix | Cadence | Sensitive Fields |
|---|---|---|---|---|
| ORDERS | file | SRC_ORDERS | ad hoc sandbox | customer_name, email |
```
