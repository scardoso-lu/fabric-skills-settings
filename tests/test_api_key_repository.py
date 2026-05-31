"""Tests for the pluggable API-key repository (server/auth/repository.py)."""

from __future__ import annotations

import pytest

from server.auth.repository import (
    AzureBlobApiKeyRepository,
    CompositeApiKeyRepository,
    EnvVarApiKeyRepository,
    LocalFileApiKeyRepository,
    MutableApiKeyStore,
    SqliteApiKeyStore,
    build_api_key_repository,
    build_csv_api_key_repository,
    build_key_store_from_env,
    load_api_keys,
    parse_api_keys_csv,
)

_CSV = "email,apikey\nalice@example.com,keyA\nbob@example.com,keyB\n"


@pytest.fixture(autouse=True)
def _clear_source_env(monkeypatch):
    """Each test starts from a clean key-source environment."""
    for var in (
        "FABRIC_MCP_API_KEYS",
        "FABRIC_MCP_API_KEYS_SOURCE",
        "FABRIC_MCP_API_KEYS_FILE",
        "FABRIC_MCP_API_KEYS_BLOB_CONTAINER",
        "FABRIC_MCP_API_KEYS_BLOB_NAME",
        "FABRIC_MCP_API_KEYS_BLOB_CONNECTION_STRING",
        "FABRIC_MCP_API_KEYS_BLOB_ACCOUNT_URL",
    ):
        monkeypatch.delenv(var, raising=False)


# ── parse_api_keys_csv ──────────────────────────────────────────────────────

def test_parse_csv_extracts_apikey_column():
    assert parse_api_keys_csv(_CSV) == {"keyA", "keyB"}


def test_parse_csv_tolerates_header_whitespace_and_blank_keys():
    text = "email, apikey\nalice@example.com, keyA \nno-key@example.com,\nbob@example.com,keyB\n"
    assert parse_api_keys_csv(text) == {"keyA", "keyB"}


def test_parse_csv_empty_or_header_only():
    assert parse_api_keys_csv("") == set()
    assert parse_api_keys_csv("email,apikey\n") == set()


# ── LocalFileApiKeyRepository ───────────────────────────────────────────────

def test_local_file_repository_reads_keys(tmp_path):
    f = tmp_path / "api-keys.csv"
    f.write_text(_CSV, encoding="utf-8")
    repo = LocalFileApiKeyRepository(f)
    assert repo.load_keys() == {"keyA", "keyB"}


def test_local_file_repository_missing_file_yields_empty(tmp_path):
    repo = LocalFileApiKeyRepository(tmp_path / "does-not-exist.csv")
    assert repo.fetch_csv() is None
    assert repo.load_keys() == set()


# ── AzureBlobApiKeyRepository ───────────────────────────────────────────────

class _FakeDownloader:
    def __init__(self, data):
        self._data = data

    def readall(self):
        return self._data


class _FakeBlobClient:
    def __init__(self, data=None, *, raise_not_found=False):
        self._data = data
        self._raise_not_found = raise_not_found

    def download_blob(self):
        if self._raise_not_found:
            from azure.core.exceptions import ResourceNotFoundError

            raise ResourceNotFoundError("missing")
        return _FakeDownloader(self._data)


def test_azure_repository_decodes_blob_bytes():
    repo = AzureBlobApiKeyRepository(
        container="c", blob="api-keys.csv",
        blob_client=_FakeBlobClient(_CSV.encode("utf-8")),
    )
    assert repo.load_keys() == {"keyA", "keyB"}


def test_azure_repository_accepts_str_payload():
    repo = AzureBlobApiKeyRepository(
        container="c", blob="b", blob_client=_FakeBlobClient(_CSV),
    )
    assert repo.fetch_csv() == _CSV


def test_azure_repository_missing_blob_yields_empty():
    pytest.importorskip("azure.core.exceptions")
    repo = AzureBlobApiKeyRepository(
        container="c", blob="b",
        blob_client=_FakeBlobClient(raise_not_found=True),
    )
    assert repo.load_keys() == set()


def test_azure_repository_requires_container_and_blob():
    with pytest.raises(ValueError):
        AzureBlobApiKeyRepository(container="", blob="b", connection_string="cs")


def test_azure_repository_requires_some_auth():
    with pytest.raises(ValueError):
        AzureBlobApiKeyRepository(container="c", blob="b")


# ── EnvVarApiKeyRepository ───────────────────────────────────────────────────

def test_env_var_repository_splits_and_strips():
    repo = EnvVarApiKeyRepository("key1, key2 , key3")
    assert repo.load_keys() == {"key1", "key2", "key3"}


def test_env_var_repository_empty():
    assert EnvVarApiKeyRepository("").load_keys() == set()


# ── CompositeApiKeyRepository ────────────────────────────────────────────────

def test_composite_unions_keys(tmp_path):
    f = tmp_path / "api-keys.csv"
    f.write_text(_CSV, encoding="utf-8")
    composite = CompositeApiKeyRepository(
        [EnvVarApiKeyRepository("env1,env2"), LocalFileApiKeyRepository(f)]
    )
    assert composite.load_keys() == {"env1", "env2", "keyA", "keyB"}


def test_composite_empty_when_no_repositories():
    assert CompositeApiKeyRepository([]).load_keys() == set()


# ── build_csv_api_key_repository (source selector) ───────────────────────────

def test_csv_factory_defaults_to_file_source(tmp_path, monkeypatch):
    f = tmp_path / "api-keys.csv"
    f.write_text(_CSV, encoding="utf-8")
    monkeypatch.setenv("FABRIC_MCP_API_KEYS_FILE", str(f))
    repo = build_csv_api_key_repository()
    assert isinstance(repo, LocalFileApiKeyRepository)
    assert repo.load_keys() == {"keyA", "keyB"}


def test_csv_factory_file_source_without_path_returns_none(monkeypatch):
    monkeypatch.setenv("FABRIC_MCP_API_KEYS_SOURCE", "file")
    assert build_csv_api_key_repository() is None


def test_csv_factory_builds_azure_repository_with_connection_string(monkeypatch):
    monkeypatch.setenv("FABRIC_MCP_API_KEYS_SOURCE", "azure-blob")
    monkeypatch.setenv("FABRIC_MCP_API_KEYS_BLOB_CONTAINER", "keys")
    monkeypatch.setenv("FABRIC_MCP_API_KEYS_BLOB_NAME", "api-keys.csv")
    monkeypatch.setenv("FABRIC_MCP_API_KEYS_BLOB_CONNECTION_STRING", "UseDevelopmentStorage=true")
    repo = build_csv_api_key_repository()
    assert isinstance(repo, AzureBlobApiKeyRepository)


def test_csv_factory_builds_azure_repository_with_account_url(monkeypatch):
    monkeypatch.setenv("FABRIC_MCP_API_KEYS_SOURCE", "azure-blob")
    monkeypatch.setenv("FABRIC_MCP_API_KEYS_BLOB_CONTAINER", "keys")
    monkeypatch.setenv("FABRIC_MCP_API_KEYS_BLOB_NAME", "api-keys.csv")
    monkeypatch.setenv("FABRIC_MCP_API_KEYS_BLOB_ACCOUNT_URL", "https://acct.blob.core.windows.net")
    repo = build_csv_api_key_repository()
    assert isinstance(repo, AzureBlobApiKeyRepository)


def test_csv_factory_azure_missing_container_raises(monkeypatch):
    monkeypatch.setenv("FABRIC_MCP_API_KEYS_SOURCE", "azure-blob")
    monkeypatch.setenv("FABRIC_MCP_API_KEYS_BLOB_NAME", "api-keys.csv")
    monkeypatch.setenv("FABRIC_MCP_API_KEYS_BLOB_CONNECTION_STRING", "cs")
    with pytest.raises(RuntimeError, match="CONTAINER"):
        build_csv_api_key_repository()


def test_csv_factory_azure_missing_auth_raises(monkeypatch):
    monkeypatch.setenv("FABRIC_MCP_API_KEYS_SOURCE", "azure-blob")
    monkeypatch.setenv("FABRIC_MCP_API_KEYS_BLOB_CONTAINER", "keys")
    monkeypatch.setenv("FABRIC_MCP_API_KEYS_BLOB_NAME", "api-keys.csv")
    with pytest.raises(RuntimeError, match="CONNECTION_STRING"):
        build_csv_api_key_repository()


def test_csv_factory_unknown_source_raises(monkeypatch):
    monkeypatch.setenv("FABRIC_MCP_API_KEYS_SOURCE", "ftp")
    with pytest.raises(RuntimeError, match="Unknown"):
        build_csv_api_key_repository()


# ── build_api_key_repository / load_api_keys (composed entry point) ──────────

def test_load_api_keys_from_env_only(monkeypatch):
    monkeypatch.setenv("FABRIC_MCP_API_KEYS", "key1, key2 , key3")
    assert load_api_keys() == {"key1", "key2", "key3"}


def test_load_api_keys_from_csv_file_only(tmp_path, monkeypatch):
    f = tmp_path / "api-keys.csv"
    f.write_text(_CSV, encoding="utf-8")
    monkeypatch.setenv("FABRIC_MCP_API_KEYS_FILE", str(f))
    assert load_api_keys() == {"keyA", "keyB"}


def test_load_api_keys_combines_env_and_file(tmp_path, monkeypatch):
    f = tmp_path / "api-keys.csv"
    f.write_text(_CSV, encoding="utf-8")
    monkeypatch.setenv("FABRIC_MCP_API_KEYS", "envkey")
    monkeypatch.setenv("FABRIC_MCP_API_KEYS_FILE", str(f))
    assert load_api_keys() == {"envkey", "keyA", "keyB"}


def test_load_api_keys_empty_when_not_configured():
    assert load_api_keys() == set()


def test_build_api_key_repository_returns_composite():
    assert isinstance(build_api_key_repository(), CompositeApiKeyRepository)


# ── MutableApiKeyStore.from_env — security boundary tests ────────────────────

def test_mutable_store_unknown_source_raises(monkeypatch):
    """Unknown FABRIC_MCP_API_KEYS_SOURCE must raise, not silently disable auth."""
    monkeypatch.setenv("FABRIC_MCP_API_KEYS_SOURCE", "ftp")
    with pytest.raises(RuntimeError, match="Unknown"):
        MutableApiKeyStore.from_env()


def test_mutable_store_azure_missing_config_raises(monkeypatch):
    """Misconfigured Azure source must raise, not silently return an empty store."""
    monkeypatch.setenv("FABRIC_MCP_API_KEYS_SOURCE", "azure-blob")
    monkeypatch.setenv("FABRIC_MCP_API_KEYS_BLOB_NAME", "api-keys.csv")
    monkeypatch.setenv("FABRIC_MCP_API_KEYS_BLOB_CONNECTION_STRING", "cs")
    # Missing container — build_csv_api_key_repository raises; must propagate.
    with pytest.raises(RuntimeError, match="CONTAINER"):
        MutableApiKeyStore.from_env()


def test_mutable_store_file_loads_and_contains(tmp_path, monkeypatch):
    f = tmp_path / "api-keys.csv"
    f.write_text(_CSV, encoding="utf-8")
    monkeypatch.setenv("FABRIC_MCP_API_KEYS_FILE", str(f))
    store = MutableApiKeyStore.from_env()
    assert bool(store)
    assert "keyA" in store
    assert "keyB" in store
    assert "unknown" not in store


def test_mutable_store_add_and_remove(tmp_path, monkeypatch):
    f = tmp_path / "api-keys.csv"
    f.write_text(_CSV, encoding="utf-8")
    monkeypatch.setenv("FABRIC_MCP_API_KEYS_FILE", str(f))
    store = MutableApiKeyStore.from_env()

    entry = store.add("carol@example.com", "keyC")
    assert "keyC" in store
    assert entry["email"] == "carol@example.com"
    assert "keyC" not in entry["masked_key"]  # key must be masked

    assert store.remove(entry["id"]) is True
    assert "keyC" not in store
    assert store.remove(entry["id"]) is False  # already gone


def test_mutable_store_env_only_is_not_writable(monkeypatch):
    monkeypatch.setenv("FABRIC_MCP_API_KEYS", "envkey")
    store = MutableApiKeyStore.from_env()
    assert "envkey" in store
    assert not store.is_writable()
    with pytest.raises(ValueError, match="writable"):
        store.add("x@y.com", "newkey")


# ── SqliteApiKeyStore ─────────────────────────────────────────────────────────

def test_sqlite_store_creates_db_and_contains(tmp_path):
    db = str(tmp_path / "keys.db")
    store = SqliteApiKeyStore(db)
    assert not store  # empty
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
    assert store.remove(entry["id"]) is False  # idempotent


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

    store2 = SqliteApiKeyStore(db)  # new instance, same file
    assert "persistent-key" in store2


def test_sqlite_store_missing_db_path_raises(monkeypatch):
    monkeypatch.setenv("FABRIC_MCP_API_KEYS_SOURCE", "sqlite")
    monkeypatch.delenv("FABRIC_MCP_API_KEYS_DB", raising=False)
    with pytest.raises(RuntimeError, match="FABRIC_MCP_API_KEYS_DB"):
        build_key_store_from_env()


def test_sqlite_store_from_env(tmp_path, monkeypatch):
    db = str(tmp_path / "keys.db")
    monkeypatch.setenv("FABRIC_MCP_API_KEYS_SOURCE", "sqlite")
    monkeypatch.setenv("FABRIC_MCP_API_KEYS_DB", db)
    store = build_key_store_from_env()
    assert isinstance(store, SqliteApiKeyStore)
    assert store.is_writable()


def test_build_key_store_from_env_falls_back_to_file(tmp_path, monkeypatch):
    f = tmp_path / "api-keys.csv"
    f.write_text(_CSV, encoding="utf-8")
    monkeypatch.setenv("FABRIC_MCP_API_KEYS_FILE", str(f))
    # No FABRIC_MCP_API_KEYS_SOURCE set → file mode → MutableApiKeyStore
    store = build_key_store_from_env()
    assert isinstance(store, MutableApiKeyStore)
    assert "keyA" in store
