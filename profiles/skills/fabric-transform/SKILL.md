---
name: fabric-transform
description: Transform Bronze data into Silver — clean, deduplicate, enforce schema, and MERGE into Delta tables. Prefer SQL, fall back to SQL+Python hybrid for complex logic, use pure Python as a last resort. DQ checks run in a separate dq_silver_<source>.py notebook using Great Expectations.
---

# fabric-transform

## MUST

- Cast all columns explicitly — never leave Bronze string types in Silver
- Use Delta MERGE for upserts — never plain APPEND to Silver
- Preserve lineage envelope columns from Bronze
- Log rows dropped due to null PKs — never drop silently

## PREFER

- **SQL first** — use `spark.sql(...)` for all casting, joining, coalescing, and MERGE; it is readable, portable, and debuggable in the Fabric SQL editor
- SQL MERGE over the DeltaTable Python API when the logic is expressible in a single statement
- `mergeSchema=True` on MERGE operations for schema evolution
- Z-ORDER Silver tables by high-cardinality filter columns after bulk writes
- Null strategy: string fields → `""` or `"Unknown"`, numeric fields → keep null (never zero-fill)

## AVOID

- Dropping records silently — always log a count and reason before dropping
- Plain `df.write.mode("append")` in Silver (creates duplicates)
- `df.show()` or `print(df)` in production notebooks
- Zero-filling numeric nulls (hides data quality issues from downstream)
- Any DQ assertion logic — that belongs in the separate `dq_silver_<source>.py` notebook

---

## Implementation Hierarchy

Choose the **first tier** whose complexity the logic fits into.

### Tier 1 — Full SQL (preferred)

Use when casting, coalescing, joining, and the MERGE are all expressible in one or two SQL statements. Python is only used for logging and to surface the null PK count.

```python
# %% [transform]
null_pk_count = spark.sql(
    "SELECT COUNT(*) FROM bronze_orders WHERE order_id IS NULL"
).collect()[0][0]
if null_pk_count > 0:
    print(f"[WARN] {null_pk_count} rows with null order_id excluded from Silver")

# %% [merge]
spark.sql("""
    MERGE INTO silver_orders AS target
    USING (
        SELECT
            CAST(order_id       AS INT)            AS order_id,
            CAST(order_date     AS TIMESTAMP)       AS order_date,
            CAST(amount         AS DECIMAL(18, 2))  AS amount,
            COALESCE(status, 'Unknown')             AS status,
            _ingest_timestamp,
            _source_system,
            _batch_id
        FROM bronze_orders
        WHERE order_id IS NOT NULL
    ) AS source
    ON target.order_id = source.order_id
    WHEN MATCHED AND source._ingest_timestamp > target._ingest_timestamp
        THEN UPDATE SET *
    WHEN NOT MATCHED
        THEN INSERT *
""")
```

### Tier 2 — SQL + Python hybrid

Use when the SQL MERGE USING subquery would require 3+ levels of CTEs, complex window functions, or dynamic column handling that SQL cannot express cleanly. SQL owns the transformation; Python owns the control flow and MERGE execution.

```python
# %% [transform — SQL handles casting and business rules]
df_silver = spark.sql("""
    WITH ranked AS (
        SELECT
            CAST(order_id   AS INT)           AS order_id,
            CAST(order_date AS TIMESTAMP)     AS order_date,
            CAST(amount     AS DECIMAL(18,2)) AS amount,
            COALESCE(status, 'Unknown')       AS status,
            _ingest_timestamp,
            _source_system,
            _batch_id,
            ROW_NUMBER() OVER (
                PARTITION BY order_id
                ORDER BY _ingest_timestamp DESC
            ) AS rn
        FROM bronze_orders
        WHERE order_id IS NOT NULL
    )
    SELECT * EXCEPT (rn) FROM ranked WHERE rn = 1
""")

# %% [merge — Python handles MERGE execution and logging]
null_pk_count = spark.sql(
    "SELECT COUNT(*) FROM bronze_orders WHERE order_id IS NULL"
).collect()[0][0]
if null_pk_count > 0:
    print(f"[WARN] {null_pk_count} rows with null order_id excluded from Silver")

from delta.tables import DeltaTable
silver = DeltaTable.forPath(spark, silver_path)
silver.alias("target").merge(
    source=df_silver.alias("source"),
    condition="target.order_id = source.order_id"
).whenMatchedUpdate(
    condition="source._ingest_timestamp > target._ingest_timestamp",
    set={"col1": "source.col1", "col2": "source.col2", "_ingest_timestamp": "source._ingest_timestamp"}
).whenNotMatchedInsertAll(
).execute()
```

### Tier 3 — Pure Python with Fabric Spark (last resort)

Use only when SQL cannot express the logic — e.g. recursive computation, dynamic schema resolution, or Python-specific business rules. Full DataFrame API throughout.

```python
# %% [transform]
from pyspark.sql import functions as F
from pyspark.sql.types import IntegerType, TimestampType, DecimalType

df_cast = df.select(
    F.col("order_id").cast(IntegerType()).alias("order_id"),
    F.col("order_date").cast(TimestampType()).alias("order_date"),
    F.col("amount").cast(DecimalType(18, 2)).alias("amount"),
    F.coalesce(F.col("status"), F.lit("Unknown")).alias("status"),
    F.col("_ingest_timestamp"),
    F.col("_source_system"),
    F.col("_batch_id"),
)

null_pk_count = df_cast.filter(F.col("order_id").isNull()).count()
if null_pk_count > 0:
    print(f"[WARN] Dropping {null_pk_count} rows with null order_id before Silver write")
df_silver = df_cast.filter(F.col("order_id").isNotNull())

# %% [merge]
from delta.tables import DeltaTable
silver = DeltaTable.forPath(spark, silver_path)
silver.alias("target").merge(
    source=df_silver.alias("source"),
    condition="target.order_id = source.order_id"
).whenMatchedUpdate(
    condition="source._ingest_timestamp > target._ingest_timestamp",
    set={"col1": "source.col1", "col2": "source.col2", "_ingest_timestamp": "source._ingest_timestamp"}
).whenNotMatchedInsertAll(
).execute()
```

---

## Z-ORDER After Bulk Write

```python
spark.sql(f"OPTIMIZE delta.`{silver_path}` ZORDER BY (event_date, customer_id)")
```
