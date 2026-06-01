#!/usr/bin/env python3
"""Generate deterministic sandbox data for Fabric topics and load into PostgreSQL.

Usage:
    python tool/data/mock-data-generator.py --topic orders --rows 1000
    python tool/data/mock-data-generator.py --engine faker --topic customers --rows 1000
    python tool/data/mock-data-generator.py --schema '[{"name":"id","type":"id"},{"name":"email","type":"email"}]' --rows 500
    python tool/data/mock-data-generator.py --schema-file schemas/orders.json --rows 1000
    python tool/data/mock-data-generator.py --engine sklearn --rows 5000

Output table is ``sandbox_<topic>`` in the PostgreSQL database specified by
DATABASE_URL (or --dsn). The table is dropped and recreated on each run.
The generated rows are synthetic and may include PII-shaped fields so
ingestion and DQ notebooks can exercise masking and validation behavior.
Never replace this with real source extracts.

Column types (for --schema / --schema-file):
    id                          Sequential integer starting at 1
    int     [min, max]          Random integer
    float   [min, max, decimals] Random float
    decimal [min, max, decimals] Random decimal (alias for float)
    string  / word / str        Random word
    sentence / text             Random sentence
    name                        Full name
    first_name                  First name
    last_name                   Last name
    email                       Email address
    address                     Street address
    date    [start, end]        ISO date (YYYY-MM-DD)
    datetime / timestamp [start, end]  ISO datetime
    boolean / bool              True or False
    uuid                        UUID v4
    phone                       Phone number
    company                     Company name
    url                         URL
"""

from __future__ import annotations

import argparse
import datetime as dt
import importlib
import json
import os
import re
import random
import uuid as uuid_module
from collections.abc import Iterator
from pathlib import Path
from typing import Any

_TOPIC_RE = re.compile(r"^[a-zA-Z0-9_\-]+$")
_SCRIPT_ROOT = Path(__file__).resolve().parents[2]

# PostgreSQL column type mapping
_PG_TYPES: dict[str, str] = {
    "id": "INTEGER",
    "int": "INTEGER",
    "float": "DOUBLE PRECISION",
    "decimal": "NUMERIC",
    "date": "DATE",
    "datetime": "TIMESTAMP",
    "timestamp": "TIMESTAMP",
    "boolean": "BOOLEAN",
    "bool": "BOOLEAN",
    "uuid": "UUID",
    "string": "TEXT",
    "word": "TEXT",
    "str": "TEXT",
    "sentence": "TEXT",
    "text": "TEXT",
    "name": "TEXT",
    "first_name": "TEXT",
    "last_name": "TEXT",
    "email": "TEXT",
    "address": "TEXT",
    "phone": "TEXT",
    "company": "TEXT",
    "url": "TEXT",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--topic", default="orders", help="Topic name; output table is sandbox_<topic>")
    parser.add_argument("--rows", type=int, default=1000, help="Number of rows to generate")
    parser.add_argument("--seed", type=int, default=42, help="Deterministic random seed")
    parser.add_argument(
        "--engine",
        choices=["stdlib", "faker", "mimesis", "sklearn"],
        default="stdlib",
        help="Generation engine. Optional engines require their Python package to be installed.",
    )
    schema_group = parser.add_mutually_exclusive_group()
    schema_group.add_argument(
        "--schema",
        help='JSON array of column definitions: \'[{"name":"id","type":"id"},{"name":"email","type":"email"}]\'',
    )
    schema_group.add_argument(
        "--schema-file",
        type=Path,
        metavar="PATH",
        help="Path to a JSON file containing a column definitions array.",
    )
    parser.add_argument(
        "--dsn",
        help="PostgreSQL connection string. Defaults to DATABASE_URL environment variable.",
    )
    return parser.parse_args(argv)


def load_schema(args: argparse.Namespace) -> list[dict[str, Any]]:
    if args.schema:
        try:
            return json.loads(args.schema)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"--schema is not valid JSON: {exc}") from exc
    if args.schema_file:
        try:
            return json.loads(Path(args.schema_file).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SystemExit(f"--schema-file error: {exc}") from exc
    raise SystemExit(
        "error: --schema or --schema-file is required for all engines.\n"
        "Inspect your target table (e.g. python tool/lakehouse/list-tables.py) and pass its columns:\n"
        '  --schema \'[{"name":"id","type":"id"},{"name":"email","type":"email"}]\'\n'
        "  --schema-file schemas/<topic>.json\n"
        "For sklearn, declare float columns (features) and a target column:\n"
        '  --engine sklearn --schema \'[{"name":"id","type":"id"},{"name":"price","type":"float","decimals":4},{"name":"qty","type":"float","decimals":4},{"name":"target","type":"int"}]\''
    )


def require_module(module_name: str, install_hint: str) -> Any:
    try:
        return importlib.import_module(module_name)
    except ImportError as exc:
        raise SystemExit(f"{module_name} is required for this engine. Install it first: {install_hint}") from exc


# --- stdlib engine -----------------------------------------------------------

def _stdlib_value(col: dict[str, Any], index: int, rng: random.Random) -> Any:
    ctype = col["type"].lower()
    col_name = col["name"]
    if ctype == "id":
        return index
    if ctype == "int":
        return rng.randint(int(col.get("min", 0)), int(col.get("max", 1000)))
    if ctype in ("float", "decimal"):
        decimals = int(col.get("decimals", 4))
        return round(rng.uniform(float(col.get("min", 0.0)), float(col.get("max", 1.0))), decimals)
    if ctype == "date":
        start = dt.date.fromisoformat(col.get("start", "2026-01-01"))
        end = dt.date.fromisoformat(col.get("end", "2026-12-31"))
        return start + dt.timedelta(days=rng.randint(0, (end - start).days))
    if ctype in ("datetime", "timestamp"):
        start = dt.date.fromisoformat(col.get("start", "2026-01-01"))
        end = dt.date.fromisoformat(col.get("end", "2026-12-31"))
        seconds = rng.randint(0, (end - start).days * 86400)
        return dt.datetime(start.year, start.month, start.day) + dt.timedelta(seconds=seconds)
    if ctype in ("boolean", "bool"):
        return rng.choice([True, False])
    if ctype == "uuid":
        return uuid_module.UUID(int=rng.getrandbits(128))
    if ctype == "email":
        return f"user.{index}@example.test"
    if ctype == "name":
        return f"User {index}"
    if ctype == "first_name":
        return f"First{index}"
    if ctype == "last_name":
        return f"Last{index}"
    if ctype == "address":
        return f"{rng.randint(1, 200)} Street, City {index}"
    if ctype in ("sentence", "text"):
        return f"Synthetic record {index}."
    if ctype == "phone":
        return f"+{rng.randint(1, 99)}-{rng.randint(100, 999)}-{rng.randint(1000, 9999)}"
    if ctype == "company":
        return f"Company {index}"
    if ctype == "url":
        return f"https://example.test/{col_name}/{index}"
    return f"{col_name}_{index}"


def stdlib_rows(rows: int, seed: int, schema: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
    rng = random.Random(seed)
    for index in range(1, rows + 1):
        yield {col["name"]: _stdlib_value(col, index, rng) for col in schema}


# --- faker engine ------------------------------------------------------------

def _faker_value(col: dict[str, Any], index: int, fake: Any, rng: random.Random) -> Any:
    ctype = col["type"].lower()
    if ctype == "id":
        return index
    if ctype == "int":
        return fake.random_int(min=int(col.get("min", 0)), max=int(col.get("max", 1000)))
    if ctype in ("float", "decimal"):
        decimals = int(col.get("decimals", 2))
        return round(rng.uniform(float(col.get("min", 0.0)), float(col.get("max", 1.0))), decimals)
    if ctype == "date":
        start = dt.date.fromisoformat(col.get("start", "2026-01-01"))
        end = dt.date.fromisoformat(col.get("end", "2026-12-31"))
        return fake.date_between(start_date=start, end_date=end)
    if ctype in ("datetime", "timestamp"):
        return fake.date_time_between(start_date=col.get("start", "-1y"), end_date=col.get("end", "now"))
    if ctype in ("boolean", "bool"):
        return fake.boolean()
    if ctype == "uuid":
        return uuid_module.UUID(fake.uuid4())
    if ctype == "name":
        return fake.name()
    if ctype == "first_name":
        return fake.first_name()
    if ctype == "last_name":
        return fake.last_name()
    if ctype == "email":
        return fake.email()
    if ctype == "address":
        return fake.address().replace("\n", ", ")
    if ctype in ("sentence", "text"):
        return fake.sentence()
    if ctype in ("string", "word", "str"):
        return fake.word()
    if ctype == "phone":
        return fake.phone_number()
    if ctype == "company":
        return fake.company()
    if ctype == "url":
        return fake.url()
    return fake.word()


def faker_rows(rows: int, seed: int, schema: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
    faker_module = require_module("faker", "python -m pip install Faker")
    fake = faker_module.Faker()
    fake.seed_instance(seed)
    rng = random.Random(seed)
    for index in range(1, rows + 1):
        yield {col["name"]: _faker_value(col, index, fake, rng) for col in schema}


# --- mimesis engine ----------------------------------------------------------

def _mimesis_value(col: dict[str, Any], index: int, generic: Any, rng: random.Random) -> Any:
    ctype = col["type"].lower()
    col_name = col["name"]
    if ctype == "id":
        return index
    if ctype == "int":
        return rng.randint(int(col.get("min", 0)), int(col.get("max", 1000)))
    if ctype in ("float", "decimal"):
        decimals = int(col.get("decimals", 2))
        return round(rng.uniform(float(col.get("min", 0.0)), float(col.get("max", 1.0))), decimals)
    if ctype == "date":
        start = dt.date.fromisoformat(col.get("start", "2026-01-01"))
        end = dt.date.fromisoformat(col.get("end", "2026-12-31"))
        return start + dt.timedelta(days=rng.randint(0, (end - start).days))
    if ctype in ("datetime", "timestamp"):
        start = dt.date.fromisoformat(col.get("start", "2026-01-01"))
        end = dt.date.fromisoformat(col.get("end", "2026-12-31"))
        seconds = rng.randint(0, (end - start).days * 86400)
        return dt.datetime(start.year, start.month, start.day) + dt.timedelta(seconds=seconds)
    if ctype in ("boolean", "bool"):
        return rng.choice([True, False])
    if ctype == "uuid":
        return uuid_module.UUID(int=rng.getrandbits(128))
    if ctype == "name":
        return generic.person.full_name()
    if ctype == "first_name":
        return generic.person.first_name()
    if ctype == "last_name":
        return generic.person.last_name()
    if ctype == "email":
        return generic.person.email()
    if ctype == "address":
        return generic.address.address()
    if ctype in ("sentence", "text"):
        return generic.text.sentence()
    if ctype in ("string", "word", "str"):
        return generic.text.word()
    if ctype == "phone":
        return generic.person.telephone()
    if ctype == "company":
        return generic.finance.company()
    if ctype == "url":
        return generic.internet.url()
    return f"{col_name}_{index}"


def mimesis_rows(rows: int, seed: int, schema: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
    mimesis = require_module("mimesis", "python -m pip install mimesis")
    locale = getattr(mimesis, "Locale", None)
    if locale is None:
        locale = require_module("mimesis.locales", "python -m pip install mimesis").Locale
    rng = random.Random(seed)
    try:
        generic = mimesis.Generic(locale.EN, seed=seed)
    except TypeError:
        generic = mimesis.Generic(locale.EN)
        if hasattr(generic, "reseed"):
            generic.reseed(seed)
    for index in range(1, rows + 1):
        yield {col["name"]: _mimesis_value(col, index, generic, rng) for col in schema}


# --- sklearn engine ----------------------------------------------------------

def sklearn_rows(rows: int, seed: int, schema: list[dict[str, Any]]) -> Iterator[dict[str, Any]]:
    datasets = require_module("sklearn.datasets", "python -m pip install scikit-learn")
    feature_cols = [c for c in schema if c["type"] in ("float", "decimal")]
    n_features = len(feature_cols) or 4
    features, targets = datasets.make_classification(
        n_samples=rows,
        n_features=n_features,
        n_informative=max(1, n_features - 1),
        n_redundant=0,
        n_clusters_per_class=1,
        weights=[0.85, 0.15],
        random_state=seed,
    )
    target_col = next((c for c in schema if c["name"] == "target"), {"name": "target"})
    for index, (feature_row, target) in enumerate(zip(features, targets, strict=True), start=1):
        row: dict[str, Any] = {"id": index}
        for i, col in enumerate(feature_cols):
            row[col["name"]] = round(float(feature_row[i]), int(col.get("decimals", 6)))
        row[target_col["name"]] = int(target)
        yield row


# --- dispatch ----------------------------------------------------------------

def build_rows(args: argparse.Namespace, schema: list[dict[str, Any]]) -> tuple[list[str], Iterator[dict[str, Any]]]:
    fieldnames = [col["name"] for col in schema]
    engines = {
        "sklearn": lambda: sklearn_rows(args.rows, args.seed, schema),
        "faker":   lambda: faker_rows(args.rows, args.seed, schema),
        "mimesis": lambda: mimesis_rows(args.rows, args.seed, schema),
        "stdlib":  lambda: stdlib_rows(args.rows, args.seed, schema),
    }
    return fieldnames, engines[args.engine]()


# --- PostgreSQL output -------------------------------------------------------

def write_postgres(
    dsn: str,
    table_name: str,
    schema: list[dict[str, Any]],
    rows: Iterator[dict[str, Any]],
    batch_size: int = 1000,
) -> int:
    try:
        import psycopg2
        import psycopg2.extras
    except ImportError as exc:
        raise SystemExit(
            "psycopg2 is required to write to PostgreSQL. "
            "Install it: pip install psycopg2-binary"
        ) from exc

    fieldnames = [col["name"] for col in schema]
    col_defs = ", ".join(
        f'"{col["name"]}" {_PG_TYPES.get(col["type"].lower(), "TEXT")}'
        for col in schema
    )
    quoted_cols = ", ".join('"' + f + '"' for f in fieldnames)
    insert_sql = f'INSERT INTO "{table_name}" ({quoted_cols}) VALUES %s'

    count = 0
    with psycopg2.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(f'DROP TABLE IF EXISTS "{table_name}"')
            cur.execute(f'CREATE TABLE "{table_name}" ({col_defs})')
            batch: list[tuple] = []
            for row in rows:
                batch.append(tuple(row[f] for f in fieldnames))
                count += 1
                if len(batch) >= batch_size:
                    psycopg2.extras.execute_values(cur, insert_sql, batch)
                    batch = []
            if batch:
                psycopg2.extras.execute_values(cur, insert_sql, batch)
        conn.commit()
    return count


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.rows < 1:
        raise SystemExit("--rows must be greater than zero")
    if not _TOPIC_RE.match(args.topic):
        raise SystemExit(
            f"Invalid topic name {args.topic!r}. "
            "Only alphanumeric characters, hyphens, and underscores are allowed."
        )

    dsn = args.dsn or os.environ.get("DATABASE_URL", "").strip()
    if not dsn:
        raise SystemExit(
            "No PostgreSQL connection string found. "
            "Set DATABASE_URL or pass --dsn postgresql://user:pass@host/db"
        )

    schema = load_schema(args)
    table_name = f"sandbox_{args.topic.replace('-', '_')}"
    _, rows = build_rows(args, schema)
    count = write_postgres(dsn, table_name, schema, rows)
    print(f"Generated {count} synthetic rows into table {table_name!r} using {args.engine}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
