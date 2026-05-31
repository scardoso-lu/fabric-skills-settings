"""Repository pattern for loading MCP API keys from a pluggable backend.

The set of valid API keys lives in a persistent store chosen at deploy time via
the ``FABRIC_MCP_API_KEYS_SOURCE`` environment variable:

  - ``sqlite``     — **recommended** — SQLite database at ``FABRIC_MCP_API_KEYS_DB``.
                     No file-permission issues; atomic writes; works out of the box
                     when the db file's directory is volume-mounted into the container.
  - ``file``       — CSV at ``FABRIC_MCP_API_KEYS_FILE`` (``email,apikey`` or
                     ``id,email,apikey``). Default when the variable is unset.
  - ``azure-blob`` — download from Azure Blob Storage (read-only CRUD).

In addition, ``FABRIC_MCP_API_KEYS`` (comma-separated) is always honored as an
inline source on top of any backend.

The live stores (:class:`SqliteApiKeyStore`, :class:`MutableApiKeyStore`) implement
the same duck-typed interface and are used by the auth middleware and the admin REST
API — both react to changes immediately without a restart.

Azure mode needs the optional ``azure-storage-blob`` / ``azure-identity`` packages
(``server-azure`` extra). SQLite mode needs ``sqlalchemy>=2.0``. Both are lazy so
the default file-mode image stays lean.
"""

from __future__ import annotations

import csv
import io
import logging
import os
import threading
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

logger = logging.getLogger(__name__)

# Accepted spellings for the source selector, normalized to the canonical name.
_FILE_ALIASES = {"", "file", "local", "disk", "filesystem"}
_AZURE_BLOB_ALIASES = {"azure-blob", "azure_blob", "azureblob", "blob", "azure"}
_SQLITE_ALIASES = {"sqlite", "database", "db"}

# ── SQLAlchemy: lazy module-level import so file-mode stays dep-free ──────────
try:
    from sqlalchemy import Column, String
    from sqlalchemy import create_engine as _sa_create_engine
    from sqlalchemy.orm import DeclarativeBase as _SaDeclarativeBase
    from sqlalchemy.orm import Session as _SaSession

    class _SaBase(_SaDeclarativeBase):  # type: ignore[valid-b]
        pass

    class _KeyRow(_SaBase):
        __tablename__ = "api_keys"
        id = Column(String, primary_key=True)
        email = Column(String, nullable=False, default="")
        key = Column(String, nullable=False, unique=True)

    _SA_AVAILABLE = True
except ImportError:  # pragma: no cover
    _SA_AVAILABLE = False
    _SaSession = None  # type: ignore[assignment,misc]
    _sa_create_engine = None  # type: ignore[assignment]
    _KeyRow = None  # type: ignore[assignment,misc]


def parse_api_keys_csv(text: str) -> set[str]:
    """Parse an ``email,apikey`` CSV into the set of API keys.

    Only the ``apikey`` column is used. Header names are matched
    case-insensitively and tolerate surrounding whitespace; blank key cells are
    skipped.
    """
    keys: set[str] = set()
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        key = next(
            (
                (value or "").strip()
                for name, value in row.items()
                if name and name.strip().lower() == "apikey"
            ),
            "",
        )
        if key:
            keys.add(key)
    return keys


def _parse_entries_csv(text: str) -> tuple[list[dict], bool]:
    """Parse CSV to entry dicts, handling both ``email,apikey`` and ``id,email,apikey``.

    Returns ``(entries, migrated)`` where ``migrated`` is True when UUIDs were
    generated (old format without ``id`` column), signalling the caller to
    write back the canonical three-column format.
    """
    entries: list[dict] = []
    migrated = False
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return [], False
    headers = {(h.strip().lower() if h else "") for h in reader.fieldnames}
    for row in reader:
        normalized = {(k.strip().lower() if k else ""): (v or "").strip() for k, v in row.items()}
        key = normalized.get("apikey", "")
        if not key:
            continue
        email = normalized.get("email", "")
        entry_id = normalized.get("id", "")
        if not entry_id:
            entry_id = str(uuid.uuid4())
            migrated = True
        entries.append({"id": entry_id, "email": email, "key": key})
    return entries, migrated


def _mask_key(key: str) -> str:
    """Return a display-safe masked version of an API key."""
    if len(key) <= 8:
        return "****"
    return key[:4] + "****" + key[-4:]


# ── SQLite store ─────────────────────────────────────────────────────────────

class SqliteApiKeyStore:
    """SQLite-backed API key store via SQLAlchemy ORM.

    Recommended for production: no CSV file-permission headaches, atomic
    writes, and proper transactions. The database file is created automatically
    on first startup. Mount the parent directory as a Docker volume so it
    persists across container restarts.

    ``FABRIC_MCP_API_KEYS_SOURCE=sqlite``
    ``FABRIC_MCP_API_KEYS_DB=/config/api-keys.db``
    """

    def __init__(self, db_path: str, readonly_keys: set[str] | None = None) -> None:
        if not _SA_AVAILABLE:
            raise RuntimeError(
                "SQLite key store requires SQLAlchemy. "
                "Add it to the server image: pip install 'sqlalchemy>=2.0'"
            )
        self._readonly_keys: set[str] = readonly_keys or set()
        self._db_path = db_path
        self._engine = _sa_create_engine(
            f"sqlite:///{db_path}",
            connect_args={"check_same_thread": False},
        )
        _SaBase.metadata.create_all(self._engine)
        logger.info(
            "SQLite API key store at %s (%d row(s))",
            db_path,
            self._db_count(),
        )
        if self._readonly_keys:
            logger.info(
                "  + %d key(s) from FABRIC_MCP_API_KEYS",
                len(self._readonly_keys),
            )

    def _db_count(self) -> int:
        with _SaSession(self._engine) as s:
            return s.query(_KeyRow).count()

    # ── auth check ────────────────────────────────────────────────────────────

    def __contains__(self, key: str) -> bool:
        if key in self._readonly_keys:
            return True
        with _SaSession(self._engine) as s:
            return s.query(_KeyRow).filter_by(key=key).count() > 0

    def __bool__(self) -> bool:
        if self._readonly_keys:
            return True
        return self._db_count() > 0

    def __len__(self) -> int:
        return len(self._readonly_keys) + self._db_count()

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def is_writable(self) -> bool:
        return True

    def list_entries(self) -> list[dict]:
        with _SaSession(self._engine) as s:
            rows = s.query(_KeyRow).order_by(_KeyRow.email).all()
            result = [
                {"id": r.id, "email": r.email, "masked_key": _mask_key(r.key)}
                for r in rows
            ]
        if self._readonly_keys:
            result.append({
                "id": None,
                "email": "(environment)",
                "masked_key": f"+{len(self._readonly_keys)} key(s) from FABRIC_MCP_API_KEYS",
                "readonly": True,
            })
        return result

    def add(self, email: str, key: str) -> dict:
        email = email.strip()
        key = key.strip()
        if not email or not key:
            raise ValueError("email and key must not be empty")
        entry_id = str(uuid.uuid4())
        with _SaSession(self._engine) as s:
            s.add(_KeyRow(id=entry_id, email=email, key=key))
            s.commit()
        logger.info("Added API key for %s (id=%s)", email, entry_id)
        return {"id": entry_id, "email": email, "masked_key": _mask_key(key)}

    def remove(self, entry_id: str) -> bool:
        with _SaSession(self._engine) as s:
            row = s.query(_KeyRow).filter_by(id=entry_id).first()
            if row is None:
                return False
            s.delete(row)
            s.commit()
        logger.info("Removed API key id=%s", entry_id)
        return True


# ── Mutable store (used by the live auth middleware) ──────────────────────────

class MutableApiKeyStore:
    """Thread-safe, optionally file-backed API key store.

    Used by :func:`~server.auth.middleware.install_auth_middleware` so that CRUD
    operations via the admin API are visible to the auth check immediately
    (no restart needed). Only the file backend (``FABRIC_MCP_API_KEYS_FILE``)
    supports mutations; env-var and Azure Blob entries are read-only.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._file_path: str | None = None
        self._file_entries: list[dict] = []      # {id, email, key} from file
        self._readonly_keys: set[str] = set()    # from env var / Azure Blob

    @classmethod
    def from_env(cls) -> "MutableApiKeyStore":
        """Build a store from the current process environment."""
        store = cls()

        # Inline env-var source (always honored, read-only).
        env_val = os.environ.get("FABRIC_MCP_API_KEYS", "").strip()
        if env_val:
            keys = {k.strip() for k in env_val.split(",") if k.strip()}
            store._readonly_keys |= keys
            logger.info("Loaded %d API key(s) from FABRIC_MCP_API_KEYS", len(keys))

        source = os.environ.get("FABRIC_MCP_API_KEYS_SOURCE", "").strip().lower()

        if source in _FILE_ALIASES:
            file_path = os.environ.get("FABRIC_MCP_API_KEYS_FILE", "").strip()
            if file_path:
                store._file_path = file_path
                store._load_from_file()

        elif source in _AZURE_BLOB_ALIASES:
            # Azure Blob: read-only — delegate to existing repository for the key set.
            # Any RuntimeError from build_csv_api_key_repository() (missing env vars,
            # missing SDK) is re-raised so a misconfigured Azure source fails startup
            # rather than silently disabling auth.
            csv_repo = build_csv_api_key_repository()
            if csv_repo is not None:
                keys = csv_repo.load_keys()
                store._readonly_keys |= keys
                logger.info("Loaded %d API key(s) from Azure Blob Storage", len(keys))

        elif source:
            # Unknown non-empty source value — fail closed.  An empty string is
            # handled by _FILE_ALIASES above (defaults to file mode).
            raise RuntimeError(
                f"Unknown FABRIC_MCP_API_KEYS_SOURCE: {source!r} "
                "(expected 'sqlite', 'file', or 'azure-blob')."
            )

        return store

    def _load_from_file(self) -> None:
        assert self._file_path is not None
        path = Path(self._file_path)
        if not path.is_file():
            logger.warning(
                "FABRIC_MCP_API_KEYS_FILE=%s — file not found, no file keys loaded",
                self._file_path,
            )
            return
        text = path.read_text(encoding="utf-8")
        entries, migrated = _parse_entries_csv(text)
        self._file_entries = entries
        logger.info("Loaded %d API key(s) from %s", len(entries), self._file_path)
        if migrated:
            self._write_file()
            logger.info("Migrated %s to id,email,apikey format", self._file_path)

    # ── auth check ────────────────────────────────────────────────────────────

    def __contains__(self, key: str) -> bool:
        with self._lock:
            if key in self._readonly_keys:
                return True
            return any(e["key"] == key for e in self._file_entries)

    def __bool__(self) -> bool:
        with self._lock:
            return bool(self._readonly_keys) or bool(self._file_entries)

    def __len__(self) -> int:
        with self._lock:
            return len(self._readonly_keys) + len(self._file_entries)

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def is_writable(self) -> bool:
        """True when a file path is configured and mutations can be persisted."""
        return self._file_path is not None

    def list_entries(self) -> list[dict]:
        """Return all entries safe for API responses (keys are masked)."""
        with self._lock:
            result = [
                {"id": e["id"], "email": e["email"], "masked_key": _mask_key(e["key"])}
                for e in self._file_entries
            ]
            if self._readonly_keys:
                result.append({
                    "id": None,
                    "email": "(environment)",
                    "masked_key": f"+{len(self._readonly_keys)} key(s) from FABRIC_MCP_API_KEYS",
                    "readonly": True,
                })
            return result

    def add(self, email: str, key: str) -> dict:
        """Add a new entry, persist to file, return the masked entry dict."""
        if not self._file_path:
            raise ValueError("No writable key source — set FABRIC_MCP_API_KEYS_FILE to enable key management")
        email = email.strip()
        key = key.strip()
        if not email or not key:
            raise ValueError("email and key must not be empty")
        entry = {"id": str(uuid.uuid4()), "email": email, "key": key}
        with self._lock:
            self._file_entries.append(entry)
            self._write_file()
        logger.info("Added API key for %s (id=%s)", email, entry["id"])
        return {"id": entry["id"], "email": email, "masked_key": _mask_key(key)}

    def remove(self, entry_id: str) -> bool:
        """Remove an entry by ID, persist, return True if found."""
        if not self._file_path:
            raise ValueError("No writable key source — set FABRIC_MCP_API_KEYS_FILE to enable key management")
        with self._lock:
            before = len(self._file_entries)
            self._file_entries = [e for e in self._file_entries if e["id"] != entry_id]
            if len(self._file_entries) == before:
                return False
            self._write_file()
        logger.info("Removed API key id=%s", entry_id)
        return True

    def _write_file(self) -> None:
        """Rewrite the CSV file atomically (must be called with _lock held)."""
        path = Path(self._file_path)  # type: ignore[arg-type]
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["id", "email", "apikey"])
            writer.writeheader()
            for e in self._file_entries:
                writer.writerow({"id": e["id"], "email": e["email"], "apikey": e["key"]})
        tmp.replace(path)
        logger.debug("Wrote %d API key(s) to %s", len(self._file_entries), self._file_path)


# ── Factory: picks the right store from env ───────────────────────────────────

def build_key_store_from_env() -> SqliteApiKeyStore | MutableApiKeyStore:
    """Instantiate the appropriate live key store from the current environment.

    Resolution order:
      1. ``FABRIC_MCP_API_KEYS_SOURCE=sqlite`` → :class:`SqliteApiKeyStore`
         (requires ``FABRIC_MCP_API_KEYS_DB`` and ``sqlalchemy>=2.0``).
      2. Everything else → :class:`MutableApiKeyStore` (file / Azure Blob / env-var).

    ``FABRIC_MCP_API_KEYS`` env-var keys are always added as read-only entries
    on top of whichever backend is selected.
    """
    source = os.environ.get("FABRIC_MCP_API_KEYS_SOURCE", "").strip().lower()

    if source in _SQLITE_ALIASES:
        db_path = os.environ.get("FABRIC_MCP_API_KEYS_DB", "").strip()
        if not db_path:
            raise RuntimeError(
                "FABRIC_MCP_API_KEYS_SOURCE=sqlite requires FABRIC_MCP_API_KEYS_DB "
                "(e.g. FABRIC_MCP_API_KEYS_DB=/config/api-keys.db)"
            )
        env_keys = {k.strip() for k in os.environ.get("FABRIC_MCP_API_KEYS", "").split(",") if k.strip()}
        return SqliteApiKeyStore(db_path, readonly_keys=env_keys or None)

    return MutableApiKeyStore.from_env()


# ── Module-level store singleton (set by install_auth_middleware) ─────────────

_current_store: SqliteApiKeyStore | MutableApiKeyStore | None = None


def get_store() -> SqliteApiKeyStore | MutableApiKeyStore | None:
    """Return the active key store, or ``None`` if auth is disabled."""
    return _current_store


def _set_store(store: SqliteApiKeyStore | MutableApiKeyStore | None) -> None:
    global _current_store
    _current_store = store


# ── Read-only repository hierarchy (kept for backward compat + tests) ─────────

class ApiKeyRepository(ABC):
    """A source of valid MCP API keys."""

    @abstractmethod
    def load_keys(self) -> set[str]:
        """Return the set of valid API keys this source provides."""


class CsvApiKeyRepository(ApiKeyRepository):
    """Base for repositories backed by an ``email,apikey`` CSV.

    Subclasses only implement :meth:`fetch_csv`; CSV parsing lives here so the
    format stays in one place.
    """

    @abstractmethod
    def fetch_csv(self) -> str | None:
        """Return the raw CSV text, or ``None`` if the source is absent/empty."""

    def load_keys(self) -> set[str]:
        text = self.fetch_csv()
        if not text:
            return set()
        return parse_api_keys_csv(text)


class EnvVarApiKeyRepository(ApiKeyRepository):
    """Keys from a comma-separated environment value (``FABRIC_MCP_API_KEYS``)."""

    def __init__(self, raw: str) -> None:
        self._raw = raw

    def load_keys(self) -> set[str]:
        return {k.strip() for k in self._raw.split(",") if k.strip()}


class LocalFileApiKeyRepository(CsvApiKeyRepository):
    """Load the api-keys CSV from a file on the local filesystem."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self._path = Path(path)

    def fetch_csv(self) -> str | None:
        if not self._path.is_file():
            logger.warning("API keys file not found: %s", self._path)
            return None
        text = self._path.read_text(encoding="utf-8")
        logger.debug("Read API keys CSV from %s", self._path)
        return text

    def load_keys(self) -> set[str]:
        keys = super().load_keys()
        logger.info("Loaded %d API key(s) from %s", len(keys), self._path)
        return keys


class AzureBlobApiKeyRepository(CsvApiKeyRepository):
    """Load the api-keys CSV from a blob in Azure Blob Storage.

    Authentication is resolved in this order:

      1. ``connection_string`` — a storage-account connection string.
      2. ``account_url`` + :class:`~azure.identity.DefaultAzureCredential`
         (managed identity, workload identity, env credentials, …).

    A ``blob_client`` may be injected directly (primarily for tests) to bypass
    SDK construction entirely.
    """

    def __init__(
        self,
        *,
        container: str,
        blob: str,
        connection_string: str | None = None,
        account_url: str | None = None,
        blob_client=None,
    ) -> None:
        if not container or not blob:
            raise ValueError("AzureBlobApiKeyRepository requires both 'container' and 'blob'.")
        if blob_client is None and not connection_string and not account_url:
            raise ValueError(
                "AzureBlobApiKeyRepository requires a connection_string or an account_url."
            )
        self._container = container
        self._blob = blob
        self._connection_string = connection_string
        self._account_url = account_url
        self._injected_client = blob_client

    def fetch_csv(self) -> str | None:
        client = self._injected_client or self._build_blob_client()
        # Import lazily so the SDK is only required at call time.
        try:
            from azure.core.exceptions import ResourceNotFoundError
        except ImportError:  # pragma: no cover - only when SDK missing
            ResourceNotFoundError = ()  # type: ignore[assignment]
        try:
            data = client.download_blob().readall()
        except ResourceNotFoundError:
            return None
        if isinstance(data, bytes):
            return data.decode("utf-8")
        return data

    def _build_blob_client(self):
        try:
            from azure.storage.blob import BlobServiceClient
        except ImportError as exc:  # pragma: no cover - exercised via message only
            raise RuntimeError(
                "Azure Blob API-key source requires the 'azure-storage-blob' package. "
                "Install the 'server-azure' extra (pip install "
                "'fabric-vibecoding-settings[server-azure]')."
            ) from exc

        if self._connection_string:
            service = BlobServiceClient.from_connection_string(self._connection_string)
        else:
            try:
                from azure.identity import DefaultAzureCredential
            except ImportError as exc:  # pragma: no cover - exercised via message only
                raise RuntimeError(
                    "Azure Blob API-key source with account_url requires the "
                    "'azure-identity' package. Install the 'server-azure' extra."
                ) from exc
            service = BlobServiceClient(
                account_url=self._account_url, credential=DefaultAzureCredential()
            )
        return service.get_blob_client(container=self._container, blob=self._blob)


class CompositeApiKeyRepository(ApiKeyRepository):
    """Union the keys from several repositories into one set."""

    def __init__(self, repositories: list[ApiKeyRepository]) -> None:
        self._repositories = repositories

    def load_keys(self) -> set[str]:
        keys: set[str] = set()
        for repository in self._repositories:
            keys |= repository.load_keys()
        return keys


def build_csv_api_key_repository() -> CsvApiKeyRepository | None:
    """Construct the CSV-backed source selected by ``FABRIC_MCP_API_KEYS_SOURCE``.

    Returns ``None`` only for the file backend when no path is configured —
    keeping auth opt-in for local single-user dev. Misconfigured backends raise
    ``RuntimeError`` so the server fails fast at startup.
    """
    source = os.environ.get("FABRIC_MCP_API_KEYS_SOURCE", "").strip().lower()

    if source in _FILE_ALIASES:
        file_path = os.environ.get("FABRIC_MCP_API_KEYS_FILE", "").strip()
        if not file_path:
            return None
        return LocalFileApiKeyRepository(file_path)

    if source in _AZURE_BLOB_ALIASES:
        container = os.environ.get("FABRIC_MCP_API_KEYS_BLOB_CONTAINER", "").strip()
        blob = os.environ.get("FABRIC_MCP_API_KEYS_BLOB_NAME", "").strip()
        if not container or not blob:
            raise RuntimeError(
                "FABRIC_MCP_API_KEYS_SOURCE=azure-blob requires "
                "FABRIC_MCP_API_KEYS_BLOB_CONTAINER and FABRIC_MCP_API_KEYS_BLOB_NAME."
            )
        connection_string = (
            os.environ.get("FABRIC_MCP_API_KEYS_BLOB_CONNECTION_STRING", "").strip() or None
        )
        account_url = os.environ.get("FABRIC_MCP_API_KEYS_BLOB_ACCOUNT_URL", "").strip() or None
        if not connection_string and not account_url:
            raise RuntimeError(
                "FABRIC_MCP_API_KEYS_SOURCE=azure-blob requires either "
                "FABRIC_MCP_API_KEYS_BLOB_CONNECTION_STRING or "
                "FABRIC_MCP_API_KEYS_BLOB_ACCOUNT_URL (used with DefaultAzureCredential)."
            )
        return AzureBlobApiKeyRepository(
            container=container,
            blob=blob,
            connection_string=connection_string,
            account_url=account_url,
        )

    raise RuntimeError(
        f"Unknown FABRIC_MCP_API_KEYS_SOURCE: {source!r} "
        "(expected 'file' or 'azure-blob')."
    )


def build_api_key_repository() -> ApiKeyRepository:
    """Build the composite repository for every configured key source.

    Always includes the inline ``FABRIC_MCP_API_KEYS`` source (when set) plus
    the CSV backend selected by ``FABRIC_MCP_API_KEYS_SOURCE``. This is the
    single place that knows which sources exist; callers just ``load_keys()``.
    """
    repositories: list[ApiKeyRepository] = []
    env_val = os.environ.get("FABRIC_MCP_API_KEYS", "").strip()
    if env_val:
        repositories.append(EnvVarApiKeyRepository(env_val))
    csv_repository = build_csv_api_key_repository()
    if csv_repository is not None:
        repositories.append(csv_repository)
    return CompositeApiKeyRepository(repositories)


def load_api_keys() -> set[str]:
    """Load every valid API key from all configured sources.

    Single entry point for the auth layer — keeps key sourcing fully inside the
    repository module so the app/middleware stays decoupled from it.
    """
    keys = build_api_key_repository().load_keys()
    logger.info("load_api_keys: %d total key(s) across all sources", len(keys))
    return keys
