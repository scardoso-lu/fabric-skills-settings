"""Regression tests for tool/data/mock-data-generator.py."""

from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATOR_PATH = ROOT / "tool" / "data" / "mock-data-generator.py"


def load_generator():
    spec = importlib.util.spec_from_file_location("mock_data_generator", GENERATOR_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ORDERS_SCHEMA = json.dumps([
    {"name": "id",          "type": "id"},
    {"name": "customer_id", "type": "int",     "min": 1,    "max": 500},
    {"name": "name",        "type": "name"},
    {"name": "email",       "type": "email"},
    {"name": "address",     "type": "address"},
    {"name": "note",        "type": "sentence"},
    {"name": "amount",      "type": "decimal", "min": 2.5,  "max": 2500.0, "decimals": 2},
    {"name": "created_at",  "type": "date",    "start": "2026-01-01", "end": "2026-06-30"},
])


def test_stdlib_engine_writes_deterministic_business_csv(tmp_path):
    generator = load_generator()
    output = tmp_path / "orders.csv"

    assert generator.main([
        "--topic", "orders", "--rows", "3", "--seed", "7",
        "--schema", ORDERS_SCHEMA, "--output", str(output),
    ]) == 0

    with output.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 3
    assert list(rows[0].keys()) == ["id", "customer_id", "name", "email", "address", "note", "amount", "created_at"]
    assert [row["id"] for row in rows] == ["1", "2", "3"]
    assert rows[0]["name"] == "User 1"
    assert rows[0]["email"] == "user.1@example.test"
    assert rows[0]["note"] == "Synthetic record 1."
    for row in rows:
        assert 1 <= int(row["customer_id"]) <= 500
        assert "." in row["amount"] and len(row["amount"].split(".")[1]) == 2
        date_parts = row["created_at"].split("-")
        assert len(date_parts) == 3 and date_parts[0] == "2026"


def test_stdlib_engine_is_deterministic_across_runs(tmp_path):
    generator = load_generator()
    out1 = tmp_path / "run1.csv"
    out2 = tmp_path / "run2.csv"

    generator.main(["--rows", "10", "--seed", "99", "--schema", ORDERS_SCHEMA, "--output", str(out1)])
    generator.main(["--rows", "10", "--seed", "99", "--schema", ORDERS_SCHEMA, "--output", str(out2)])

    assert out1.read_text() == out2.read_text()


def test_schema_flag_generates_custom_columns(tmp_path):
    generator = load_generator()
    output = tmp_path / "custom.csv"
    schema = json.dumps([
        {"name": "pk",    "type": "id"},
        {"name": "score", "type": "int", "min": 0, "max": 100},
        {"name": "label", "type": "sentence"},
    ])

    assert generator.main(["--topic", "custom", "--rows", "5", "--schema", schema, "--output", str(output)]) == 0

    with output.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 5
    assert list(rows[0].keys()) == ["pk", "score", "label"]
    assert [row["pk"] for row in rows] == ["1", "2", "3", "4", "5"]
    for row in rows:
        assert 0 <= int(row["score"]) <= 100


def test_schema_file_flag_generates_custom_columns(tmp_path):
    generator = load_generator()
    schema_file = tmp_path / "schema.json"
    schema_file.write_text(json.dumps([
        {"name": "id",   "type": "id"},
        {"name": "code", "type": "uuid"},
        {"name": "ts",   "type": "date", "start": "2025-01-01", "end": "2025-12-31"},
    ]))
    output = tmp_path / "out.csv"

    assert generator.main(["--schema-file", str(schema_file), "--rows", "4", "--output", str(output)]) == 0

    with output.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 4
    assert list(rows[0].keys()) == ["id", "code", "ts"]
    for row in rows:
        assert row["ts"].startswith("2025-")


def test_missing_schema_exits_with_message(tmp_path, capsys):
    generator = load_generator()
    output = tmp_path / "out.csv"

    try:
        generator.main(["--rows", "5", "--output", str(output)])
        assert False, "expected SystemExit"
    except SystemExit as exc:
        assert "schema" in str(exc).lower()


import pytest

ML_SCHEMA = json.dumps([
    {"name": "id",       "type": "id"},
    {"name": "price",    "type": "float", "decimals": 4},
    {"name": "quantity", "type": "float", "decimals": 4},
    {"name": "target",   "type": "int"},
])

@pytest.mark.skipif(
    importlib.util.find_spec("sklearn") is None,
    reason="scikit-learn not installed",
)
def test_sklearn_engine_generates_expected_columns(tmp_path):
    generator = load_generator()
    output = tmp_path / "ml.csv"

    assert generator.main([
        "--engine", "sklearn", "--rows", "5",
        "--schema", ML_SCHEMA, "--output", str(output),
    ]) == 0

    with output.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert len(rows) == 5
    assert list(rows[0].keys()) == ["id", "price", "quantity", "target"]
    for row in rows:
        assert row["target"] in ("0", "1")
