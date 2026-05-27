"""FastMCP app builder.

The server exposes graph, content, validate, data, and semantic-model
(uses sempy.fabric python lib). Fabric-CLI-dependent helpers plus the
deterministic lints and pre-commit aggregator live in cli/ and run on the
user's laptop as plain CLI commands (Claude invokes them via Bash).
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

import jwt  # PyJWT
from mcp.server.fastmcp import FastMCP
from starlette.middleware.cors import CORSMiddleware

from .tools.data import tools as data_tools
from .tools.graph import tools as graph_tools
from .tools.semantic_model import tools as semantic_model_tools
from .tools.validate import tools as validate_tools

_JWT_ALGORITHM = "HS256"
_JWT_EXPIRY_SECONDS = 3600  # 1 hour
_LOGIN_PATH = "/auth/login"
_REFRESH_PATH = "/auth/refresh"


def _load_api_keys() -> set[str]:
    """Load valid API keys from FABRIC_MCP_API_KEYS (comma-sep) or FABRIC_MCP_API_KEYS_FILE."""
    keys: set[str] = set()
    env_val = os.environ.get("FABRIC_MCP_API_KEYS", "").strip()
    if env_val:
        for k in env_val.split(","):
            k = k.strip()
            if k:
                keys.add(k)
    file_path = os.environ.get("FABRIC_MCP_API_KEYS_FILE", "").strip()
    if file_path:
        p = Path(file_path)
        if p.is_file():
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    keys.add(line)
    return keys


def _jwt_secret() -> str:
    return os.environ.get("FABRIC_MCP_JWT_SECRET", "").strip()


def _resource_server_url() -> str:
    configured = os.environ.get("MCP_SERVER_URL", "").strip().rstrip("/")
    if configured:
        return configured
    host = os.environ.get("HOST", "127.0.0.1").strip() or "127.0.0.1"
    port = os.environ.get("PORT", "8000").strip() or "8000"
    public_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    return f"http://{public_host}:{port}"


class JtiStore:
    """Track issued JTIs to prevent replay of revoked or forged tokens."""

    def __init__(self) -> None:
        self._store: dict[str, float] = {}  # jti -> expiry (unix timestamp)

    def issue(self, jti: str, expiry: float) -> None:
        self._store[jti] = expiry
        self._purge()

    def revoke(self, jti: str) -> None:
        self._store.pop(jti, None)

    def is_valid(self, jti: str) -> bool:
        exp = self._store.get(jti)
        return exp is not None and time.time() < exp

    def _purge(self) -> None:
        now = time.time()
        stale = [j for j, e in self._store.items() if e <= now]
        for j in stale:
            del self._store[j]


def _mint_jwt(sub: str, secret: str, jti_store: JtiStore) -> tuple[str, float]:
    """Return (encoded_jwt, expires_at_unix_timestamp)."""
    jti = str(uuid.uuid4())
    now = time.time()
    expiry = now + _JWT_EXPIRY_SECONDS
    payload = {
        "sub": sub,
        "jti": jti,
        "iat": now,
        "exp": expiry,
        "iss": "fabric-mcp-server",
    }
    token = jwt.encode(payload, secret, algorithm=_JWT_ALGORITHM)
    jti_store.issue(jti, expiry)
    return token, expiry


def _decode_jwt(token: str, secret: str, jti_store: JtiStore) -> dict | None:
    """Return the verified payload dict, or None if invalid / expired / replayed."""
    try:
        payload = jwt.decode(token, secret, algorithms=[_JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
    jti = payload.get("jti", "")
    if not jti_store.is_valid(jti):
        return None
    return payload


async def _read_body(receive, max_bytes: int = 16_384) -> bytes:
    body = b""
    while True:
        event = await receive()
        if event["type"] == "http.request":
            body += event.get("body", b"")
            if len(body) > max_bytes:
                raise ValueError("request body too large")
            if not event.get("more_body", False):
                break
        elif event["type"] == "http.disconnect":
            break
    return body


async def _send_json(send, data: dict, status: int) -> None:
    body = json.dumps(data).encode("utf-8")
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode()),
        ],
    })
    await send({"type": "http.response.body", "body": body})


class FabricAuthMiddleware:
    """Pure-ASGI middleware: handles /auth/login, /auth/refresh, and JWT validation.

    All non-auth paths require Authorization: Bearer <jwt>. The JWT is obtained
    by POSTing {"api_key": "..."} to /auth/login. Refresh via POST /auth/refresh
    with the current token in the Authorization header — the old JTI is revoked,
    preventing replay of the superseded token.
    """

    def __init__(self, app, *, api_keys: set[str], secret: str, jti_store: JtiStore) -> None:
        self.app = app
        self._api_keys = api_keys
        self._secret = secret
        self._jti_store = jti_store

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        if scope["type"] == "http":
            path = scope.get("path", "")
            if path == _LOGIN_PATH:
                await self._login(receive, send)
                return
            if path == _REFRESH_PATH:
                await self._refresh(scope, receive, send)
                return

        token = self._extract_token(scope)
        if not token:
            if scope["type"] == "http":
                await _send_json(send, {"error": "missing_token"}, 401)
            return

        payload = _decode_jwt(token, self._secret, self._jti_store)
        if payload is None:
            if scope["type"] == "http":
                await _send_json(send, {"error": "invalid_token"}, 401)
            return

        await self.app(scope, receive, send)

    async def _login(self, receive, send) -> None:
        try:
            body = await _read_body(receive)
            data = json.loads(body)
        except (ValueError, json.JSONDecodeError):
            await _send_json(send, {"error": "invalid_request"}, 400)
            return
        api_key = data.get("api_key", "")
        if not api_key or api_key not in self._api_keys:
            await _send_json(send, {"error": "invalid_api_key"}, 401)
            return
        token, expiry = _mint_jwt("client", self._secret, self._jti_store)
        await _send_json(send, {"token": token, "expires_at": expiry, "token_type": "Bearer"}, 200)

    async def _refresh(self, scope, receive, send) -> None:
        await _read_body(receive)  # consume body to keep ASGI lifecycle clean
        old_token = self._extract_token(scope)
        if not old_token:
            await _send_json(send, {"error": "missing_token"}, 401)
            return
        old_payload = _decode_jwt(old_token, self._secret, self._jti_store)
        if old_payload is None:
            await _send_json(send, {"error": "invalid_token"}, 401)
            return
        self._jti_store.revoke(old_payload["jti"])
        token, expiry = _mint_jwt(old_payload.get("sub", "client"), self._secret, self._jti_store)
        await _send_json(send, {"token": token, "expires_at": expiry, "token_type": "Bearer"}, 200)

    @staticmethod
    def _extract_token(scope) -> str | None:
        headers = {k.lower(): v for k, v in scope.get("headers", [])}
        auth = headers.get(b"authorization", b"").decode("utf-8", errors="replace")
        if auth.startswith("Bearer ") and len(auth) > 7:
            return auth[7:]
        return None


def build_app():
    """Construct the FastMCP app, register every tool, return the ASGI app.

    Auth is enabled when FABRIC_MCP_API_KEYS_FILE or FABRIC_MCP_API_KEYS contains
    at least one valid API key. Clients call POST /auth/login with {"api_key": "..."}
    to receive a 1-hour JWT. The JWT must be presented as Authorization: Bearer <token>
    on every subsequent request. Clients refresh via POST /auth/refresh (old JTI is
    revoked, blocking replay of the superseded token). When no API keys are configured
    the server accepts all requests — suitable for local single-user dev.
    """
    mcp = FastMCP("fabric-server")
    graph_tools.register(mcp)
    semantic_model_tools.register(mcp)
    validate_tools.register(mcp)
    data_tools.register(mcp)

    app = mcp.streamable_http_app()

    api_keys = _load_api_keys()
    if api_keys:
        secret = _jwt_secret()
        if not secret:
            raise RuntimeError(
                "FABRIC_MCP_JWT_SECRET must be set when API key auth is enabled. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        jti_store = JtiStore()
        # FabricAuthMiddleware added first (inner); CORSMiddleware added last (outermost).
        app.add_middleware(
            FabricAuthMiddleware,
            api_keys=api_keys,
            secret=secret,
            jti_store=jti_store,
        )

    origins_raw = os.environ.get("FABRIC_CORS_ORIGINS", "*").strip()
    allow_origins = [o.strip() for o in origins_raw.split(",") if o.strip()] or ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["Mcp-Session-Id"],
    )
    return app
