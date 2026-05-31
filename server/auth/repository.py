"""SQLite-backed API key store for the Fabric MCP server.

API keys are stored in a SQLite database. The database is created automatically
on first startup. Mount the parent directory as a Docker volume so it persists
across container restarts.

Required env vars when auth is enabled:
  FABRIC_MCP_API_KEYS_DB=/config/api-keys.db   path to the SQLite database file

Optional:
  FABRIC_MCP_API_KEYS=key1,key2,...             comma-separated read-only keys
                                                 (on top of the database; useful
                                                 for single-user dev without CRUD)

Auth is disabled entirely when neither variable is set.
"""

from __future__ import annotations

import logging
import os
import uuid

logger = logging.getLogger(__name__)

# ── SQLAlchemy: lazy import so installs without it still start ─────────────────
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


def _mask_key(key: str) -> str:
    if len(key) <= 8:
        return "****"
    return key[:4] + "****" + key[-4:]


class SqliteApiKeyStore:
    """SQLite-backed API key store via SQLAlchemy ORM.

    ``FABRIC_MCP_API_KEYS_DB=/config/api-keys.db``

    Pass ``db_path=':memory:'`` for an in-memory store (dev/test). An in-memory
    store is not writable via CRUD — keys come only from ``readonly_keys``.
    """

    def __init__(self, db_path: str, readonly_keys: set[str] | None = None) -> None:
        if not _SA_AVAILABLE:
            raise RuntimeError(
                "SQLite key store requires SQLAlchemy. "
                "Install it: pip install 'sqlalchemy>=2.0'"
            )
        self._readonly_keys: set[str] = readonly_keys or set()
        self._db_path = db_path

        # Ensure the parent directory exists before SQLAlchemy tries to open
        # the file. This handles both missing directories and gives a clearer
        # error than SQLAlchemy's generic OperationalError.
        if db_path != ":memory:":
            import pathlib
            parent = pathlib.Path(db_path).parent
            try:
                parent.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                raise RuntimeError(
                    f"Cannot create SQLite key store directory {parent}: {exc}\n"
                    "Ensure the directory exists and is writable by the server process.\n"
                    "For Docker deployments: run  chown 10001:10001 ./config  on the host, "
                    "or set FABRIC_MCP_API_KEYS instead (in-memory, no CRUD)."
                ) from exc

        try:
            # In-memory SQLite: StaticPool keeps all queries on the same
            # connection so the schema created by create_all is visible to
            # subsequent queries (each new connection sees an empty DB).
            if db_path == ":memory:":
                from sqlalchemy.pool import StaticPool
                self._engine = _sa_create_engine(
                    "sqlite://",
                    connect_args={"check_same_thread": False},
                    poolclass=StaticPool,
                )
            else:
                self._engine = _sa_create_engine(
                    f"sqlite:///{db_path}",
                    connect_args={"check_same_thread": False},
                )
            _SaBase.metadata.create_all(self._engine)
        except Exception as exc:
            raise RuntimeError(
                f"Cannot open SQLite key store at {db_path!r}: {exc}\n"
                "Ensure the path is writable by the server process.\n"
                "For Docker deployments: run  chown 10001:10001 ./config  on the host, "
                "or set FABRIC_MCP_API_KEYS instead (in-memory, no CRUD)."
            ) from exc
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
        return self._db_path != ":memory:"

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
        if not self.is_writable():
            raise ValueError("Key store is read-only (in-memory mode — set FABRIC_MCP_API_KEYS_DB)")
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
        if not self.is_writable():
            raise ValueError("Key store is read-only (in-memory mode — set FABRIC_MCP_API_KEYS_DB)")
        with _SaSession(self._engine) as s:
            row = s.query(_KeyRow).filter_by(id=entry_id).first()
            if row is None:
                return False
            s.delete(row)
            s.commit()
        logger.info("Removed API key id=%s", entry_id)
        return True


# ── Factory ────────────────────────────────────────────────────────────────────

def build_key_store_from_env() -> SqliteApiKeyStore | None:
    """Build the SQLite key store from environment variables.

    Resolution:
      - ``FABRIC_MCP_API_KEYS_DB`` → path for the SQLite database (writable CRUD).
      - ``FABRIC_MCP_API_KEYS`` → comma-separated inline keys added as read-only
        entries on top of the database.
      - If neither is set → returns ``None`` (auth disabled, local dev mode).
      - If only ``FABRIC_MCP_API_KEYS`` is set (no DB) → in-memory SQLite with
        the env keys as read-only entries (no CRUD, keys lost on restart).
    """
    db_path = os.environ.get("FABRIC_MCP_API_KEYS_DB", "").strip()
    env_keys = {k.strip() for k in os.environ.get("FABRIC_MCP_API_KEYS", "").split(",") if k.strip()}

    if not db_path and not env_keys:
        return None

    if not db_path:
        logger.info(
            "FABRIC_MCP_API_KEYS set but no FABRIC_MCP_API_KEYS_DB — "
            "using in-memory key store (no CRUD, keys lost on restart)"
        )
        db_path = ":memory:"

    return SqliteApiKeyStore(db_path, readonly_keys=env_keys or None)


# ── Module-level store singleton ───────────────────────────────────────────────

_current_store: SqliteApiKeyStore | None = None


def get_store() -> SqliteApiKeyStore | None:
    return _current_store


def _set_store(store: SqliteApiKeyStore | None) -> None:
    global _current_store
    _current_store = store
