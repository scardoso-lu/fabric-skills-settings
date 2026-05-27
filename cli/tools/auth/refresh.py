#!/usr/bin/env python3
"""Generate an MCP identity key pair and sign the user's email for MCP auth.

The MCP server authenticates users by an RSA-signed email. On first run this
command generates an unencrypted RSA key pair under ~/.fabric-vibecoding/,
prompts for the user's email, signs the email with the private key, and writes
the signed string into the Claude/Codex MCP configuration as the bearer token.

The user shares the printed PUBLIC key with the MCP server admin. The admin
drops it into the server's public-keys directory; the server then accepts the
signed email and records the email in its user registry file.

Usage:
    fabric-vibe auth refresh [--email you@example.com]
"""

from __future__ import annotations

import base64
import json
import os
import re
import sys
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

ROOT = Path.cwd()
TOKEN_PREFIX = "fvmcp_rsa_"
KEY_SIZE = 3072

KEY_DIR = Path.home() / ".fabric-vibecoding"
PRIVATE_KEY_FILE = KEY_DIR / "fabric-mcp-private-key.pem"
EMAIL_FILE = KEY_DIR / "email"


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def load_or_create_keypair(key_dir: Path = KEY_DIR) -> tuple[RSAPrivateKey, bool]:
    """Return (private_key, created). Generate and persist on first run."""
    private_file = key_dir / PRIVATE_KEY_FILE.name
    if private_file.exists():
        key = serialization.load_pem_private_key(private_file.read_bytes(), password=None)
        if not isinstance(key, RSAPrivateKey):
            raise SystemExit(f"{private_file} must contain an RSA private key")
        return key, False

    key_dir.mkdir(parents=True, exist_ok=True)
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=KEY_SIZE)
    private_file.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    try:
        os.chmod(private_file, 0o600)
    except OSError:
        pass
    return private_key, True


def write_public_key_file(key_dir: Path, private_key: RSAPrivateKey, email: str) -> Path:
    """Write the shareable public key as <email>.pem and return its path."""
    key_dir.mkdir(parents=True, exist_ok=True)
    path = key_dir / f"{email}.pem"
    path.write_text(public_key_pem(private_key), encoding="utf-8")
    return path


def public_key_pem(private_key: RSAPrivateKey) -> str:
    return private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")


def _valid_email(value: str) -> bool:
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value))


def resolve_email(argv: list[str], key_dir: Path = KEY_DIR) -> str:
    """Resolve the user email from --email, env, saved file, or a prompt."""
    email = ""
    if "--email" in argv:
        idx = argv.index("--email")
        if idx + 1 < len(argv):
            email = argv[idx + 1].strip()
    if not email:
        email = os.environ.get("FABRIC_MCP_USER_EMAIL", "").strip()
    if not email:
        saved = key_dir / "email"
        if saved.exists():
            email = saved.read_text(encoding="utf-8").strip()
    if not email:
        try:
            email = input("  Your email (identity for MCP auth): ").strip()
        except EOFError:
            email = ""
    if not _valid_email(email):
        raise SystemExit(
            "A valid email is required. Pass --email you@example.com, set "
            "FABRIC_MCP_USER_EMAIL, or enter one when prompted."
        )
    key_dir.mkdir(parents=True, exist_ok=True)
    (key_dir / "email").write_text(email + "\n", encoding="utf-8")
    return email


def sign_email(private_key: RSAPrivateKey, email: str) -> str:
    payload_b64 = _b64url_encode(email.encode("utf-8"))
    signature = private_key.sign(
        payload_b64.encode("ascii"),
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH,
        ),
        hashes.SHA256(),
    )
    return f"{TOKEN_PREFIX}{payload_b64}.{_b64url_encode(signature)}"


def update_mcp_json(root: Path, token: str) -> None:
    mcp_json = root / ".mcp.json"
    if not mcp_json.exists():
        print(f"  .mcp.json not found at {mcp_json}; skipping", file=sys.stderr)
        return
    doc = json.loads(mcp_json.read_text(encoding="utf-8-sig"))
    (
        doc.setdefault("mcpServers", {})
        .setdefault("fabric-server", {})
        .setdefault("headers", {})["Authorization"]
    ) = f"Bearer {token}"
    mcp_json.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print("  Updated .mcp.json")


def update_codex_config(root: Path, token: str) -> None:
    config = root / ".codex" / "config.toml"
    if not config.exists():
        return
    text = config.read_text(encoding="utf-8")
    auth_line = f'Authorization = "Bearer {token}"'
    if re.search(r"^\[mcp_servers\.fabric-server\.headers\]", text, re.MULTILINE):
        text = re.sub(
            r"(^\[mcp_servers\.fabric-server\.headers\][^\[]*?)^Authorization\s*=.*$",
            lambda m: m.group(1) + auth_line,
            text,
            flags=re.MULTILINE | re.DOTALL,
        )
        if f'Authorization = "Bearer' not in text:
            text = re.sub(
                r"(\[mcp_servers\.fabric-server\.headers\])",
                rf"\1\n{auth_line}",
                text,
            )
    else:
        text = text.rstrip() + f"\n\n[mcp_servers.fabric-server.headers]\n{auth_line}\n"
    config.write_text(text, encoding="utf-8")
    print("  Updated .codex/config.toml")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    private_key, created = load_or_create_keypair()
    email = resolve_email(argv)
    token = sign_email(private_key, email)
    update_mcp_json(ROOT, token)
    update_codex_config(ROOT, token)
    public_key_file = write_public_key_file(KEY_DIR, private_key, email)

    print()
    if created:
        print(f"Generated a new RSA key pair under {KEY_DIR}.")
    print(f"Signed identity for {email} written to the MCP client headers.")
    print("Reload your Claude Code / Codex session to pick up the MCP token.")
    print()
    print("Send this public key file to your MCP server admin. Its name is already")
    print("set to your email, which is how the server links the key to you:")
    print()
    print(f"  {public_key_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
