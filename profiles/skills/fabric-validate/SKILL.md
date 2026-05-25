---
name: fabric-validate
description: Validate pipeline output using Great Expectations — row counts, null PKs, duplicates, schema drift, referential integrity, and business metric sanity. DQ notebooks run after ingestion notebooks and are the sole place where data quality is enforced. Produces a structured PASS/FAIL report.
---

# fabric-validate

## Separation of concerns — non-negotiable

DQ notebooks are **separate from ingestion notebooks**. Never mix DQ logic into a bronze/silver/gold ingestion notebook.

| Notebook | Naming convention |
|---|---|
| Bronze DQ | `dq_bronze_<source>.py` |
| Silver DQ | `dq_silver_<source>.py` |
| Gold DQ | `dq_gold_<model>.py` |

## MUST

- Run checks independently — never rely on or import the ingestion notebook's logic
- Use **Great Expectations** (`great_expectations>=1.0`) for all DQ checks
- Produce a structured PASS/FAIL result; raise `RuntimeError` on failure so Fabric pipeline stops
- Threshold values live in the `# %% [parameters]` cell — never hardcoded, never loaded from YAML at runtime
- Check both the current batch AND row count delta vs previous run

## AVOID

- Loading `config/thresholds.yaml` or any file from disk at runtime — Fabric cannot reach local repository config files at notebook runtime
- Writing to or modifying Bronze/Silver/Gold tables from the DQ notebook — read-only
- Mixing ingestion writes with DQ assertions in the same notebook

## Notebook cell structure

```
# %% [parameters]      — threshold values, table path, batch_id to check
# %% [contract]        — DQContract @dataclass (columns to check, pk, thresholds)
# %% [imports]         — great_expectations, pyspark, os
# %% [load]            — read the Bronze/Silver table into a Spark DataFrame
# %% [expectations]    — build GX suite
# %% [run]             — execute and assert
# %% [report]          — print structured summary
```

## Great Expectations Pattern (GX v1)

```python
# %% [parameters]
BATCH_ID_FILTER: str = ""     # blank = check entire table
ROW_COUNT_MIN: int = 1
NULL_PK_MAX: int = 0
DUPLICATE_PK_MAX: int = 0
NULL_ENVELOPE_MAX: int = 0
ROW_COUNT_DROP_PCT_MAX: float = 20.0  # vs previous run

# %% [contract]
from dataclasses import dataclass, field

@dataclass(frozen=True)
class DQContract:
    table: str
    pk_columns: list[str]
    required_envelope: list[str]
    non_null_columns: list[str]        # business columns that must not be null

CONTRACT = DQContract(
    table="raw_orders",
    pk_columns=["order_id"],
    required_envelope=["_ingest_timestamp", "_source_system", "_batch_id", "_ingest_date"],
    non_null_columns=["order_id"],
)

# %% [imports]
import great_expectations as gx
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

spark = SparkSession.builder.getOrCreate()

# %% [load]
df = spark.read.table(CONTRACT.table)
if BATCH_ID_FILTER:
    df = df.filter(F.col("_batch_id") == BATCH_ID_FILTER)
total_rows = df.count()
print(f"[LOAD] {CONTRACT.table}: {total_rows} rows")

# %% [expectations]
context = gx.get_context(mode="ephemeral")

datasource = context.data_sources.add_spark("spark_ds")
asset = datasource.add_dataframe_asset("table_asset")
batch_def = asset.add_batch_definition_whole_dataframe("batch")

suite = gx.ExpectationSuite(name=f"dq_{CONTRACT.table}")

# Row count
suite.add_expectation(
    gx.expectations.ExpectTableRowCountToBeBetween(min_value=ROW_COUNT_MIN)
)

# Null checks — PK and required business columns
for col in CONTRACT.pk_columns + CONTRACT.non_null_columns:
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column=col)
    )

# Envelope columns present and not null
for col in CONTRACT.required_envelope:
    suite.add_expectation(
        gx.expectations.ExpectColumnToExist(column=col)
    )
    suite.add_expectation(
        gx.expectations.ExpectColumnValuesToNotBeNull(column=col)
    )

context.suites.add(suite)

vd = context.validation_definitions.add(
    gx.ValidationDefinition(name="dq_run", data=batch_def, suite=suite)
)

# %% [run]
result = vd.run(batch_parameters={"dataframe": df})

passed = result["success"]
results_list = result["results"]

# %% [report]
print(f"\n=== DQ Report: {CONTRACT.table} ===")
print(f"total rows : {total_rows}")
print(f"overall    : {'PASS' if passed else 'FAIL'}")
print()
for r in results_list:
    status = "PASS" if r["success"] else "FAIL"
    expectation = r["expectation_config"]["type"]
    print(f"  [{status}] {expectation}")

if not passed:
    raise RuntimeError(
        f"DQ checks failed for {CONTRACT.table} — see report above."
    )
```

## Security DQ Checks

Include these checks in DQ notebooks for tables that receive external or user-generated data (OWASP Data Security Top 10):

| Risk | OWASP | Check | GX Expectation |
|---|---|---|---|
| Unexpected volume spike | DATA3 | Row count within expected ceiling | `ExpectTableRowCountToBeBetween(max_value=EXPECTED_MAX)` |
| PII masking verification | DATA7 | Masked column follows format | `ExpectColumnValuesToMatchRegex(column="email", regex=r"^[A-Z]{3}\*+@.*$")` |
| Audit envelope integrity | DATA5/DATA9 | Envelope columns non-null and in range | `ExpectColumnValuesToBeBetween(column="_ingest_timestamp", ...)` |
| Schema drift | DATA9 | Column set matches contract | `ExpectColumnToExist` for each contract field |

Add `EXPECTED_MAX` and masking regex defaults to the `# %% [parameters]` cell. Set `EXPECTED_MAX = 0` to skip the ceiling check for unbounded tables.

## Standard Expectations Reference

| Check | GX Expectation class |
|---|---|
| Row count ≥ N | `ExpectTableRowCountToBeBetween(min_value=N)` |
| Column not null | `ExpectColumnValuesToNotBeNull(column=c)` |
| Column exists | `ExpectColumnToExist(column=c)` |
| Values in set | `ExpectColumnValuesToBeInSet(column=c, value_set={...})` |
| Values in range | `ExpectColumnValuesToBeBetween(column=c, min_value=0)` |
| No duplicates on key | `ExpectColumnValuesToBeUnique(column=c)` |
| Match regex | `ExpectColumnValuesToMatchRegex(column=c, regex=r"...")` |

## Thresholds (parameter cell defaults)

| Parameter | Default | Meaning |
|---|---|---|
| `ROW_COUNT_MIN` | 1 | Fail if table is empty |
| `NULL_PK_MAX` | 0 | No null primary keys allowed |
| `DUPLICATE_PK_MAX` | 0 | No duplicate keys allowed |
| `NULL_ENVELOPE_MAX` | 0 | All lineage columns must be populated |
| `ROW_COUNT_DROP_PCT_MAX` | 20.0 | Fail if row count drops >20% vs previous run |
