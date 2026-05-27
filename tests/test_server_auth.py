from __future__ import annotations

import asyncio
import time

import jwt
import pytest

from server.app import (
    JtiStore,
    _decode_jwt,
    _load_api_keys,
    _mint_jwt,
    _resource_server_url,
    FabricAuthMiddleware,
)

_SECRET = "test-secret-for-unit-tests-must-be-at-least-32-bytes"


# ── JtiStore ─────────────────────────────────────────────────────────────────

def test_jti_store_issue_makes_jti_valid():
    store = JtiStore()
    store.issue("abc", time.time() + 60)
    assert store.is_valid("abc") is True


def test_jti_store_revoke_removes_jti():
    store = JtiStore()
    store.issue("abc", time.time() + 60)
    store.revoke("abc")
    assert store.is_valid("abc") is False


def test_jti_store_expired_jti_is_invalid():
    store = JtiStore()
    store.issue("abc", time.time() - 1)
    assert store.is_valid("abc") is False


def test_jti_store_purges_stale_on_issue():
    store = JtiStore()
    # Directly insert a stale entry to bypass issue()'s own purge call.
    store._store["old"] = time.time() - 1
    assert "old" in store._store
    store.issue("new", time.time() + 60)
    assert "old" not in store._store


def test_jti_store_unknown_jti_is_invalid():
    store = JtiStore()
    assert store.is_valid("never-issued") is False


# ── JWT mint / decode ─────────────────────────────────────────────────────────

def test_mint_and_decode_round_trip():
    store = JtiStore()
    token, expiry = _mint_jwt("client", _SECRET, store)
    payload = _decode_jwt(token, _SECRET, store)
    assert payload is not None
    assert payload["sub"] == "client"
    assert payload["iss"] == "fabric-mcp-server"
    assert "jti" in payload
    assert expiry > time.time()


def test_decode_rejects_wrong_secret():
    store = JtiStore()
    token, _ = _mint_jwt("client", _SECRET, store)
    assert _decode_jwt(token, "wrong-secret", store) is None


def test_decode_rejects_expired_token():
    store = JtiStore()
    jti = "test-jti"
    payload = {
        "sub": "client",
        "jti": jti,
        "iat": time.time() - 7200,
        "exp": time.time() - 3600,  # already expired
        "iss": "fabric-mcp-server",
    }
    token = jwt.encode(payload, _SECRET, algorithm="HS256")
    store.issue(jti, time.time() + 60)  # JTI still in store
    assert _decode_jwt(token, _SECRET, store) is None


def test_decode_rejects_revoked_jti():
    store = JtiStore()
    token, _ = _mint_jwt("client", _SECRET, store)
    payload = _decode_jwt(token, _SECRET, store)
    assert payload is not None
    store.revoke(payload["jti"])
    assert _decode_jwt(token, _SECRET, store) is None


def test_decode_rejects_token_with_unissued_jti():
    store = JtiStore()
    # Forge a payload with a JTI the server never issued. Even with the correct
    # secret, the JTI check blocks it.
    forged_payload = {
        "sub": "client",
        "jti": "attacker-chosen-jti",
        "iat": time.time(),
        "exp": time.time() + 3600,
        "iss": "fabric-mcp-server",
    }
    forged_token = jwt.encode(forged_payload, _SECRET, algorithm="HS256")
    assert _decode_jwt(forged_token, _SECRET, store) is None


# ── _load_api_keys ────────────────────────────────────────────────────────────

def test_load_api_keys_from_env(monkeypatch):
    monkeypatch.setenv("FABRIC_MCP_API_KEYS", "key1, key2 , key3")
    monkeypatch.delenv("FABRIC_MCP_API_KEYS_FILE", raising=False)
    keys = _load_api_keys()
    assert keys == {"key1", "key2", "key3"}


def test_load_api_keys_from_file(tmp_path, monkeypatch):
    key_file = tmp_path / "api-keys.txt"
    key_file.write_text("# comment\nkeyA\nkeyB\n\n# another comment\nkeyC\n", encoding="utf-8")
    monkeypatch.delenv("FABRIC_MCP_API_KEYS", raising=False)
    monkeypatch.setenv("FABRIC_MCP_API_KEYS_FILE", str(key_file))
    keys = _load_api_keys()
    assert keys == {"keyA", "keyB", "keyC"}


def test_load_api_keys_empty_when_not_configured(monkeypatch):
    monkeypatch.delenv("FABRIC_MCP_API_KEYS", raising=False)
    monkeypatch.delenv("FABRIC_MCP_API_KEYS_FILE", raising=False)
    assert _load_api_keys() == set()


# ── FabricAuthMiddleware (ASGI tests via asyncio.run) ─────────────────────────

class _Captured:
    """Minimal ASGI send/receive collector for unit-testing middleware."""

    def __init__(self, body: bytes = b"") -> None:
        self._body = body
        self.responses: list[dict] = []

    async def receive(self):
        return {"type": "http.request", "body": self._body, "more_body": False}

    async def send(self, event):
        self.responses.append(event)

    @property
    def status(self) -> int:
        return next(r["status"] for r in self.responses if r["type"] == "http.response.start")

    @property
    def body(self) -> dict:
        import json as _json
        raw = next(r["body"] for r in self.responses if r["type"] == "http.response.body")
        return _json.loads(raw)


async def _noop_app(scope, receive, send):
    """Inner ASGI app that always returns 200 OK."""
    import json as _json
    body = _json.dumps({"ok": True}).encode()
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": body})


def _make_middleware() -> tuple[FabricAuthMiddleware, JtiStore]:
    store = JtiStore()
    mw = FabricAuthMiddleware(
        _noop_app, api_keys={"good-key"}, secret=_SECRET, jti_store=store
    )
    return mw, store


def _http_scope(path: str, token: str | None = None) -> dict:
    headers = []
    if token:
        headers.append((b"authorization", f"Bearer {token}".encode()))
    return {"type": "http", "path": path, "headers": headers}


def test_middleware_login_valid_key():
    mw, _ = _make_middleware()
    cap = _Captured(b'{"api_key": "good-key"}')
    asyncio.run(mw(_http_scope("/auth/login"), cap.receive, cap.send))
    assert cap.status == 200
    assert "token" in cap.body
    assert cap.body["token_type"] == "Bearer"


def test_middleware_login_invalid_key():
    mw, _ = _make_middleware()
    cap = _Captured(b'{"api_key": "bad-key"}')
    asyncio.run(mw(_http_scope("/auth/login"), cap.receive, cap.send))
    assert cap.status == 401
    assert cap.body["error"] == "invalid_api_key"


def test_middleware_missing_token_returns_401():
    mw, _ = _make_middleware()
    cap = _Captured()
    asyncio.run(mw(_http_scope("/mcp"), cap.receive, cap.send))
    assert cap.status == 401
    assert cap.body["error"] == "missing_token"


def test_middleware_valid_jwt_passes_through():
    mw, store = _make_middleware()
    token, _ = _mint_jwt("client", _SECRET, store)
    cap = _Captured()
    asyncio.run(mw(_http_scope("/mcp", token=token), cap.receive, cap.send))
    assert cap.status == 200
    assert cap.body == {"ok": True}


def test_middleware_invalid_jwt_returns_401():
    mw, _ = _make_middleware()
    cap = _Captured()
    asyncio.run(mw(_http_scope("/mcp", token="not.a.jwt"), cap.receive, cap.send))
    assert cap.status == 401
    assert cap.body["error"] == "invalid_token"


def test_middleware_refresh_issues_new_token_and_revokes_old():
    mw, store = _make_middleware()
    old_token, _ = _mint_jwt("client", _SECRET, store)
    old_payload = _decode_jwt(old_token, _SECRET, store)
    old_jti = old_payload["jti"]

    cap = _Captured(b"")
    asyncio.run(mw(_http_scope("/auth/refresh", token=old_token), cap.receive, cap.send))

    assert cap.status == 200
    new_token = cap.body["token"]
    assert new_token != old_token
    assert store.is_valid(old_jti) is False  # old JTI revoked
    assert _decode_jwt(new_token, _SECRET, store) is not None  # new token valid


def test_middleware_refresh_with_invalid_token_returns_401():
    mw, _ = _make_middleware()
    cap = _Captured(b"")
    asyncio.run(mw(_http_scope("/auth/refresh", token="bad.token.here"), cap.receive, cap.send))
    assert cap.status == 401


def test_middleware_passes_non_http_scopes():
    received = []

    async def inner(scope, receive, send):
        received.append(scope["type"])

    mw = FabricAuthMiddleware(inner, api_keys={"k"}, secret=_SECRET, jti_store=JtiStore())
    asyncio.run(mw({"type": "lifespan", "headers": []}, None, None))
    assert received == ["lifespan"]


# ── _resource_server_url ──────────────────────────────────────────────────────

def test_resource_server_url_uses_public_host_fallback(monkeypatch):
    monkeypatch.delenv("MCP_SERVER_URL", raising=False)
    monkeypatch.setenv("HOST", "0.0.0.0")
    monkeypatch.setenv("PORT", "8000")
    assert _resource_server_url() == "http://127.0.0.1:8000"

    monkeypatch.setenv("MCP_SERVER_URL", "https://fabric.example.com/")
    assert _resource_server_url() == "https://fabric.example.com"
