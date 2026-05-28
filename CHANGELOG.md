# Changelog

All notable changes to **fabric-vibecoding-settings** are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.2.0] — 2026-05-28

Headline: a reworked **MCP server authentication** stack — a CSV-based API-key
store, a pluggable key source (local disk **or** Azure Blob Storage), and a
self-contained `server/auth` module.

### Added
- **Pluggable API-key repository.** The key store is now loaded through a
  repository abstraction selected at deploy time with
  `FABRIC_MCP_API_KEYS_SOURCE`:
  - `file` (default) — read the CSV from disk (`FABRIC_MCP_API_KEYS_FILE`).
  - `azure-blob` — download the CSV from Azure Blob Storage, authenticating with
    a connection string (`FABRIC_MCP_API_KEYS_BLOB_CONNECTION_STRING`) or an
    account URL + `DefaultAzureCredential`
    (`FABRIC_MCP_API_KEYS_BLOB_ACCOUNT_URL`).
- **`server-azure` optional extra** (`azure-storage-blob`, `azure-identity`) for
  the Azure Blob source. Imported lazily, so file-mode deployments pull in no
  Azure dependencies.
- New env vars: `FABRIC_MCP_API_KEYS_SOURCE`,
  `FABRIC_MCP_API_KEYS_BLOB_CONTAINER`, `FABRIC_MCP_API_KEYS_BLOB_NAME`,
  `FABRIC_MCP_API_KEYS_BLOB_CONNECTION_STRING`,
  `FABRIC_MCP_API_KEYS_BLOB_ACCOUNT_URL`.
- Test coverage for the repository (`tests/test_api_key_repository.py`) and the
  auth middleware installer.

### Changed
- **API-key store is now a CSV** with the headers `email,apikey` (one row per
  user; only the `apikey` column authenticates, `email` is for admin
  bookkeeping) — replacing the previous one-key-per-line plaintext file.
- **`server/auth` is now a self-contained package.** All authentication logic
  moved out of `server/app.py`:
  - `repository.py` — API-key sourcing (`load_api_keys`, the repositories, the
    source factory).
  - `tokens.py` — `JtiStore`, JWT mint/decode, secret loading.
  - `middleware.py` — `FabricAuthMiddleware` and `install_auth_middleware(app)`.

  `server/app.py` now only builds the FastMCP app and wires auth + CORS.
- `docker-compose.yml` mounts `config/api-keys.csv` and exposes the
  `FABRIC_MCP_API_KEYS_SOURCE` selector (defaults to `file`).
- Docs refreshed: `docs/mcp-auth-flow.md`, `docs/architecture.md`, and the
  `CLAUDE.md` source-layout table.

### Migration (0.1 → 0.2)
1. **Convert your key file to CSV.** Replace the old one-key-per-line file with
   a CSV that has an `email,apikey` header row:
   ```csv
   email,apikey
   alice@example.com,user-alice-abc123def456
   bob@example.com,user-bob-789xyz...
   ```
   Rename it to `api-keys.csv` (the bundled compose file now mounts
   `config/api-keys.csv`). Comment lines (`#`) are no longer supported.
2. **No env changes required for disk mode** beyond pointing
   `FABRIC_MCP_API_KEYS_FILE` at the CSV. `FABRIC_MCP_API_KEYS_SOURCE` defaults
   to `file`.
3. **To load keys from Azure Blob Storage**, set
   `FABRIC_MCP_API_KEYS_SOURCE=azure-blob`, provide the container/blob and an
   auth method, and install the `server-azure` extra in the server image.
4. Keys are read at server startup — restart the container after rotating keys,
   regardless of source.

## [0.1.0]

- Client/server split: Fabric-CLI-dependent helpers run on the user's laptop
  (`fabric-vibe`), graph/lint/validate tools run in the Dockerized FastMCP
  server (`fabric-server`).
- Knowledge-graph-driven Claude and Codex profiles, installer
  (`fabric-vibecoding-agents`), and target-side tooling.
- MCP server authentication (API-key + JWT) with a plaintext key file.

[0.2.0]: https://github.com/scardoso-lu/fabric-skills-settings/releases/tag/v0.2.0
[0.1.0]: https://github.com/scardoso-lu/fabric-skills-settings/releases/tag/v0.1.0
