---
name: fabric-ingest
description: Ingest local staged files (CSV, Parquet, JSON, Excel) into a Microsoft Fabric Lakehouse as Bronze Delta tables. Use when loading data from the target repo's data/sandbox/ into the Bronze layer. Handles sanitization, lineage envelope injection, and idempotent partition overwrite.
---

# fabric-ingest

## Separation of concerns — non-negotiable

Each source produces **three notebooks**:

| Notebook | Naming | Job |
|---|---|---|
| Download | `download_<source>.py` | Call source API → skip existing sandbox files → save raw files as-is. No Spark. No Delta writes. |
| Ingestion | `bronze_<source>.py` | Read sandbox files → compare against Bronze Delta table → process only new files → MERGE/partition-overwrite. Never full-overwrite. |
| Data quality | `dq_bronze_<source>.py` | Run Great Expectations checks on the Bronze table. Fail the job if checks fail. |

**Never combine these responsibilities.** A single notebook that downloads + ingests + overwrites is always wrong.

## MUST

- Read source files from `data/sandbox/` in this repository. Never read from live databases or APIs directly.
- Apply sanitization barrier: load to RAM → mask/redact in RAM → write to Delta
- Inject lineage envelope on every record: `_ingest_timestamp`, `_source_system`, `_batch_id`, `_ingest_date`
- Use `mergeSchema=True` for schema evolution
- Use `replaceWhere` (partition overwrite) for idempotent re-runs — write all rows, not a filtered subset
- **Source contracts are Python `@dataclass` embedded in the notebook** (`# %% [contract]` cell) — never YAML files
- **Downloads are Python notebooks** (`download_sources.py`) — never `.sh` scripts; use `mssparkutils` detection for Fabric vs local
- **Thresholds belong in the DQ notebook's parameter cell**, not in the ingestion notebook
- **`download_<source>` must skip existing sandbox files** — check by filename before downloading; never re-download a file already present in `Files/data/sandbox/<topic>/`
- **`bronze_<source>` must process only new files** — compare sandbox filenames against records already in the Bronze Delta table; do not reprocess files already ingested
- **`bronze_<source>` must use MERGE or partition-overwrite** — never full-overwrite the Bronze table; use `replaceWhere` or Delta MERGE so existing partitions are preserved

## PREFER

- Append-only writes to Bronze (never UPDATE or DELETE)
- Partition by `_ingest_date` for tables above ~100k rows
- Delta Lake over raw files (ACID transactions, compression, schema enforcement)
- All columns as `StringType` at Bronze — Silver is responsible for casting
- Read column types explicitly — never trust CSV type inference

## AVOID

- Reading from any network path, database, or API endpoint
- Writing raw unmasked data to any Delta table (sanitize first, always)
- Any filtering, splitting, or conditional writes based on data quality — that belongs in the DQ notebook
- `df.show()` or `print(df)` with sensitive columns
- Absolute paths like `/lakehouse/default/Files/...` — Fabric's `mssparkutils` rejects them; use lakehouse-relative paths: `Files/data/sandbox/...`

## Source organisation

Notebooks live under `workspace/<topic>/` — one subfolder per data source or business domain. The agent picks the folder name from the data subject (snake_case, short, descriptive — e.g. `lux_energy_price`, `lux_residence`). Stems must be unique across all subfolders because Fabric display names are flat.

```
workspace/
  lux_energy_price/
    download_electricity_day_ahead_prices.py
    bronze_electricity_day_ahead_prices.py
    dq_bronze_electricity_day_ahead_prices.py
  lux_residence/
    download_population_stats.py
    bronze_population_stats.py
    dq_bronze_population_stats.py
```

## Notebook cell structure

```
# %% [parameters]      — source path override, ingest date override
# %% [contract]        — BronzeContract @dataclass
# %% [imports]         — os, uuid, datetime, pyspark imports
# %% [schemas]         — StructType definitions (all StringType)
# %% [helpers]         — add_lineage_envelope(), write_bronze()
# %% [ingest]          — read → sanitize → envelope → write
# %% [summary]         — print row counts, batch_id, table path
```

## Key Pattern

```python
# %% [parameters]
SOURCE_PATH: str = ""        # blank = resolved from env
INGEST_DATE_OVERRIDE: str = ""

# %% [contract]
from dataclasses import dataclass

@dataclass(frozen=True)
class BronzeContract:
    source_system: str
    grain: str
    primary_keys: list[str]
    bronze_table: str
    sensitive_fields: list[str]
    sensitivity: str

CONTRACT = BronzeContract(
    source_system="ORDERS",
    grain="one order line item",
    primary_keys=["order_id"],
    bronze_table="raw_orders",
    sensitive_fields=[],
    sensitivity="internal",
)

# %% [imports]
import os, uuid
from datetime import datetime, timezone, date
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StructField, StringType

spark = SparkSession.builder.getOrCreate()
BATCH_ID = str(uuid.uuid4())
INGEST_TS = datetime.now(timezone.utc)
INGEST_DATE = (
    datetime.fromisoformat(INGEST_DATE_OVERRIDE).date()
    if INGEST_DATE_OVERRIDE else INGEST_TS.date()
)
SRC = SOURCE_PATH or "Files/data/sandbox/orders.csv"  # lakehouse-relative, not /lakehouse/default/...

# %% [schemas]
SCHEMA = StructType([
    StructField("order_id",    StringType(), True),
    StructField("customer_id", StringType(), True),
    StructField("amount",      StringType(), True),
    StructField("order_date",  StringType(), True),
])

# %% [helpers]
def add_lineage_envelope(df: DataFrame) -> DataFrame:
    return (df
        .withColumn("_ingest_timestamp", F.lit(INGEST_TS).cast("timestamp"))
        .withColumn("_source_system",    F.lit(CONTRACT.source_system))
        .withColumn("_batch_id",         F.lit(BATCH_ID))
        .withColumn("_ingest_date",      F.lit(str(INGEST_DATE)).cast("date"))
    )

def write_bronze(df: DataFrame) -> None:
    (df.write
        .format("delta")
        .option("mergeSchema", "true")
        .option("replaceWhere", f"_ingest_date = '{INGEST_DATE}'")
        .partitionBy("_ingest_date")
        .mode("overwrite")
        .saveAsTable(CONTRACT.bronze_table)
    )

# %% [ingest]
df = spark.read.format("csv").options(header=True, enforceSchema=True).schema(SCHEMA).load(SRC)
df = add_lineage_envelope(df)
write_bronze(df)

# %% [summary]
print(f"[OK] {CONTRACT.bronze_table}: {df.count()} rows written")
print(f"     batch_id={BATCH_ID}  ingest_date={INGEST_DATE}")
print(f"     table={CONTRACT.bronze_table}")
```

## Supported Sources

| Format | How to read |
|---|---|
| CSV | `spark.read.format("csv").options(header=True).schema(schema).load(path)` |
| Parquet | `spark.read.format("parquet").load(path)` |
| GeoJSON | `spark.read.format("json").option("multiLine","true").load(path)` then `explode(col("features"))` |
| Excel | `pandas.read_excel()` → `spark.createDataFrame(pd_df)` |

## Multi-notebook pipelines

When a `download_sources.py` notebook fetches files that the Bronze notebook then reads, the paths **must match exactly**. Use a single shared constant so the match is guaranteed in code, not by coincidence:

```python
# Both download_sources.py and bronze_<source>.py — same value in both files
FABRIC_STAGING_DIR = "Files/data/sandbox/<topic>/xml"
LOCAL_STAGING_DIR  = "data/sandbox/<topic>/xml"
```

Use `mssparkutils` detection to resolve the active path at runtime:

```python
try:
    from notebookutils import mssparkutils as mss
    IS_FABRIC = True
except ImportError:
    IS_FABRIC = False

OUTPUT_DIR = FABRIC_STAGING_DIR if IS_FABRIC else LOCAL_STAGING_DIR
```

After any change to a staging directory constant, verify consistency before building:

```bash
python tool/validate/pipeline-lineage.py
```

A path mismatch produces a silent empty read — no error, just missing data. A FAIL must be fixed before building or deploying.

## Non-standard packages

The Fabric Spark runtime does not include packages like `great_expectations`, `requests`, or `lxml`. Add a `%pip install` cell as the **first cell** of any notebook that needs them:

```python
# %% [install]
%pip install "great_expectations>=1.0,<2.0"
```

This works when the notebook is API-triggered because `deploy.py` sets `_inlineInstallationEnabled` automatically.

## Mock Data

Use the **mock-data** skill to generate a synthetic `data/sandbox/<topic>.csv` before building the notebook pipeline.
