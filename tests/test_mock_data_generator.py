"""Regression tests for server/tools/data/mock-data-generator.py.

Row-generation tests run without any database. The write_postgres integration
test requires TEST_DATABASE_URL to be set.
"""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GENERATOR_PATH = ROOT / "server" / "tools" / "data" / "mock-data-generator.py"

TEST_DSN = os.environ.get("TEST_DATABASE_URL", "")
needs_db = pytest.mark.skipif(not TEST_DSN, reason="TEST_DATABASE_URL not set — skipping PostgreSQL tests")


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


def _build_rows(argv):
    generator = load_generator()
    args = generator.parse_args(argv)
    schema = generator.load_schema(args)
    _, row_iter = generator.build_rows(args, schema)
    return list(row_iter), schema


def test_stdlib_engine_generates_deterministic_rows():
    rows, _ = _build_rows(["--topic", "orders", "--rows", "3", "--seed", "7", "--schema", ORDERS_SCHEMA])
    assert len(rows) == 3
    assert list(rows[0].keys()) == ["id", "customer_id", "name", "email", "address", "note", "amount", "created_at"]
    assert [row["id"] for row in rows] == [1, 2, 3]
    assert rows[0]["name"] == "User 1"
    assert rows[0]["email"] == "user.1@example.test"
    assert rows[0]["note"] == "Synthetic record 1."
    for row in rows:
        assert 1 <= row["customer_id"] <= 500
        assert isinstance(row["amount"], float)
        import datetime
        assert isinstance(row["created_at"], datetime.date)
        assert row["created_at"].year == 2026


def test_stdlib_engine_is_deterministic_across_runs():
    rows1, _ = _build_rows(["--rows", "10", "--seed", "99", "--schema", ORDERS_SCHEMA])
    rows2, _ = _build_rows(["--rows", "10", "--seed", "99", "--schema", ORDERS_SCHEMA])
    assert rows1 == rows2


def test_schema_flag_generates_custom_columns():
    schema = json.dumps([
        {"name": "pk",    "type": "id"},
        {"name": "score", "type": "int", "min": 0, "max": 100},
        {"name": "label", "type": "sentence"},
    ])
    rows, _ = _build_rows(["--topic", "custom", "--rows", "5", "--schema", schema])
    assert len(rows) == 5
    assert list(rows[0].keys()) == ["pk", "score", "label"]
    assert [row["pk"] for row in rows] == [1, 2, 3, 4, 5]
    for row in rows:
        assert 0 <= row["score"] <= 100


def test_schema_file_flag_generates_custom_columns(tmp_path):
    schema_file = tmp_path / "schema.json"
    schema_file.write_text(json.dumps([
        {"name": "id",   "type": "id"},
        {"name": "code", "type": "uuid"},
        {"name": "ts",   "type": "date", "start": "2025-01-01", "end": "2025-12-31"},
    ]))
    rows, _ = _build_rows(["--schema-file", str(schema_file), "--rows", "4"])
    assert len(rows) == 4
    assert list(rows[0].keys()) == ["id", "code", "ts"]
    import datetime
    for row in rows:
        assert isinstance(row["ts"], datetime.date)
        assert row["ts"].year == 2025


def test_missing_schema_exits_with_message():
    generator = load_generator()
    with pytest.raises(SystemExit) as exc_info:
        generator.main(["--rows", "5", "--dsn", "postgresql://x/y"])
    assert "schema" in str(exc_info.value).lower()


@pytest.mark.skipif(
    importlib.util.find_spec("sklearn") is None,
    reason="scikit-learn not installed",
)
def test_sklearn_engine_generates_expected_columns():
    ML_SCHEMA = json.dumps([
        {"name": "id",       "type": "id"},
        {"name": "price",    "type": "float", "decimals": 4},
        {"name": "quantity", "type": "float", "decimals": 4},
        {"name": "target",   "type": "int"},
    ])
    rows, _ = _build_rows(["--engine", "sklearn", "--rows", "5", "--schema", ML_SCHEMA])
    assert len(rows) == 5
    assert list(rows[0].keys()) == ["id", "price", "quantity", "target"]
    for row in rows:
        assert row["target"] in (0, 1)


# ── PostgreSQL integration ────────────────────────────────────────────────────

@needs_db
def test_write_postgres_inserts_rows():
    import psycopg2
    generator = load_generator()
    schema_list = [
        {"name": "id",    "type": "id"},
        {"name": "email", "type": "email"},
        {"name": "score", "type": "int", "min": 0, "max": 100},
    ]
    args = generator.parse_args(["--rows", "5", "--seed", "1", "--schema", json.dumps(schema_list)])
    _, row_iter = generator.build_rows(args, schema_list)
    count = generator.write_postgres(TEST_DSN, "sandbox_test_gen", schema_list, row_iter)
    assert count == 5

    with psycopg2.connect(TEST_DSN) as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) FROM "sandbox_test_gen"')
            assert cur.fetchone()[0] == 5
            cur.execute('DROP TABLE IF EXISTS "sandbox_test_gen"')
        conn.commit()


@needs_db
def test_main_writes_to_postgres_table(monkeypatch):
    import psycopg2
    generator = load_generator()
    result = generator.main([
        "--topic", "main_test",
        "--rows", "3",
        "--seed", "42",
        "--schema", json.dumps([
            {"name": "id",    "type": "id"},
            {"name": "label", "type": "sentence"},
        ]),
        "--dsn", TEST_DSN,
    ])
    assert result == 0

    with psycopg2.connect(TEST_DSN) as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) FROM "sandbox_main_test"')
            assert cur.fetchone()[0] == 3
            cur.execute('DROP TABLE IF EXISTS "sandbox_main_test"')
        conn.commit()
