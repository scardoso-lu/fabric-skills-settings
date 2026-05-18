# Data Engineering Rules

Fundamental principles that apply across all data engineering work.

## DE-01: Idempotency

Running a pipeline twice on the same data must produce the same result.
- Ingestion: use partition overwrite (`replaceWhere`) or MERGE, never plain APPEND on re-runs
- Transformation: MERGE on primary keys, never INSERT without deduplication
- Aggregation: overwrite target partition, never accumulate

## DE-02: Lineage Preservation

Every table must be traceable to its source. Minimum lineage columns:
- `_ingest_timestamp` — when data entered the system
- `_source_system` — which system provided it
- `_batch_id` — which pipeline run wrote it

## DE-03: Schema Evolution

- New columns: always allowed via `mergeSchema=True`
- Type changes (`int` → `string`): always fail-safe — log affected record count and cast defensively
- Column removals: never silently drop; update contract and bump schema version

## DE-04: Quality Gates

Every pipeline must define at least:
1. Row count check (source vs. target)
2. Null primary key check
3. Duplicate check on business keys
4. At least one business rule validation (range, reference, format)

Records failing quality checks are logged with count and reason. The DQ notebook raises on any failure and stops the pipeline — there is no silent drop. DQ assertions run in a separate `dq_<layer>_<source>.py` notebook using Great Expectations.

## DE-05: Immutable Bronze

Bronze is append-only and write-once. Never UPDATE or DELETE from Bronze.
If source data changes, insert a new record with a new `_ingest_timestamp`.

## DE-06: MERGE for Upserts

Silver and Gold use Delta MERGE for deduplication:
- Match on business primary key
- UPDATE only if incoming record is newer (`_ingest_timestamp`)
- INSERT if no match

## DE-07: Error Handling

All IO operations (network, disk, external APIs) must be wrapped:
```python
try:
    result = call_api(endpoint)
except Exception as e:
    logger.error(f"API call failed: {e}")
    raise  # surface the failure — do not swallow IO errors silently
```
Silent failures are forbidden.

## DE-08: DAG Ordering

Pipelines must respect layer dependencies:
- Bronze must complete before Silver starts
- Silver must complete before Gold starts
- If a layer fails, downstream layers must not start

## DE-09: Testing Strategy

- **Unit tests**: pure logic, no disk/network IO, fast
- **Integration tests**: full pipeline with local/sandbox Delta tables
- Use `Faker` with `seed(42)` for deterministic synthetic PII in tests — never real data

## DE-10: Code Quality

- Type hints on all Python function signatures
- Functions under 50 lines — split when they grow
- One function, one responsibility
- No `from module import *`
- Standard lib → third-party → local import order
