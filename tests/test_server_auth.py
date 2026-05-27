from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric import rsa
from server.app import (
    SignedEmailTokenVerifier,
    _load_public_key,
    _public_key_map,
    _resource_server_url,
    claimed_email,
    verify_signed_email,
)

ROOT = Path(__file__).resolve().parents[1]
AUTH_REFRESH = ROOT / "cli" / "tools" / "auth" / "refresh.py"


def _load_auth_refresh():
    spec = importlib.util.spec_from_file_location("auth_refresh", AUTH_REFRESH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _private_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=3072)


def _sign(private_key, email):
    return _load_auth_refresh().sign_email(private_key, email)


def test_verifier_accepts_email_signed_by_its_registered_key_and_caches():
    private_key = _private_key()
    verifier = SignedEmailTokenVerifier({"alice@example.com": private_key.public_key()})
    token = _sign(private_key, "alice@example.com")

    access = asyncio.run(verifier.verify_token(token))
    cached = asyncio.run(verifier.verify_token(token))

    assert access is not None
    assert access.client_id == "alice@example.com"
    assert access.scopes == ["mcp"]
    assert cached is not None


def test_verifier_rejects_unregistered_email():
    private_key = _private_key()
    verifier = SignedEmailTokenVerifier({"alice@example.com": private_key.public_key()})
    token = _sign(private_key, "stranger@example.com")

    assert asyncio.run(verifier.verify_token(token)) is None


def test_verifier_rejects_email_signed_by_another_users_key():
    # Mallory holds her own registered key but tries to claim Alice's email.
    alice = _private_key()
    mallory = _private_key()
    verifier = SignedEmailTokenVerifier(
        {
            "alice@example.com": alice.public_key(),
            "mallory@example.com": mallory.public_key(),
        }
    )

    impersonation = _sign(mallory, "alice@example.com")
    assert asyncio.run(verifier.verify_token(impersonation)) is None

    legit = _sign(mallory, "mallory@example.com")
    assert asyncio.run(verifier.verify_token(legit)) is not None


def test_verifier_email_match_is_case_insensitive():
    private_key = _private_key()
    verifier = SignedEmailTokenVerifier({"Alice@Example.com": private_key.public_key()})
    token = _sign(private_key, "ALICE@example.COM")

    access = asyncio.run(verifier.verify_token(token))
    assert access is not None
    assert access.client_id == "alice@example.com"


def test_verifier_records_emails_to_file(tmp_path):
    alice = _private_key()
    bob = _private_key()
    emails_file = tmp_path / "emails.txt"
    verifier = SignedEmailTokenVerifier(
        {"alice@example.com": alice.public_key(), "bob@example.com": bob.public_key()},
        emails_file=emails_file,
    )

    asyncio.run(verifier.verify_token(_sign(alice, "alice@example.com")))
    asyncio.run(verifier.verify_token(_sign(bob, "bob@example.com")))
    asyncio.run(verifier.verify_token(_sign(alice, "alice@example.com")))  # duplicate

    lines = emails_file.read_text(encoding="utf-8").splitlines()
    recorded = {line.split()[-1] for line in lines}
    assert recorded == {"alice@example.com", "bob@example.com"}
    assert len(lines) == 2


def test_claimed_and_verify_helpers():
    private_key = _private_key()
    token = _sign(private_key, "Carol@Example.com")
    assert claimed_email(token) == "carol@example.com"
    assert verify_signed_email(token, private_key.public_key()) == "carol@example.com"
    assert claimed_email("not-a-token") is None
    assert verify_signed_email(token, _private_key().public_key()) is None


def test_public_key_map_loads_email_named_files(tmp_path, monkeypatch):
    auth_refresh = _load_auth_refresh()
    keys_dir = tmp_path / "keys"
    keys_dir.mkdir()

    alice = _private_key()
    bob = _private_key()
    (keys_dir / "alice@example.com.pem").write_text(
        auth_refresh.public_key_pem(alice), encoding="utf-8"
    )
    (keys_dir / "bob@example.com.pem").write_text(
        auth_refresh.public_key_pem(bob), encoding="utf-8"
    )
    monkeypatch.setenv("FABRIC_MCP_PUBLIC_KEYS_DIR", str(keys_dir))

    key_map = _public_key_map()
    assert set(key_map) == {"alice@example.com", "bob@example.com"}

    verifier = SignedEmailTokenVerifier(key_map)
    assert asyncio.run(verifier.verify_token(_sign(bob, "bob@example.com"))) is not None
    assert asyncio.run(verifier.verify_token(_sign(bob, "alice@example.com"))) is None


def test_resource_server_url_uses_public_host_fallback(monkeypatch):
    monkeypatch.delenv("MCP_SERVER_URL", raising=False)
    monkeypatch.setenv("HOST", "0.0.0.0")
    monkeypatch.setenv("PORT", "8000")
    assert _resource_server_url() == "http://127.0.0.1:8000"

    monkeypatch.setenv("MCP_SERVER_URL", "https://fabric.example.com/")
    assert _resource_server_url() == "https://fabric.example.com"


def test_load_public_key_accepts_escaped_pem():
    private_key = _private_key()
    escaped = _load_auth_refresh().public_key_pem(private_key).replace("\n", "\\n")
    loaded = _load_public_key(escaped)
    token = _sign(private_key, "dan@example.com")
    assert verify_signed_email(token, loaded) == "dan@example.com"
