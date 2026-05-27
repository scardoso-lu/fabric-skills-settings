from __future__ import annotations

import importlib.util
import json
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


def test_keypair_generated_under_home_and_reused(tmp_path):
    mod = _load_auth_refresh()
    key_dir = tmp_path / ".fabric-vibecoding"

    first_key, created_first = mod.load_or_create_keypair(key_dir)
    assert created_first is True
    assert (key_dir / "fabric-mcp-private-key.pem").exists()

    second_key, created_second = mod.load_or_create_keypair(key_dir)
    assert created_second is False
    assert mod.public_key_pem(second_key) == mod.public_key_pem(first_key)


def test_public_key_written_as_email_named_file(tmp_path):
    mod = _load_auth_refresh()
    key_dir = tmp_path / ".fabric-vibecoding"
    private_key, _ = mod.load_or_create_keypair(key_dir)

    path = mod.write_public_key_file(key_dir, private_key, "alice@example.com")
    assert path == key_dir / "alice@example.com.pem"
    assert path.read_text(encoding="utf-8").startswith("-----BEGIN PUBLIC KEY-----")


def test_resolve_email_prefers_arg_then_persists(tmp_path, monkeypatch):
    mod = _load_auth_refresh()
    monkeypatch.delenv("FABRIC_MCP_USER_EMAIL", raising=False)
    key_dir = tmp_path / ".fabric-vibecoding"

    email = mod.resolve_email(["--email", "alice@example.com"], key_dir)
    assert email == "alice@example.com"
    assert (key_dir / "email").read_text(encoding="utf-8").strip() == "alice@example.com"

    # Saved email is reused when no arg/env is provided.
    assert mod.resolve_email([], key_dir) == "alice@example.com"


def test_resolve_email_rejects_invalid(tmp_path, monkeypatch):
    mod = _load_auth_refresh()
    monkeypatch.delenv("FABRIC_MCP_USER_EMAIL", raising=False)
    with pytest.raises(SystemExit, match="valid email"):
        mod.resolve_email(["--email", "not-an-email"], tmp_path / ".fabric-vibecoding")


def test_sign_email_hydrates_mcp_configs(tmp_path):
    mod = _load_auth_refresh()
    key_dir = tmp_path / ".fabric-vibecoding"
    private_key, _ = mod.load_or_create_keypair(key_dir)
    token = mod.sign_email(private_key, "alice@example.com")
    assert token.startswith("fvmcp_rsa_")

    root = tmp_path / "repo"
    (root / ".codex").mkdir(parents=True)
    (root / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"fabric-server": {"type": "http", "url": "http://x/mcp"}}}),
        encoding="utf-8",
    )
    (root / ".codex" / "config.toml").write_text(
        '[mcp_servers.fabric-server]\nurl = "http://x/mcp"\n',
        encoding="utf-8",
    )

    mod.update_mcp_json(root, token)
    mod.update_codex_config(root, token)

    mcp_doc = json.loads((root / ".mcp.json").read_text(encoding="utf-8"))
    assert mcp_doc["mcpServers"]["fabric-server"]["headers"]["Authorization"] == f"Bearer {token}"
    codex_config = (root / ".codex" / "config.toml").read_text(encoding="utf-8")
    assert "[mcp_servers.fabric-server.headers]" in codex_config
    assert f'Authorization = "Bearer {token}"' in codex_config
