"""Authentication helpers for the Fabric MCP server.

The API-key store is loaded through a small repository abstraction so the
*source* of the keys (local disk vs Azure Blob Storage) can be swapped at
deploy time without touching the auth middleware. See ``repository.py``.
"""

from .repository import (
    ApiKeyRepository,
    AzureBlobApiKeyRepository,
    LocalFileApiKeyRepository,
    build_api_key_repository,
    parse_api_keys_csv,
)

__all__ = [
    "ApiKeyRepository",
    "AzureBlobApiKeyRepository",
    "LocalFileApiKeyRepository",
    "build_api_key_repository",
    "parse_api_keys_csv",
]
