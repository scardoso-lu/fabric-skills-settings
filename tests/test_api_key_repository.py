"""Tests for the PostgreSQL API-key store (server/auth/repository.py).

DB-backed tests require a running PostgreSQL instance. Set TEST_DATABASE_URL
to a DSN (e.g. postgresql://fabric:secret@localhost:5432/fabric_test) and
those tests will run; without it they are skipped automatically.
"""

from __future__ import annotations

import os
import pytest

from server.auth.repository import (
    ApiKeyStore,
    MemoryKeyStore,
    build_key_store_from_env,
)

TEST_DSN = os.environ.get("TEST_DATABASE_URL", "")
needs_db = pytest.mark.skipif(not TEST_DSN, reason="TEST_DATABASE_URL not set — skipping PostgreSQL tests")


@pytest.fixture(autouse=True)
def _clear_key_env(monkeypatch):
    for var in ("FABRIC_MCP_API_KEYS", "DATABASE_URL"):
        monkeypatch.delenv(var, raising=False)


# ── MemoryKeyStore ────────────────────────────────────────────────────────────

def test_memory_store_contains():
    store = MemoryKeyStore({"key-a", "key-b"})
    assert "key-a" in store
    assert "key-b" in store
    assert "unknown" not in store


def test_memory_store_bool_and_len():
    assert not MemoryKeyStore(set())
    store = MemoryKeyStore({"k1", "k2"})
    assert store
    assert len(store) == 2


def test_memory_store_is_not_writable():
    store = MemoryKeyStore({"envkey"})
    assert store.is_writable() is False
    with pytest.raises(ValueError, match="read-only"):
        store.add("x@y.com", "newkey")
    with pytest.raises(ValueError, match="read-only"):
        store.remove("some-id")


def test_memory_store_list_entries():
    store = MemoryKeyStore({"k1", "k2"})
    entries = store.list_entries()
    assert len(entries) == 1
    assert entries[0]["readonly"] is True
    assert "2 key(s)" in entries[0]["masked_key"]


# ── ApiKeyStore (PostgreSQL) ──────────────────────────────────────────────────

@needs_db
def test_pg_store_creates_table_and_contains():
    store = ApiKeyStore(TEST_DSN)
    # clean slate: remove any keys left from previous runs
    for e in store.list_entries():
        if e.get("id"):
            store.remove(e["id"])

    assert not store
    entry = store.add("alice@example.com", "secret-key-pg")
    assert "secret-key-pg" in store
    assert "unknown" not in store
    assert entry["email"] == "alice@example.com"
    assert "secret-key-pg" not in entry["masked_key"]


@needs_db
def test_pg_store_remove():
    store = ApiKeyStore(TEST_DSN)
    entry = store.add("bob@example.com", "key-bob-pg")
    assert store.remove(entry["id"]) is True
    assert "key-bob-pg" not in store
    assert store.remove(entry["id"]) is False


@needs_db
def test_pg_store_list_entries_masked():
    store = ApiKeyStore(TEST_DSN)
    entry = store.add("carol@example.com", "12345678abcdefgh")
    try:
        entries = [e for e in store.list_entries() if e.get("id") == entry["id"]]
        assert len(entries) == 1
        assert entries[0]["email"] == "carol@example.com"
        assert "12345678abcdefgh" not in entries[0]["masked_key"]
    finally:
        store.remove(entry["id"])


@needs_db
def test_pg_store_readonly_keys_shown_in_list():
    store = ApiKeyStore(TEST_DSN, readonly_keys={"env-key-pg"})
    assert "env-key-pg" in store
    entries = store.list_entries()
    env_entry = next((e for e in entries if e.get("readonly")), None)
    assert env_entry is not None


@needs_db
def test_pg_store_persists_across_instances():
    store1 = ApiKeyStore(TEST_DSN)
    entry = store1.add("dave@example.com", "persistent-key-pg")
    try:
        store2 = ApiKeyStore(TEST_DSN)
        assert "persistent-key-pg" in store2
    finally:
        store1.remove(entry["id"])


@needs_db
def test_pg_store_is_writable():
    store = ApiKeyStore(TEST_DSN)
    assert store.is_writable() is True


# ── build_key_store_from_env ──────────────────────────────────────────────────

def test_build_key_store_returns_none_when_not_configured():
    assert build_key_store_from_env() is None


def test_build_key_store_missing_db_but_env_keys(monkeypatch):
    monkeypatch.setenv("FABRIC_MCP_API_KEYS", "key1,key2")
    store = build_key_store_from_env()
    assert isinstance(store, MemoryKeyStore)
    assert not store.is_writable()
    assert "key1" in store
    assert "key2" in store


@needs_db
def test_build_key_store_with_dsn(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", TEST_DSN)
    store = build_key_store_from_env()
    assert isinstance(store, ApiKeyStore)
    assert store.is_writable()


@needs_db
def test_build_key_store_combines_db_and_env_keys(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", TEST_DSN)
    monkeypatch.setenv("FABRIC_MCP_API_KEYS", "envkey-pg")
    store = build_key_store_from_env()
    assert isinstance(store, ApiKeyStore)
    assert "envkey-pg" in store
    entry = store.add("alice@example.com", "dbkey-pg")
    try:
        assert "dbkey-pg" in store
    finally:
        store.remove(entry["id"])
