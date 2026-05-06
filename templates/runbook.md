# Runbook: [Pipeline Name]

> Fill Phase 1 before the first run. Fill Phase 2 after the first successful run, when observed runtime, row counts, and failure modes are known.

## Phase 1 — Before First Run

### Asset

- **Item**:
- **Workspace**:
- **Environment**: sandbox | dev | prod
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
- **Expected quarantine rate**:
- **Success indicator**: `✓ Pipeline Finished: Processed X records`
- **Normal nbmon status**:

### Validation (run after each execution)

```sql
-- Check quarantine table.
SELECT COUNT(*)
FROM <table>_quarantine
WHERE _batch_id = '<latest>';

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
| AnalysisException: table not found | Lakehouse ID mismatch | Check BRONZE/SILVER/GOLD_LAKEHOUSE_ID in `.env` |
| 401 Unauthorized | Token expired | Run `fab auth login` |
| Quarantine rate >5% | Schema change or sensitive data issue | Escalate to operator, inspect quarantine reasons, update contract/casting |

### Recovery Steps

1. Check `nbmon status <run-id>` for error details.
2. Fix root cause (see failure modes above).
3. Re-run with the same batch parameters (idempotent).
4. Run validation checks.
5. Verify quarantine rate returns to the expected range.

## Validation Log

| Date | Batch ID | Status | Records | Quarantine Rate | Notes |
|---|---|---|---|---|---|
| | | | | | |
