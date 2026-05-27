# MCP auth flow

The `fabric-server` FastMCP server uses **API-key + JWT** authentication. Auth is opt-in: if neither `FABRIC_MCP_API_KEYS_FILE` nor `FABRIC_MCP_API_KEYS` is set, the server accepts unauthenticated requests (local single-user dev mode).

## Overview

```
Client (user's laptop)                   Server (Docker 127.0.0.1:8000)
─────────────────────                    ───────────────────────────────
FABRIC_MCP_API_KEY                       config/api-keys.txt
  (from shell profile)                     (admin-managed list)
        │                                        │
        ▼                                        ▼
POST /auth/login ──{"api_key": "..."} ──► validate key
        ◄── {"token": "<jwt>", ...} ─────── mint JWT (1 h, signed HS256)
        │                                   JtiStore: record jti
        ▼
Bearer <jwt> injected into
  .mcp.json + .codex/config.toml
        │
        ▼
MCP request ──► FabricAuthMiddleware
                  verify signature
                  check exp (PyJWT)
                  check jti in JtiStore
                        ▼
                  tool executed
```

## Token lifecycle

| Step | Client | Server |
|---|---|---|
| **Login** | POST `/auth/login` with `{"api_key": "..."}` | Validates key, mints JWT, records jti |
| **Request** | `Authorization: Bearer <jwt>` | Checks signature, `exp`, jti in JtiStore |
| **Refresh** | POST `/auth/refresh` with current Bearer token | Revokes old jti, mints new JWT |
| **Expiry** | Automatic via `fabric-vibe auth refresh` | Purges stale JTIs on next issue |

## JWT claims

```json
{
  "sub": "client",
  "jti": "<uuid4>",
  "iat": 1234567890,
  "exp": 1234571490,
  "iss": "fabric-mcp-server"
}
```

Signed with HS256 using `FABRIC_MCP_JWT_SECRET`. Expiry: **1 hour**.

## Client side — `fabric-vibe auth refresh`

Driven by `cli/tools/auth/refresh.py`. Called by `setup.sh` / `setup.ps1` at bootstrap and re-runnable at any time.

```mermaid
sequenceDiagram
    participant User
    participant CLI as fabric-vibe auth refresh
    participant FS as ~/.fabric-vibecoding/mcp-token.json
    participant CFG as .mcp.json / .codex/config.toml
    participant Srv as MCP server /auth/*

    User->>CLI: fabric-vibe auth refresh
    CLI->>CLI: read FABRIC_MCP_API_KEY from env
    CLI->>FS: load saved token (if any)
    alt token still fresh (>5 min remaining)
        FS-->>CLI: token
        CLI->>CFG: patch Authorization header
    else token expiring soon
        CLI->>Srv: POST /auth/refresh (Bearer <old_token>)
        Srv-->>CLI: new JWT (old JTI revoked)
        CLI->>FS: save new token
        CLI->>CFG: patch Authorization header
    else no saved token / refresh failed
        CLI->>Srv: POST /auth/login (api_key)
        Srv-->>CLI: new JWT
        CLI->>FS: save token
        CLI->>CFG: patch Authorization header
    end
```

## Server side — `FabricAuthMiddleware`

Implemented in `server/app.py` as a pure ASGI middleware wrapping the FastMCP app.

```mermaid
sequenceDiagram
    participant Agent as Claude Code / Codex
    participant CORS as CORSMiddleware (outer)
    participant Auth as FabricAuthMiddleware (inner)
    participant MCP as FastMCP app

    Agent->>CORS: POST /mcp  Authorization: Bearer <jwt>
    CORS->>Auth: forward
    Auth->>Auth: extract Bearer token
    Auth->>Auth: jwt.decode (signature + exp)
    Auth->>Auth: JtiStore.is_valid(jti)
    alt valid token
        Auth->>MCP: forward request
        MCP-->>Agent: tool result
    else invalid / expired / replayed
        Auth-->>Agent: 401 {"error": "invalid_token"}
    end
```

### Replay prevention

Each JWT contains a unique `jti` (UUID4). The `JtiStore` tracks all issued JTIs with their expiry timestamps:

- **Login / Refresh**: new jti added to JtiStore
- **Refresh**: old jti immediately revoked — a captured old token can no longer be replayed
- **Expiry**: stale JTIs purged lazily on the next `issue()` call
- **Forged tokens**: unknown jti → rejected even if signature were somehow valid

### Auth opt-out

Auth is **disabled entirely** when `FABRIC_MCP_API_KEYS_FILE` is unset and `FABRIC_MCP_API_KEYS` is empty — the `FabricAuthMiddleware` is not added to the app, and `/auth/login` returns 404.

## Server configuration

### docker-compose.yml

```yaml
services:
  server:
    environment:
      MCP_SERVER_URL: ${MCP_SERVER_URL:-http://127.0.0.1:8000}
      FABRIC_MCP_API_KEYS_FILE: /config/api-keys.txt
      FABRIC_MCP_JWT_SECRET: ${FABRIC_MCP_JWT_SECRET}
    volumes:
      - ./config/api-keys.txt:/config/api-keys.txt:ro  # admin-managed
      - ./data:/data
    ports:
      - "127.0.0.1:8000:8000"
```

### Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `FABRIC_MCP_API_KEYS_FILE` | _(unset)_ | Path to file with one API key per line. Auth enabled when set. |
| `FABRIC_MCP_API_KEYS` | _(unset)_ | Comma-separated API keys (alternative to file). |
| `FABRIC_MCP_JWT_SECRET` | _(required when auth enabled)_ | HS256 signing secret. Generate: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `MCP_SERVER_URL` | derived from `HOST`+`PORT` | Informational — returned in auth responses. |
| `FABRIC_CORS_ORIGINS` | `*` | Comma-separated allowed CORS origins. Tighten for non-local deployments. |

### Admin API key management

Create `server/config/api-keys.txt` on the host. One key per line. Lines starting with `#` are comments:

```
# Fabric MCP API keys — one per line, one per user
user-alice-abc123def456
user-bob-789xyz...
```

Give each user their key. They set `FABRIC_MCP_API_KEY=<key>` in their shell profile (setup script handles this). Restart the container after adding or removing keys.

## Setup flow (end to end)

`setup.sh` / `setup.ps1` runs `fabric-vibe auth refresh` as part of the MCP token step:

1. Prompt for `FABRIC_MCP_API_KEY` (secret, persisted to shell profile / OS registry, **not** `.env`)
2. Write `.mcp.json` with the MCP URL (no auth header yet)
3. Call `fabric-vibe auth refresh`
   - reads `FABRIC_MCP_API_KEY` from env
   - POST `/auth/login` → receives JWT
   - saves JWT to `~/.fabric-vibecoding/mcp-token.json`
   - patches `.mcp.json` and `.codex/config.toml` with `Authorization: Bearer <token>`
4. User is ready to run Claude Code / Codex against the MCP server
