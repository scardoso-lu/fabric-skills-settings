"""PostgreSQL-backed API key store for the Fabric MCP server.

API keys are stored in a PostgreSQL database (SQLAlchemy + psycopg2).

Required env vars when auth is enabled:
  DATABASE_URL=postgresql://user:pass@host:5432/fabric   PostgreSQL DSN

Optional:
  FABRIC_MCP_API_KEYS=key1,key2,...   comma-separated read-only keys
                                       (in-memory; useful for single-user dev)

Auth is disabled entirely when neither variable is set.
"""

from __future__ import annotations

import logging
import os
import uuid

logger = logging.getLogger(__name__)

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


class MemoryKeyStore:
    """Read-only in-memory key store for FABRIC_MCP_API_KEYS-only deployments."""

    def __init__(self, readonly_keys: set[str]) -> None:
        self._readonly_keys = readonly_keys

    def __contains__(self, key: str) -> bool:
        return key in self._readonly_keys

    def __bool__(self) -> bool:
        return bool(self._readonly_keys)

    def __len__(self) -> int:
        return len(self._readonly_keys)

    def is_writable(self) -> bool:
        return False

    def list_entries(self) -> list[dict]:
        return [{
            "id": None,
            "email": "(environment)",
            "masked_key": f"+{len(self._readonly_keys)} key(s) from FABRIC_MCP_API_KEYS",
            "readonly": True,
        }]

    def add(self, email: str, key: str) -> dict:
        raise ValueError("Key store is read-only (in-memory mode — set DATABASE_URL)")

    def remove(self, entry_id: str) -> bool:
        raise ValueError("Key store is read-only (in-memory mode — set DATABASE_URL)")


class ApiKeyStore:
    """PostgreSQL-backed API key store via SQLAlchemy ORM.

    ``DATABASE_URL=postgresql://user:pass@host:5432/fabric``
    """

    def __init__(self, dsn: str, readonly_keys: set[str] | None = None) -> None:
        if not _SA_AVAILABLE:
            raise RuntimeError(
                "PostgreSQL key store requires SQLAlchemy and psycopg2. "
                "Install: pip install 'sqlalchemy>=2.0' psycopg2-binary"
            )
        self._readonly_keys: set[str] = readonly_keys or set()
        self._dsn = dsn

        try:
            self._engine = _sa_create_engine(dsn, pool_pre_ping=True)
            _SaBase.metadata.create_all(self._engine)
        except Exception as exc:
            safe_dsn = dsn.split("@")[-1] if "@" in dsn else dsn
            raise RuntimeError(
                f"Cannot connect to PostgreSQL ({safe_dsn}): {exc}\n"
                "Ensure DATABASE_URL is set to a valid PostgreSQL connection string.\n"
                "Example: postgresql://user:password@postgres:5432/fabric"
            ) from exc

        logger.info(
            "PostgreSQL API key store connected (%s, %d row(s))",
            dsn.split("@")[-1] if "@" in dsn else dsn,
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


# backward-compat alias so existing imports still resolve
SqliteApiKeyStore = ApiKeyStore


# ── Factory ────────────────────────────────────────────────────────────────────

def build_key_store_from_env() -> ApiKeyStore | MemoryKeyStore | None:
    """Build the key store from environment variables.

    Resolution:
      - ``DATABASE_URL`` → PostgreSQL (writable CRUD).
      - ``FABRIC_MCP_API_KEYS`` → comma-separated inline keys, added as read-only
        entries on top of the database (or as the sole store when no DATABASE_URL).
      - If neither is set → returns ``None`` (auth disabled, local dev mode).
    """
    dsn = os.environ.get("DATABASE_URL", "").strip()
    env_keys = {k.strip() for k in os.environ.get("FABRIC_MCP_API_KEYS", "").split(",") if k.strip()}

    if not dsn and not env_keys:
        return None

    if not dsn:
        logger.info(
            "FABRIC_MCP_API_KEYS set but no DATABASE_URL — "
            "using in-memory key store (no CRUD, keys lost on restart)"
        )
        return MemoryKeyStore(env_keys)

    return ApiKeyStore(dsn, readonly_keys=env_keys or None)


# ── Module-level store singleton ───────────────────────────────────────────────

_current_store: ApiKeyStore | MemoryKeyStore | None = None


def get_store() -> ApiKeyStore | MemoryKeyStore | None:
    return _current_store


def _set_store(store: ApiKeyStore | MemoryKeyStore | None) -> None:
    global _current_store
    _current_store = store
