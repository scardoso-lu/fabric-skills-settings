"""Tests for the SQLite API-key store (server/auth/repository.py)."""

from __future__ import annotations

import pytest

from server.auth.repository import (
    SqliteApiKeyStore,
    build_key_store_from_env,
)


@pytest.fixture(autouse=True)
def _clear_key_env(monkeypatch):
    for var in ("FABRIC_MCP_API_KEYS", "FABRIC_MCP_API_KEYS_DB"):
        monkeypatch.delenv(var, raising=False)


# ── SqliteApiKeyStore ─────────────────────────────────────────────────────────

def test_sqlite_store_creates_db_and_contains(tmp_path):
    db = str(tmp_path / "keys.db")
    store = SqliteApiKeyStore(db)
    assert not store
    entry = store.add("alice@example.com", "secret-key")
    assert "secret-key" in store
    assert "unknown" not in store
    assert entry["email"] == "alice@example.com"
    assert "secret-key" not in entry["masked_key"]


def test_sqlite_store_remove(tmp_path):
    db = str(tmp_path / "keys.db")
    store = SqliteApiKeyStore(db)
    entry = store.add("bob@example.com", "key-bob")
    assert store.remove(entry["id"]) is True
    assert "key-bob" not in store
    assert store.remove(entry["id"]) is False


def test_sqlite_store_list_entries_masked(tmp_path):
    db = str(tmp_path / "keys.db")
    store = SqliteApiKeyStore(db)
    store.add("carol@example.com", "12345678abcdefgh")
    entries = store.list_entries()
    assert len(entries) == 1
    assert entries[0]["email"] == "carol@example.com"
    assert "12345678abcdefgh" not in entries[0]["masked_key"]


def test_sqlite_store_readonly_keys_shown_in_list(tmp_path):
    db = str(tmp_path / "keys.db")
    store = SqliteApiKeyStore(db, readonly_keys={"env-key"})
    assert "env-key" in store
    entries = store.list_entries()
    env_entry = next((e for e in entries if e.get("readonly")), None)
    assert env_entry is not None


def test_sqlite_store_persists_across_instances(tmp_path):
    db = str(tmp_path / "keys.db")
    store1 = SqliteApiKeyStore(db)
    store1.add("dave@example.com", "persistent-key")
    store2 = SqliteApiKeyStore(db)
    assert "persistent-key" in store2


def test_sqlite_store_is_writable(tmp_path):
    store = SqliteApiKeyStore(str(tmp_path / "keys.db"))
    assert store.is_writable() is True


def test_sqlite_memory_store_is_not_writable():
    store = SqliteApiKeyStore(":memory:", readonly_keys={"envkey"})
    assert store.is_writable() is False
    assert "envkey" in store
    with pytest.raises(ValueError, match="read-only"):
        store.add("x@y.com", "newkey")


# ── build_key_store_from_env ──────────────────────────────────────────────────

def test_build_key_store_returns_none_when_not_configured():
    assert build_key_store_from_env() is None


def test_build_key_store_with_db_path(tmp_path, monkeypatch):
    db = str(tmp_path / "keys.db")
    monkeypatch.setenv("FABRIC_MCP_API_KEYS_DB", db)
    store = build_key_store_from_env()
    assert isinstance(store, SqliteApiKeyStore)
    assert store.is_writable()


def test_build_key_store_missing_db_path_but_env_keys(monkeypatch):
    monkeypatch.setenv("FABRIC_MCP_API_KEYS", "key1,key2")
    store = build_key_store_from_env()
    assert isinstance(store, SqliteApiKeyStore)
    assert not store.is_writable()
    assert "key1" in store
    assert "key2" in store


def test_build_key_store_combines_db_and_env_keys(tmp_path, monkeypatch):
    db = str(tmp_path / "keys.db")
    monkeypatch.setenv("FABRIC_MCP_API_KEYS_DB", db)
    monkeypatch.setenv("FABRIC_MCP_API_KEYS", "envkey")
    store = build_key_store_from_env()
    assert isinstance(store, SqliteApiKeyStore)
    assert "envkey" in store
    store.add("alice@example.com", "dbkey")
    assert "dbkey" in store
