"""FastMCP app builder.

The server exposes graph, content, validate, data, and semantic-model
(uses sempy.fabric python lib). Fabric-CLI-dependent helpers plus the
deterministic lints and pre-commit aggregator live in cli/ and run on the
user's laptop as plain CLI commands (Claude invokes them via Bash).
"""

from __future__ import annotations

import base64
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from starlette.middleware.cors import CORSMiddleware

from .tools.data import tools as data_tools
from .tools.graph import tools as graph_tools
from .tools.semantic_model import tools as semantic_model_tools
from .tools.validate import tools as validate_tools

TOKEN_PREFIX = "fvmcp_rsa_"


def _b64url_decode(value: str) -> bytes:
    padding_bytes = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding_bytes).encode("ascii"))


def _load_public_key(value: str) -> RSAPublicKey:
    key_text = value.strip()
    if "BEGIN PUBLIC KEY" in key_text:
        key_bytes = key_text.replace("\\n", "\n").encode("utf-8")
        public_key = serialization.load_pem_public_key(key_bytes)
    else:
        key_bytes = base64.b64decode(key_text)
        public_key = serialization.load_der_public_key(key_bytes)
    if not isinstance(public_key, RSAPublicKey):
        raise ValueError("public key material must be an RSA public key")
    return public_key


def _normalize_email(value: str) -> str:
    return value.strip().lower()


def claimed_email(token: str) -> str | None:
    """Return the (unverified) email a token claims, or None if malformed."""
    if not token.startswith(TOKEN_PREFIX) or "." not in token:
        return None
    payload_b64 = token.removeprefix(TOKEN_PREFIX).split(".", 1)[0]
    try:
        return _normalize_email(_b64url_decode(payload_b64).decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None


def verify_signed_email(token: str, public_key: RSAPublicKey) -> str | None:
    """Return the signed email if the token is a valid signature, else None."""
    if not token.startswith(TOKEN_PREFIX) or "." not in token:
        return None

    payload_b64, signature_b64 = token.removeprefix(TOKEN_PREFIX).split(".", 1)
    try:
        email = _b64url_decode(payload_b64).decode("utf-8")
        signature = _b64url_decode(signature_b64)
    except (ValueError, UnicodeDecodeError):
        return None

    try:
        public_key.verify(
            signature,
            payload_b64.encode("ascii"),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            ),
            hashes.SHA256(),
        )
    except InvalidSignature:
        return None
    return _normalize_email(email)


class SignedEmailTokenVerifier(TokenVerifier):
    """Authenticate users by an RSA-signed email bound to a per-user key.

    Each user registers one public key under their email. A token is accepted
    only if it claims email X and is signed by the key registered for X, so no
    user can impersonate another's email. Each authenticated email is appended
    to a simple registry file so the admin can see who is using the server.
    """

    def __init__(
        self,
        public_keys: dict[str, RSAPublicKey],
        emails_file: Path | None = None,
        cache_ttl_seconds: int = 300,
    ) -> None:
        self._public_keys = {_normalize_email(k): v for k, v in public_keys.items()}
        self._emails_file = emails_file
        self._cache_ttl_seconds = cache_ttl_seconds
        self._accepted_tokens: dict[str, tuple[float, str]] = {}
        self._seen_emails: set[str] = set()
        self._load_seen_emails()

    async def verify_token(self, token: str) -> AccessToken | None:
        now = time.monotonic()
        cached = self._accepted_tokens.get(token)
        if cached and cached[0] > now:
            return self._access_token(cached[1])

        email = claimed_email(token)
        if email is None:
            return None
        public_key = self._public_keys.get(email)
        if public_key is None:
            return None
        if verify_signed_email(token, public_key) != email:
            return None

        self._record_email(email)
        self._accepted_tokens[token] = (now + self._cache_ttl_seconds, email)
        return self._access_token(email)

    def _load_seen_emails(self) -> None:
        if self._emails_file is None or not self._emails_file.exists():
            return
        for line in self._emails_file.read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if parts:
                self._seen_emails.add(parts[-1])

    def _record_email(self, email: str) -> None:
        if email in self._seen_emails:
            return
        self._seen_emails.add(email)
        if self._emails_file is None:
            return
        try:
            self._emails_file.parent.mkdir(parents=True, exist_ok=True)
            with self._emails_file.open("a", encoding="utf-8") as handle:
                handle.write(f"{datetime.now(timezone.utc).isoformat()} {email}\n")
        except OSError:
            pass

    @staticmethod
    def _access_token(email: str) -> AccessToken:
        return AccessToken(token=email, client_id=email, scopes=["mcp"])


def _public_key_map() -> dict[str, RSAPublicKey]:
    """Load a {email: public_key} map from a directory of <email>.pem files."""
    keys_dir = os.environ.get("FABRIC_MCP_PUBLIC_KEYS_DIR", "").strip()
    if not keys_dir:
        return {}
    directory = Path(keys_dir)
    if not directory.is_dir():
        return {}
    return {
        _normalize_email(path.stem): _load_public_key(path.read_text(encoding="utf-8"))
        for path in sorted(directory.glob("*.pem"))
    }


def _emails_file() -> Path | None:
    configured = os.environ.get("FABRIC_MCP_EMAILS_FILE", "").strip()
    return Path(configured) if configured else None


def _resource_server_url() -> str:
    configured = os.environ.get("MCP_SERVER_URL", "").strip().rstrip("/")
    if configured:
        return configured
    host = os.environ.get("HOST", "127.0.0.1").strip() or "127.0.0.1"
    port = os.environ.get("PORT", "8000").strip() or "8000"
    public_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    return f"http://{public_host}:{port}"


def build_app():
    """Construct the FastMCP app, register every tool, return the ASGI app.

    When per-user public keys are configured (FABRIC_MCP_PUBLIC_KEYS_DIR holds
    one <email>.pem per user), FastMCP requires an RSA-signed email token for
    MCP access. The server stores only public keys; each client keeps its own
    private key and signs its email, which is accepted only against that user's
    registered key. Authenticated emails are appended to FABRIC_MCP_EMAILS_FILE.
    """
    public_keys = _public_key_map()
    auth_settings = None
    token_verifier = None
    if public_keys:
        resource_url = _resource_server_url()
        auth_settings = AuthSettings(
            issuer_url=resource_url,
            resource_server_url=resource_url,
            required_scopes=["mcp"],
        )
        token_verifier = SignedEmailTokenVerifier(public_keys, emails_file=_emails_file())

    mcp = FastMCP("fabric-server", auth=auth_settings, token_verifier=token_verifier)
    graph_tools.register(mcp)
    semantic_model_tools.register(mcp)
    validate_tools.register(mcp)
    data_tools.register(mcp)

    app = mcp.streamable_http_app()

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
