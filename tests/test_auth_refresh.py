from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
AUTH_REFRESH = ROOT / "cli" / "tools" / "auth" / "refresh.py"


def _load_auth_refresh():
    spec = importlib.util.spec_from_file_location("auth_refresh", AUTH_REFRESH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ── JWT expiry helper ─────────────────────────────────────────────────────────

def test_jwt_expiry_decoded_from_token():
    import base64
    mod = _load_auth_refresh()
    future = time.time() + 3600
    payload_json = json.dumps({"exp": future, "sub": "x"}).encode()
    b64 = base64.urlsafe_b64encode(payload_json).decode().rstrip("=")
    fake_token = f"header.{b64}.signature"
    result = mod._jwt_expiry(fake_token)
    assert result is not None
    assert abs(result - future) < 1


def test_jwt_expiry_returns_none_for_invalid():
    mod = _load_auth_refresh()
    assert mod._jwt_expiry("not.a.token") is None
    assert mod._jwt_expiry("onlyone") is None


# ── Token persistence ─────────────────────────────────────────────────────────

def test_save_and_load_token(tmp_path, monkeypatch):
    mod = _load_auth_refresh()
    monkeypatch.setattr(mod, "_STATE_DIR", tmp_path / ".fabric-vibecoding")
    monkeypatch.setattr(mod, "_TOKEN_FILE", tmp_path / ".fabric-vibecoding" / "mcp-token.json")

    mod._save_token("my-jwt-token", 9999999.0)
    saved_token, saved_expiry = mod._load_saved_token()
    assert saved_token == "my-jwt-token"
    assert saved_expiry == 9999999.0


def test_load_token_returns_none_when_no_file(tmp_path, monkeypatch):
    mod = _load_auth_refresh()
    monkeypatch.setattr(mod, "_TOKEN_FILE", tmp_path / "nonexistent.json")
    token, expiry = mod._load_saved_token()
    assert token is None
    assert expiry is None


# ── Server URL resolution ─────────────────────────────────────────────────────

def test_resolve_server_url_from_mcp_json(tmp_path):
    mod = _load_auth_refresh()
    (tmp_path / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"fabric-server": {"type": "http", "url": "http://host:9000/mcp"}}}),
        encoding="utf-8",
    )
    url = mod._resolve_server_url([], tmp_path)
    assert url == "http://host:9000"


def test_resolve_server_url_from_arg(tmp_path):
    mod = _load_auth_refresh()
    url = mod._resolve_server_url(["--server-url", "https://myserver.example.com"], tmp_path)
    assert url == "https://myserver.example.com"


def test_resolve_server_url_default_fallback(tmp_path):
    mod = _load_auth_refresh()
    url = mod._resolve_server_url([], tmp_path)
    assert url == "http://127.0.0.1:8000"


# ── Auth base URL resolution ──────────────────────────────────────────────────

def test_resolve_auth_base_url_default_derives_from_server(monkeypatch):
    mod = _load_auth_refresh()
    monkeypatch.delenv("FABRIC_MCP_AUTH_URL", raising=False)
    url = mod._resolve_auth_base_url([], "https://myserver.example.com")
    assert url == "https://myserver.example.com/api/auth"


def test_resolve_auth_base_url_from_env(monkeypatch):
    mod = _load_auth_refresh()
    monkeypatch.setenv("FABRIC_MCP_AUTH_URL", "https://host/server/auth")
    url = mod._resolve_auth_base_url([], "https://other.host")
    assert url == "https://host/server/auth"


def test_resolve_auth_base_url_from_flag(monkeypatch):
    mod = _load_auth_refresh()
    monkeypatch.delenv("FABRIC_MCP_AUTH_URL", raising=False)
    url = mod._resolve_auth_base_url(["--auth-url", "https://host/custom/auth"], "https://other")
    assert url == "https://host/custom/auth"


def test_resolve_auth_base_url_flag_takes_precedence_over_env(monkeypatch):
    mod = _load_auth_refresh()
    monkeypatch.setenv("FABRIC_MCP_AUTH_URL", "https://env.host/auth")
    url = mod._resolve_auth_base_url(["--auth-url", "https://flag.host/auth"], "https://other")
    assert url == "https://flag.host/auth"


# ── Config injection ──────────────────────────────────────────────────────────

def test_update_mcp_json_injects_bearer_token(tmp_path):
    mod = _load_auth_refresh()
    token = "my.jwt.token"
    (tmp_path / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"fabric-server": {"type": "http", "url": "http://x/mcp"}}}),
        encoding="utf-8",
    )
    mod.update_mcp_json(tmp_path, token)
    doc = json.loads((tmp_path / ".mcp.json").read_text(encoding="utf-8"))
    assert doc["mcpServers"]["fabric-server"]["headers"]["Authorization"] == f"Bearer {token}"


def test_update_codex_config_injects_bearer_token(tmp_path):
    mod = _load_auth_refresh()
    token = "my.jwt.token"
    (tmp_path / ".codex").mkdir()
    (tmp_path / ".codex" / "config.toml").write_text(
        '[mcp_servers.fabric_server]\nurl = "http://x/mcp"\n',
        encoding="utf-8",
    )
    mod.update_codex_config(tmp_path, token)
    text = (tmp_path / ".codex" / "config.toml").read_text(encoding="utf-8")
    assert "[mcp_servers.fabric_server.http_headers]" in text
    assert f'Authorization = "Bearer {token}"' in text


def test_update_codex_config_replaces_existing_token(tmp_path):
    mod = _load_auth_refresh()
    (tmp_path / ".codex").mkdir()
    (tmp_path / ".codex" / "config.toml").write_text(
        '[mcp_servers.fabric_server.http_headers]\nAuthorization = "Bearer old.token.here"\n',
        encoding="utf-8",
    )
    mod.update_codex_config(tmp_path, "new.jwt.token")
    text = (tmp_path / ".codex" / "config.toml").read_text(encoding="utf-8")
    assert 'Authorization = "Bearer new.jwt.token"' in text
    assert "old.token.here" not in text


def test_update_codex_config_migrates_legacy_hyphenated_sections(tmp_path):
    mod = _load_auth_refresh()
    (tmp_path / ".codex").mkdir()
    (tmp_path / ".codex" / "config.toml").write_text(
        '[mcp_servers."fabric-server"]\n'
        'url = "http://x/mcp"\n'
        '\n'
        '[mcp_servers."fabric-server".headers]\n'
        'Authorization = "Bearer old.token.here"\n',
        encoding="utf-8",
    )
    mod.update_codex_config(tmp_path, "new.jwt.token")
    text = (tmp_path / ".codex" / "config.toml").read_text(encoding="utf-8")
    assert "[mcp_servers.fabric_server]" in text
    assert "[mcp_servers.fabric_server.http_headers]" in text
    assert "fabric-server" not in text
    assert 'Authorization = "Bearer new.jwt.token"' in text
    assert "old.token.here" not in text


# ── _prompt_api_key ───────────────────────────────────────────────────────────

def test_prompt_api_key_returns_env_var(monkeypatch):
    mod = _load_auth_refresh()
    monkeypatch.setenv("FABRIC_MCP_API_KEY", "my-key-from-env")
    assert mod._prompt_api_key() == "my-key-from-env"


def test_prompt_api_key_prompts_when_env_not_set(monkeypatch):
    mod = _load_auth_refresh()
    monkeypatch.delenv("FABRIC_MCP_API_KEY", raising=False)
    monkeypatch.setattr("getpass.getpass", lambda _prompt: "prompted-key")
    assert mod._prompt_api_key() == "prompted-key"


def test_prompt_api_key_returns_none_on_empty_input(monkeypatch):
    mod = _load_auth_refresh()
    monkeypatch.delenv("FABRIC_MCP_API_KEY", raising=False)
    monkeypatch.setattr("getpass.getpass", lambda _prompt: "")
    assert mod._prompt_api_key() is None


def test_prompt_api_key_returns_none_on_eof(monkeypatch):
    mod = _load_auth_refresh()
    monkeypatch.delenv("FABRIC_MCP_API_KEY", raising=False)

    def _raise(_prompt: str) -> str:
        raise EOFError

    monkeypatch.setattr("getpass.getpass", _raise)
    assert mod._prompt_api_key() is None


# ── main: skips gracefully when no API key provided ───────────────────────────

def test_main_exits_cleanly_when_no_api_key(monkeypatch, capsys):
    mod = _load_auth_refresh()
    monkeypatch.delenv("FABRIC_MCP_API_KEY", raising=False)
    monkeypatch.setattr("getpass.getpass", lambda _prompt: "")
    result = mod.main([])
    assert result == 0
    captured = capsys.readouterr()
    assert "No API key" in captured.out or "FABRIC_MCP_API_KEY" in captured.out


def test_main_always_fetches_new_token_even_when_cache_is_valid(monkeypatch):
    mod = _load_auth_refresh()
    calls = []

    monkeypatch.setattr(mod, "_prompt_api_key", lambda: "api-key")
    monkeypatch.setattr(mod, "_resolve_server_url", lambda _argv, _root: "https://server.example")
    monkeypatch.setattr(mod, "_resolve_auth_base_url", lambda _argv, _server_url: "https://server.example/api/auth")
    monkeypatch.setattr(mod, "_load_saved_token", lambda: ("cached.jwt.token", time.time() + 3600))

    def fake_fetch(server_url: str, api_key: str):
        calls.append((server_url, api_key))
        return "fresh.jwt.token", time.time() + 3600

    saved = {}
    monkeypatch.setattr(mod, "_fetch_token", fake_fetch)
    monkeypatch.setattr(mod, "_save_token", lambda token, expires_at: saved.update(token=token, expires_at=expires_at))
    monkeypatch.setattr(mod, "update_mcp_json", lambda _root, token: saved.update(mcp_token=token))
    monkeypatch.setattr(mod, "update_codex_config", lambda _root, token: saved.update(codex_token=token))

    assert mod.main([]) == 0
    assert calls == [("https://server.example", "api-key")]
    assert saved["token"] == "fresh.jwt.token"
    assert saved["mcp_token"] == "fresh.jwt.token"
    assert saved["codex_token"] == "fresh.jwt.token"
