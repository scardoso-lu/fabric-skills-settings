---
name: fabric-ingest
description: Ingest local sandbox files (CSV, Parquet, JSON, Excel) into a Microsoft Fabric Lakehouse as Bronze Delta tables. Use when loading data from data/sandbox/ into the Bronze layer. Handles sanitization, lineage envelope injection, quarantine routing, and idempotent partition overwrite. Production connections to live systems are configured in Fabric Linked Services — not by agents.
---

# fabric-ingest

## MUST

- Read source files from `data/sandbox/` — never from live databases or APIs directly
- Apply sanitization barrier: load to RAM → mask/redact in RAM → write to Delta
- Inject lineage envelope on every record: `_ingest_timestamp`, `_source_system`, `_batch_id`
- Use `mergeSchema=True` for schema evolution
- Route malformed records to `<table>_quarantine` Delta table — never crash on bad data
- Use `replaceWhere` (partition overwrite) for idempotent re-runs

## PREFER

- Append-only writes to Bronze (never UPDATE or DELETE)
- Partition by `_ingest_date` for tables above ~100k rows
- Delta Lake over raw files (ACID transactions, compression, schema enforcement)
- Read column types explicitly — never trust inferred types from CSV

## AVOID

- Reading from any network path, database, or API endpoint
- Writing raw unmasked data to any Delta table (sanitize first, always)
- Overwriting Bronze partitions without `replaceWhere` (causes duplicates on re-run)
- `df.show()` or `print(df)` with sensitive columns

## Key Pattern

```python
import os, uuid
from datetime import datetime, timezone
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, TimestampType

batch_id = str(uuid.uuid4())
ingest_ts = datetime.now(timezone.utc)
source_system = "ORDERS"  # matches the SRC_<SYSTEM> identifier in .env

# Read from sandbox file
source_path = os.environ["SRC_ORDERS_PATH"]  # e.g., ./data/sandbox/orders.csv

schema = StructType([
    StructField("order_id", IntegerType(), True),
    StructField("customer_id", IntegerType(), True),
    StructField("amount", StringType(), True),   # keep as string until Silver casting
    StructField("order_date", StringType(), True),
])

df = spark.read.format("csv").options(header=True).schema(schema).load(source_path)

# Sanitize in RAM (mask PII before any write)
df = sanitize(df)  # implement per source-contract sensitive_fields

# Inject lineage envelope
df = (df
    .withColumn("_ingest_timestamp", F.lit(ingest_ts).cast(TimestampType()))
    .withColumn("_source_system", F.lit(source_system))
    .withColumn("_batch_id", F.lit(batch_id))
    .withColumn("_ingest_date", F.to_date(F.lit(ingest_ts)))
)

# Write idempotently to Bronze
bronze_path = f"abfss://bronze@onelake.dfs.fabric.microsoft.com/{os.environ['BRONZE_LAKEHOUSE_ID']}/Tables/raw_orders"

(df.write
    .format("delta")
    .option("mergeSchema", "true")
    .partitionBy("_ingest_date")
    .mode("append")
    .save(bronze_path)
)
```

## Supported Sandbox Sources

| Format | How to read |
|---|---|
| CSV | `spark.read.format("csv").options(header=True).schema(schema).load(path)` |
| Parquet | `spark.read.format("parquet").load(path)` |
| JSON (lines) | `spark.read.format("json").load(path)` |
| Excel | read with `pandas.read_excel()` → convert to Spark DataFrame |

## Quarantine Pattern

```python
from pyspark.sql import functions as F

# Rows that fail validation go to quarantine, not to Bronze
bad = df.filter(F.col("order_id").isNull())
good = df.filter(F.col("order_id").isNotNull())

bad = bad.withColumn("_quarantine_reason", F.lit("null primary key"))
bad.write.format("delta").mode("append").save(quarantine_path)
good.write.format("delta").mode("append").save(bronze_path)
```

## Mock Data

If no source file exists, ask the developer to generate it:
```python
# Developer generates with Faker — seed(42) for reproducibility
from faker import Faker
import pandas as pd

fake = Faker(); Faker.seed(42)
rows = [{"order_id": i, "customer_id": fake.random_int(1, 500),
         "amount": fake.pydecimal(2, 2, positive=True),
         "order_date": fake.date_this_year().isoformat()} for i in range(1, 1001)]
pd.DataFrame(rows).to_csv("data/sandbox/orders.csv", index=False)
```
