"""Authentication for the Fabric MCP server.

Self-contained auth layer so the app builder stays thin:

- ``repository.py`` — SQLite API-key store; callers use :func:`build_key_store_from_env`.
- ``tokens.py`` — HS256 JWT minting/verification and the replay-guard :class:`JtiStore`.
- ``middleware.py`` — the ASGI :class:`FabricAuthMiddleware` plus
  :func:`install_auth_middleware`, which wires everything onto an app.
"""

from .middleware import FabricAuthMiddleware, install_auth_middleware
from .repository import (
    SqliteApiKeyStore,
    build_key_store_from_env,
    get_store,
)
from .tokens import JtiStore, decode_jwt, jwt_secret, mint_jwt

__all__ = [
    # repository
    "SqliteApiKeyStore",
    "build_key_store_from_env",
    "get_store",
    # tokens
    "JtiStore",
    "decode_jwt",
    "jwt_secret",
    "mint_jwt",
    # middleware
    "FabricAuthMiddleware",
    "install_auth_middleware",
]
