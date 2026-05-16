#!/usr/bin/env python3
"""Generate deterministic sandbox data for Fabric topics.

Usage:
    python tool/data/mock-data-generator.py --topic orders --rows 1000
    python tool/data/mock-data-generator.py --engine faker --topic customers --rows 1000
    python tool/data/mock-data-generator.py --schema '[{"name":"id","type":"id"},{"name":"email","type":"email"}]' --rows 500
    python tool/data/mock-data-generator.py --schema-file schemas/orders.json --rows 1000
    python tool/data/mock-data-generator.py --engine sklearn --rows 5000

Default output is ``data/sandbox/<topic>.csv``. The generated rows are synthetic
and may include PII-shaped fields so ingestion and DQ notebooks can exercise
masking and validation behavior. Never replace this with real source extracts.

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
import csv
import datetime as dt
import importlib
import json
import random
import uuid as uuid_module
from collections.abc import Iterator
from pathlib import Path
from typing import Any


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--topic", default="orders", help="Topic/source name used for the default output path")
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
        "--output",
        type=Path,
        help="CSV output path. Defaults to data/sandbox/<topic>.csv",
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

def _stdlib_value(col: dict[str, Any], index: int, rng: random.Random) -> str | int:
    ctype = col["type"].lower()
    col_name = col["name"]
    if ctype == "id":
        return index
    if ctype == "int":
        return rng.randint(int(col.get("min", 0)), int(col.get("max", 1000)))
    if ctype in ("float", "decimal"):
        decimals = int(col.get("decimals", 4))
        return f"{rng.uniform(float(col.get('min', 0.0)), float(col.get('max', 1.0))):.{decimals}f}"
    if ctype == "date":
        start = dt.date.fromisoformat(col.get("start", "2026-01-01"))
        end = dt.date.fromisoformat(col.get("end", "2026-12-31"))
        return (start + dt.timedelta(days=rng.randint(0, (end - start).days))).isoformat()
    if ctype in ("datetime", "timestamp"):
        start = dt.date.fromisoformat(col.get("start", "2026-01-01"))
        end = dt.date.fromisoformat(col.get("end", "2026-12-31"))
        seconds = rng.randint(0, (end - start).days * 86400)
        return (dt.datetime(start.year, start.month, start.day) + dt.timedelta(seconds=seconds)).isoformat()
    if ctype in ("boolean", "bool"):
        return str(rng.choice([True, False]))
    if ctype == "uuid":
        return str(uuid_module.UUID(int=rng.getrandbits(128)))
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

def _faker_value(col: dict[str, Any], index: int, fake: Any, rng: random.Random) -> str | int:
    ctype = col["type"].lower()
    if ctype == "id":
        return index
    if ctype == "int":
        return fake.random_int(min=int(col.get("min", 0)), max=int(col.get("max", 1000)))
    if ctype in ("float", "decimal"):
        decimals = int(col.get("decimals", 2))
        return f"{rng.uniform(float(col.get('min', 0.0)), float(col.get('max', 1.0))):.{decimals}f}"
    if ctype == "date":
        start = dt.date.fromisoformat(col.get("start", "2026-01-01"))
        end = dt.date.fromisoformat(col.get("end", "2026-12-31"))
        return fake.date_between(start_date=start, end_date=end).isoformat()
    if ctype in ("datetime", "timestamp"):
        return fake.date_time_between(start_date=col.get("start", "-1y"), end_date=col.get("end", "now")).isoformat()
    if ctype in ("boolean", "bool"):
        return str(fake.boolean())
    if ctype == "uuid":
        return fake.uuid4()
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

def _mimesis_value(col: dict[str, Any], index: int, generic: Any, rng: random.Random) -> str | int:
    ctype = col["type"].lower()
    col_name = col["name"]
    if ctype == "id":
        return index
    if ctype == "int":
        return rng.randint(int(col.get("min", 0)), int(col.get("max", 1000)))
    if ctype in ("float", "decimal"):
        decimals = int(col.get("decimals", 2))
        return f"{rng.uniform(float(col.get('min', 0.0)), float(col.get('max', 1.0))):.{decimals}f}"
    if ctype == "date":
        start = dt.date.fromisoformat(col.get("start", "2026-01-01"))
        end = dt.date.fromisoformat(col.get("end", "2026-12-31"))
        return (start + dt.timedelta(days=rng.randint(0, (end - start).days))).isoformat()
    if ctype in ("datetime", "timestamp"):
        start = dt.date.fromisoformat(col.get("start", "2026-01-01"))
        end = dt.date.fromisoformat(col.get("end", "2026-12-31"))
        seconds = rng.randint(0, (end - start).days * 86400)
        return (dt.datetime(start.year, start.month, start.day) + dt.timedelta(seconds=seconds)).isoformat()
    if ctype in ("boolean", "bool"):
        return str(rng.choice([True, False]))
    if ctype == "uuid":
        return str(uuid_module.UUID(int=rng.getrandbits(128)))
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
            row[col["name"]] = f"{feature_row[i]:.{int(col.get('decimals', 6))}f}"
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


def write_csv(output: Path, fieldnames: list[str], rows: Iterator[dict[str, Any]]) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
            count += 1
    return count


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.rows < 1:
        raise SystemExit("--rows must be greater than zero")
    schema = load_schema(args)
    output = args.output or Path("data") / "sandbox" / f"{args.topic}.csv"
    fieldnames, rows = build_rows(args, schema)
    count = write_csv(output, fieldnames, rows)
    print(f"Generated {count} synthetic rows at {output} using {args.engine}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
