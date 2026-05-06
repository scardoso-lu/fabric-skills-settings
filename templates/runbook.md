# Runbook: [Pipeline Name]

## Asset

- **Item**: 
- **Workspace**: 
- **Schedule**: 
- **Owner**: 

## Dependencies

| Dependency | Type | Required Before |
|---|---|---|
| | upstream pipeline | this pipeline |

## Normal Behavior

- **Expected runtime**: 
- **Expected row count**: 
- **Success indicator**: `✓ Pipeline Finished: Processed X records`

## Validation (run after each execution)

```bash
# Check quarantine table
SELECT COUNT(*) FROM <table>_quarantine WHERE _batch_id = '<latest>';

# Check row count
SELECT COUNT(*) FROM <table>;
```

## Failure Modes

| Symptom | Likely Cause | Resolution |
|---|---|---|
| AnalysisException: table not found | Lakehouse ID mismatch | Check BRONZE_LAKEHOUSE_ID in .env |
| 401 Unauthorized | Token expired | Run `fab auth login` |
| Quarantine rate >5% | Schema change in source | Check source contract, update casting |

## Recovery Steps

1. Check `nbmon status <run-id>` for error details
2. Fix root cause (see failure modes above)
3. Re-run with same batch parameters (idempotent)
4. Verify quarantine rate returns to <1%

## Rollback

```python
# Delta Time Travel — restore to state before bad run
spark.sql(f"RESTORE TABLE {table_name} TO VERSION AS OF {version_number}")
```

## Security Notes

- Secrets used: [list Key Vault refs]
- PII fields: [list masked fields]
- Access: [who can read the output]
