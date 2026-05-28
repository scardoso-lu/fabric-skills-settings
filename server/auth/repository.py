"""Repository pattern for loading MCP API keys from a pluggable backend.

The set of valid API keys lives in a CSV with the headers ``email,apikey`` —
one row per user; only the ``apikey`` column authenticates (``email`` is for
admin bookkeeping). *Where* that CSV comes from is chosen by the server admin
at deploy time via the ``FABRIC_MCP_API_KEYS_SOURCE`` environment variable:

  - ``file``       — read from the local filesystem at
                     ``FABRIC_MCP_API_KEYS_FILE``. This is the default when the
                     variable is unset (backwards compatible).
  - ``azure-blob`` — download from Azure Blob Storage.

Every backend returns the raw CSV text; :func:`parse_api_keys_csv` turns it
into the set of keys, so the CSV format is defined in exactly one place.

Azure mode needs the optional ``azure-storage-blob`` (and, for managed-identity
auth, ``azure-identity``) packages — install the ``server-azure`` extra. The
import is lazy so file-mode deployments incur no Azure dependency.
"""

from __future__ import annotations

import csv
import io
import os
from abc import ABC, abstractmethod
from pathlib import Path

# Accepted spellings for the source selector, normalized to the canonical name.
_FILE_ALIASES = {"", "file", "local", "disk", "filesystem"}
_AZURE_BLOB_ALIASES = {"azure-blob", "azure_blob", "azureblob", "blob", "azure"}


def parse_api_keys_csv(text: str) -> set[str]:
    """Parse an ``email,apikey`` CSV into the set of API keys.

    Only the ``apikey`` column is used. Header names are matched
    case-insensitively and tolerate surrounding whitespace; blank key cells are
    skipped.
    """
    keys: set[str] = set()
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        key = next(
            (
                (value or "").strip()
                for name, value in row.items()
                if name and name.strip().lower() == "apikey"
            ),
            "",
        )
        if key:
            keys.add(key)
    return keys


class ApiKeyRepository(ABC):
    """A source of the ``email,apikey`` CSV that backs MCP authentication."""

    @abstractmethod
    def fetch_csv(self) -> str | None:
        """Return the raw CSV text, or ``None`` if the source is absent/empty."""

    def load_keys(self) -> set[str]:
        """Fetch the CSV and parse it into the set of valid API keys."""
        text = self.fetch_csv()
        if not text:
            return set()
        return parse_api_keys_csv(text)


class LocalFileApiKeyRepository(ApiKeyRepository):
    """Load the api-keys CSV from a file on the local filesystem."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self._path = Path(path)

    def fetch_csv(self) -> str | None:
        if not self._path.is_file():
            return None
        return self._path.read_text(encoding="utf-8")


class AzureBlobApiKeyRepository(ApiKeyRepository):
    """Load the api-keys CSV from a blob in Azure Blob Storage.

    Authentication is resolved in this order:

      1. ``connection_string`` — a storage-account connection string.
      2. ``account_url`` + :class:`~azure.identity.DefaultAzureCredential`
         (managed identity, workload identity, env credentials, …).

    A ``blob_client`` may be injected directly (primarily for tests) to bypass
    SDK construction entirely.
    """

    def __init__(
        self,
        *,
        container: str,
        blob: str,
        connection_string: str | None = None,
        account_url: str | None = None,
        blob_client=None,
    ) -> None:
        if not container or not blob:
            raise ValueError("AzureBlobApiKeyRepository requires both 'container' and 'blob'.")
        if blob_client is None and not connection_string and not account_url:
            raise ValueError(
                "AzureBlobApiKeyRepository requires a connection_string or an account_url."
            )
        self._container = container
        self._blob = blob
        self._connection_string = connection_string
        self._account_url = account_url
        self._injected_client = blob_client

    def fetch_csv(self) -> str | None:
        client = self._injected_client or self._build_blob_client()
        # Import lazily so the SDK is only required at call time.
        try:
            from azure.core.exceptions import ResourceNotFoundError
        except ImportError:  # pragma: no cover - only when SDK missing
            ResourceNotFoundError = ()  # type: ignore[assignment]
        try:
            data = client.download_blob().readall()
        except ResourceNotFoundError:
            return None
        if isinstance(data, bytes):
            return data.decode("utf-8")
        return data

    def _build_blob_client(self):
        try:
            from azure.storage.blob import BlobServiceClient
        except ImportError as exc:  # pragma: no cover - exercised via message only
            raise RuntimeError(
                "Azure Blob API-key source requires the 'azure-storage-blob' package. "
                "Install the 'server-azure' extra (pip install "
                "'fabric-vibecoding-settings[server-azure]')."
            ) from exc

        if self._connection_string:
            service = BlobServiceClient.from_connection_string(self._connection_string)
        else:
            try:
                from azure.identity import DefaultAzureCredential
            except ImportError as exc:  # pragma: no cover - exercised via message only
                raise RuntimeError(
                    "Azure Blob API-key source with account_url requires the "
                    "'azure-identity' package. Install the 'server-azure' extra."
                ) from exc
            service = BlobServiceClient(
                account_url=self._account_url, credential=DefaultAzureCredential()
            )
        return service.get_blob_client(container=self._container, blob=self._blob)


def build_api_key_repository() -> ApiKeyRepository | None:
    """Construct the configured repository, or ``None`` if no file source is set.

    Reads ``FABRIC_MCP_API_KEYS_SOURCE`` to pick the backend (defaults to
    ``file``). Returns ``None`` only for the file backend when no path is
    configured — keeping auth opt-in for local single-user dev. Misconfigured
    backends raise ``RuntimeError`` so the server fails fast at startup.
    """
    source = os.environ.get("FABRIC_MCP_API_KEYS_SOURCE", "").strip().lower()

    if source in _FILE_ALIASES:
        file_path = os.environ.get("FABRIC_MCP_API_KEYS_FILE", "").strip()
        if not file_path:
            return None
        return LocalFileApiKeyRepository(file_path)

    if source in _AZURE_BLOB_ALIASES:
        container = os.environ.get("FABRIC_MCP_API_KEYS_BLOB_CONTAINER", "").strip()
        blob = os.environ.get("FABRIC_MCP_API_KEYS_BLOB_NAME", "").strip()
        if not container or not blob:
            raise RuntimeError(
                "FABRIC_MCP_API_KEYS_SOURCE=azure-blob requires "
                "FABRIC_MCP_API_KEYS_BLOB_CONTAINER and FABRIC_MCP_API_KEYS_BLOB_NAME."
            )
        connection_string = (
            os.environ.get("FABRIC_MCP_API_KEYS_BLOB_CONNECTION_STRING", "").strip() or None
        )
        account_url = os.environ.get("FABRIC_MCP_API_KEYS_BLOB_ACCOUNT_URL", "").strip() or None
        if not connection_string and not account_url:
            raise RuntimeError(
                "FABRIC_MCP_API_KEYS_SOURCE=azure-blob requires either "
                "FABRIC_MCP_API_KEYS_BLOB_CONNECTION_STRING or "
                "FABRIC_MCP_API_KEYS_BLOB_ACCOUNT_URL (used with DefaultAzureCredential)."
            )
        return AzureBlobApiKeyRepository(
            container=container,
            blob=blob,
            connection_string=connection_string,
            account_url=account_url,
        )

    raise RuntimeError(
        f"Unknown FABRIC_MCP_API_KEYS_SOURCE: {source!r} "
        "(expected 'file' or 'azure-blob')."
    )
