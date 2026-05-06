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

**Daily**: Check pipeline run status, triage failures, review quarantine tables  
**Weekly**: Run VACUUM, check for schema drift, review slow jobs, check quarantine rate trends  
**Monthly**: Capacity review, access review, Key Vault secret rotation check, stale item audit

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
mkdir -p src/notebooks fabric_notebooks data/sandbox logs

# Copy environment template
cp .env.example .env

# Install Fabric CLI
uv tool install ms-fabric-cli

# Authenticate
fab auth login
```

## Platform Inventory Update

After creating a new Fabric item, add it to `.codex-fabric/memory/platform-inventory/`:
```yaml
- name: bronze_orders_lh
  type: Lakehouse
  workspace: dev-workspace
  owner: data-team
  created: 2025-01-15
  dependencies: [source_erp_api]
  runbook: runbooks/orders-pipeline.md
```
