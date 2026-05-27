# MCP auth flow

The `fabric-server` FastMCP server authenticates clients by **verifying an RSA signature**: the client signs its email address with its private key, the server checks the signature against the registered public key for that email. No JWTs, no OAuth tokens — just a proof that you hold the private key.

Auth is opt-in: when `FABRIC_MCP_PUBLIC_KEYS_DIR` is unset the server accepts all requests (single-user local dev).

## Overview

```
Client (user's laptop)                    Server (Docker 127.0.0.1:8000)
──────────────────────                    ───────────────────────────────
~/.fabric-vibecoding/
  fabric-mcp-private-key.pem  ──signs──►  signed string in .mcp.json / config.toml
  <email>.pem  ········ manual exchange ·········► server/keys/<email>.pem
               (user → admin, out of band)              │
                                               verify RSA-PSS signature:
                                               does sig match email using <email>.pem?
                                                    │
                                                    ▼
                                          /data/authenticated-emails.txt (audit)
```

> **Manual step required.** Before MCP auth works, the user must send their
> `<email>.pem` public key to the MCP server admin, and the admin must place it
> in `server/keys/` and restart the container. This is a deliberate one-time
> out-of-band exchange — see [Key exchange (user ↔ admin)](#key-exchange-user--admin) below.

## Signed credential format

```
fvmcp_rsa_<email_b64url>.<signature_b64url>
```

- `fvmcp_rsa_` — fixed prefix, identifies the scheme
- `<email_b64url>` — URL-safe base64 (no padding) of the raw email string
- `<signature_b64url>` — URL-safe base64 (no padding) of the RSA-PSS SHA-256 signature over `<email_b64url>` (i.e. the ASCII bytes of the already-encoded email)

This is a **custom format**, not a JWT. The server never decodes a header or validates expiry — it only checks whether the signature is valid for the public key registered under the claimed email.

The signed string is stored **as-is** in the MCP client configs — no `Bearer` wrapper needed.

## Client side — `fabric-vibe auth refresh`

Driven by `cli/tools/auth/refresh.py`, invoked by `setup.sh` / `setup.ps1` and re-runnable at any time.

```mermaid
sequenceDiagram
    participant User
    participant CLI as fabric-vibe auth refresh
    participant FS as ~/.fabric-vibecoding/
    participant CFG as .mcp.json / .codex/config.toml

    User->>CLI: fabric-vibe auth refresh [--email you@example.com]
    CLI->>FS: load fabric-mcp-private-key.pem (or generate 3072-bit RSA key pair on first run)
    FS-->>CLI: RSAPrivateKey
    CLI->>CLI: resolve email (--email flag → FABRIC_MCP_USER_EMAIL → saved file → prompt)
    CLI->>CLI: sign email_b64url with RSA-PSS SHA-256 → fvmcp_rsa_<email_b64>.<sig_b64>
    CLI->>FS: write <email>.pem (public key — share with server admin)
    CLI->>CFG: write signed string into .mcp.json headers
    CLI->>CFG: write signed string into .codex/config.toml [mcp_servers.fabric-server.headers]
    CLI-->>User: print path to ~/.fabric-vibecoding/<email>.pem
```

Key files written (all under `~/.fabric-vibecoding/`):

| File | Contents | Stays on machine |
|---|---|---|
| `fabric-mcp-private-key.pem` | 3072-bit RSA private key, PKCS8, unencrypted, `chmod 600` | Yes — never shared |
| `<email>.pem` | Matching RSA public key, SubjectPublicKeyInfo PEM | No — send to server admin |

The signed credential is re-generated on every `auth refresh` run. The private key is reused across refreshes unless deleted manually.

### What goes into the MCP configs

`.mcp.json` (Claude Code):
```json
{
  "mcpServers": {
    "fabric-server": {
      "type": "http",
      "url": "http://127.0.0.1:8000/mcp",
      "headers": {
        "Authorization": "fvmcp_rsa_<email_b64>.<sig_b64>"
      }
    }
  }
}
```

`.codex/config.toml` (Codex):
```toml
[mcp_servers.fabric-server]
url = "http://127.0.0.1:8000/mcp"

[mcp_servers.fabric-server.headers]
Authorization = "fvmcp_rsa_<email_b64>.<sig_b64>"
```

No `Bearer` prefix — the `fvmcp_rsa_` prefix is itself the scheme identifier. The server checks for it directly.

## Key exchange (user ↔ admin)

This is the only manual step in the auth flow. It happens once per user (or whenever they rotate their key pair).

```mermaid
sequenceDiagram
    participant User
    participant Admin as MCP server admin

    User->>User: fabric-vibe auth refresh<br/>→ generates ~/.fabric-vibecoding/<email>.pem
    User-->>Admin: send ~/.fabric-vibecoding/<email>.pem<br/>(out of band: email, Slack, file share, etc.)
    Admin->>Admin: place <email>.pem in server/keys/
    Admin->>Admin: docker compose restart
    Admin-->>User: "your key is active"
    Note over User,Admin: MCP auth now works for this user.<br/>Re-run auth refresh any time to rotate the key<br/>(requires another exchange with the admin).
```

**What gets exchanged:** only the public key file (`<email>.pem`). The private key (`fabric-mcp-private-key.pem`) **never leaves the user's machine**.

**File name is the identity:** the PEM file is named `<email>.pem` — that filename is how the server binds the key to the user's email. The admin must not rename it.

## Server side — `SignedEmailTokenVerifier`

Implemented in `server/app.py`. Plugged into FastMCP's `TokenVerifier` interface.

```mermaid
sequenceDiagram
    participant Agent as Claude Code / Codex
    participant Server as fabric-server
    participant Verifier as SignedEmailTokenVerifier
    participant Keys as FABRIC_MCP_PUBLIC_KEYS_DIR/

    Agent->>Server: POST /mcp  Authorization: fvmcp_rsa_<email_b64>.<sig_b64>
    Server->>Verifier: verify_token(credential)
    Verifier->>Verifier: decode email from <email_b64>
    Verifier->>Keys: load <email>.pem for that email
    Verifier->>Verifier: RSA-PSS verify: does sig_b64 match <email_b64> bytes using this key?
    alt signature valid
        Verifier-->>Server: accepted (email used as client identity)
        Server-->>Agent: tool result
        Verifier->>Verifier: append "timestamp email" to FABRIC_MCP_EMAILS_FILE
    else bad signature, unknown email, or wrong format
        Server-->>Agent: 401 Unauthorized
    end
```

### Validation rules

- The credential claims email X; the server verifies the signature **using only the key registered under email X** — a credential signed by user B's private key cannot pass under user A's email.
- Accepted credentials are cached in memory for 300 seconds to avoid re-verifying on every call.
- Auth is **disabled entirely** when `FABRIC_MCP_PUBLIC_KEYS_DIR` is unset or empty.

## Server configuration

### docker-compose.yml

```yaml
services:
  server:
    environment:
      MCP_SERVER_URL: ${MCP_SERVER_URL:-http://127.0.0.1:8000}
      FABRIC_MCP_PUBLIC_KEYS_DIR: /keys
      FABRIC_MCP_EMAILS_FILE: /data/authenticated-emails.txt
    volumes:
      - ./keys:/keys:ro     # one <email>.pem per authorised user
      - ./data:/data        # audit log persisted on host
    ports:
      - "127.0.0.1:8000:8000"
```

`./keys/` is where the admin places the PEM files that users send after running `fabric-vibe auth refresh`. Adding a new user requires dropping their file and restarting the container (the key map is loaded at startup).

### Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `FABRIC_MCP_PUBLIC_KEYS_DIR` | _(unset)_ | Directory of `<email>.pem` files. Auth disabled when unset. |
| `FABRIC_MCP_EMAILS_FILE` | _(unset)_ | Append-only log of authenticated emails. Skipped when unset. |
| `MCP_SERVER_URL` | derived from `HOST`+`PORT` | Reported back in the FastMCP auth settings for client discovery. |
| `FABRIC_CORS_ORIGINS` | `*` | Comma-separated allowed CORS origins. Tighten for non-local deployments. |

## Setup flow (end to end)

`setup.sh` / `setup.ps1` runs `fabric-vibe auth refresh` during bootstrap:

1. Prompt for `FABRIC_MCP_USER_EMAIL`
2. Write `.mcp.json` with the MCP URL (no auth header yet)
3. Call `fabric-vibe auth refresh --email <email>`
   - generates / loads RSA key pair under `~/.fabric-vibecoding/`
   - signs the email, writes the signed string into the `Authorization` header field in `.mcp.json` and `.codex/config.toml` (no `Bearer` prefix)
   - prints the path to `~/.fabric-vibecoding/<email>.pem`
4. **Manual key exchange** — user sends `~/.fabric-vibecoding/<email>.pem` to the MCP server admin; admin places it in `server/keys/` and restarts the container (see [Key exchange (user ↔ admin)](#key-exchange-user--admin))
5. Reload Claude Code / Codex to pick up the new MCP config

## Audit logging

Every tool call is logged as a structured JSON line by `server/audit.py` (argument values replaced with a SHA-256 hash). Separately, each newly seen authenticated email is appended to `FABRIC_MCP_EMAILS_FILE`:

```
2026-05-27T20:00:00+00:00 you@example.com
```
