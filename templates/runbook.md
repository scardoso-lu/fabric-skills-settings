---
name: runbook
description: Per-pipeline operational runbook — schedule, ownership, alerts, restart procedure, and SLOs.
kind: template
---

# Runbook: [Pipeline Name]

> Fill Phase 1 before the first run. Fill Phase 2 after the first successful run, when observed runtime, row counts, and failure modes are known.

## Phase 1 — Before First Run

### Asset

- **Item**:
- **Workspace**:
- **Environment**:
- **Schedule**: manual | cron/trigger details
- **Owner**:
- **Run command**:

### Source and Target

| Role | System/Item | Path/Table | Notes |
|---|---|---|---|
| Source | | | |
| Bronze target | | | |
| Silver target | | | |
| Gold target | | | |

### Dependencies

| Dependency | Type | Required Before |
|---|---|---|
| | upstream pipeline | this pipeline |

### Rollback Command

```python
# Delta Time Travel — restore to state before bad run.
spark.sql(f"RESTORE TABLE {table_name} TO VERSION AS OF {version_number}")
```

### Security Notes

- Secrets used: [list Key Vault refs or environment variable names only — never values]
- PII fields: [list masked fields]
- Access: [who can read/write the output]

## Phase 2 — After First Successful Run

<!-- Phase 2 fields — fill in after the first successful run. -->

### Observed Normal Behavior

- **First successful run date**:
- **Expected runtime**:
- **Expected row count**:
- **Expected null PK drops**:
- **Success indicator**: `✓ Pipeline Finished: Processed X records`
- **Normal run status**:

### Validation (run after each execution)

```sql
-- Check row count.
SELECT COUNT(*)
FROM <table>;

-- Check lineage envelope.
SELECT COUNT(*)
FROM <table>
WHERE _ingest_timestamp IS NULL
   OR _source_system IS NULL
   OR _batch_id IS NULL;
```

### Failure Modes

| Symptom | Likely Cause | Resolution |
|---|---|---|
| AnalysisException: table not found | Notebook not attached to expected Lakehouse or table not created | Check notebook Lakehouse attachment and table name |
| 401 Unauthorized | Token expired | Human runs `tool/setup/fab-sandbox auth login` or `tool\setup\fab-sandbox.ps1 auth login` |
| DQ notebook FAIL | Schema change, unexpected nulls, or sensitive data issue | Escalate to developer with failed GX expectation and batch ID |

### Recovery Steps

1. Check Fabric portal (Activities → Notebook runs) for error details, or run `python tool/notebook/deploy.py monitor <workspace_id> <item_id> <job_instance_id>`.
2. Fix root cause (see failure modes above).
3. Re-run with the same batch parameters (idempotent).
4. Run validation checks.
5. Run DQ notebook and verify all GX expectations pass.

## Validation Log

| Date | Batch ID | Status | Records | DQ Result | Notes |
|---|---|---|---|---|---|
| | | | | | |
