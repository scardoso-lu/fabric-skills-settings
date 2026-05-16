---
name: mock-data
description: Generate deterministic synthetic CSV files under data/sandbox/ using tool/data/mock-data-generator.py. Use when no real source file exists for a new or demo topic and you need staged data to build the download/bronze/dq notebook pipeline against.
---

# mock-data

## When to use

- A new topic has no real source file yet and you need something to ingest
- A demo or sandbox environment needs repeatable, PII-free data
- You are writing or testing a Bronze notebook and need a staged CSV with a specific shape

Do not use real source extracts. Always generate synthetic data and run it through the normal masking and DQ pipeline.

## Commands

```bash
# Custom schema matching your target table — always pass a schema
python tool/data/mock-data-generator.py --topic orders --rows 1000 \
  --schema '[{"name":"id","type":"id"},{"name":"customer_id","type":"int","min":1,"max":500},{"name":"email","type":"email"},{"name":"amount","type":"decimal","min":2.5,"max":2500,"decimals":2},{"name":"order_date","type":"date","start":"2025-01-01","end":"2025-12-31"}]'

# Schema from a JSON file (reusable across runs)
python tool/data/mock-data-generator.py --topic orders --schema-file schemas/orders.json --rows 5000

# Faker engine for richer PII-shaped values
python tool/data/mock-data-generator.py --engine faker --topic customers --rows 1000 \
  --schema '[{"name":"id","type":"id"},{"name":"full_name","type":"name"},{"name":"email","type":"email"},{"name":"phone","type":"phone"},{"name":"address","type":"address"}]'

# ML fixtures — schema declares feature columns (float/decimal) and a target column
python tool/data/mock-data-generator.py --engine sklearn --rows 5000 \
  --schema '[{"name":"id","type":"id"},{"name":"price","type":"float","decimals":4},{"name":"quantity","type":"float","decimals":4},{"name":"target","type":"int"}]'
```

Output lands at `data/sandbox/<topic>.csv`.

## Schema column types

| Type | Options | Notes |
|---|---|---|
| `id` | — | Sequential integer starting at 1 |
| `int` | `min`, `max` | Random integer |
| `float` / `decimal` | `min`, `max`, `decimals` | Random float |
| `string` / `word` / `str` | — | Random word |
| `sentence` / `text` | — | Random sentence |
| `name` | — | Full name |
| `first_name` / `last_name` | — | Name parts |
| `email` | — | Email address |
| `address` | — | Street address |
| `date` | `start`, `end` | ISO date (YYYY-MM-DD) |
| `datetime` / `timestamp` | `start`, `end` | ISO datetime |
| `boolean` | — | True or False |
| `uuid` | — | UUID v4 |
| `phone` | — | Phone number |
| `company` | — | Company name |
| `url` | — | URL |

## Engine selection guide

| Engine | Install | When to use |
|---|---|---|
| `stdlib` (default) | none | No-dependency fallback; string types produce placeholders (`name_1`, `user.1@example.test`) |
| `faker` | `pip install Faker` | Realistic PII-shaped values for UI tests or simple databases |
| `mimesis` | `pip install mimesis` | Very high-volume generation (millions of rows) at speed |
| `sklearn` | `pip install scikit-learn` | Controlled ML classification fixtures with known class balance |

## After generating

The staged CSV still needs the full three-notebook pipeline:

1. `download_<source>.py` — skip if file already staged; otherwise simulate a fetch
2. `bronze_<source>.py` — ingest only new files; mask any PII-shaped columns
3. `dq_bronze_<source>.py` — Great Expectations checks on the Bronze table

Synthetic PII-shaped columns (`email`, `name`, `address`, `phone`) must go through the same masking barrier as real data.
