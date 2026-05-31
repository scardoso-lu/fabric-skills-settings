"""Authentication for the Fabric MCP server.

Self-contained auth layer so the app builder stays thin:

- ``repository.py`` — pluggable API-key store (disk / Azure Blob / inline env);
  callers use :func:`load_api_keys`.
- ``tokens.py`` — HS256 JWT minting/verification and the replay-guard
  :class:`JtiStore`.
- ``middleware.py`` — the ASGI :class:`FabricAuthMiddleware` plus
  :func:`install_auth_middleware`, which wires everything onto an app.
"""

from .middleware import FabricAuthMiddleware, install_auth_middleware
from .repository import (
    ApiKeyRepository,
    AzureBlobApiKeyRepository,
    CompositeApiKeyRepository,
    CsvApiKeyRepository,
    EnvVarApiKeyRepository,
    LocalFileApiKeyRepository,
    MutableApiKeyStore,
    SqliteApiKeyStore,
    build_api_key_repository,
    build_csv_api_key_repository,
    build_key_store_from_env,
    get_store,
    load_api_keys,
    parse_api_keys_csv,
)
from .tokens import JtiStore, decode_jwt, jwt_secret, mint_jwt

__all__ = [
    # repository
    "ApiKeyRepository",
    "AzureBlobApiKeyRepository",
    "CompositeApiKeyRepository",
    "CsvApiKeyRepository",
    "EnvVarApiKeyRepository",
    "LocalFileApiKeyRepository",
    "MutableApiKeyStore",
    "SqliteApiKeyStore",
    "build_api_key_repository",
    "build_csv_api_key_repository",
    "build_key_store_from_env",
    "get_store",
    "load_api_keys",
    "parse_api_keys_csv",
    # tokens
    "JtiStore",
    "decode_jwt",
    "jwt_secret",
    "mint_jwt",
    # middleware
    "FabricAuthMiddleware",
    "install_auth_middleware",
]
