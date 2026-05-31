#!/usr/bin/env python3
"""Fetch a short-lived JWT from the MCP server using an API key.

Saves the JWT into the Claude and Codex MCP client configuration files so
Claude Code and Codex pick it up on next session load. The token is reused
until close to expiry, then refreshed automatically. Run `fabric-vibe auth
refresh` any time you need a fresh token.

The API key is read from FABRIC_MCP_API_KEY. If that variable is not set,
the command prompts for it interactively (input is hidden).

The auth service base URL is read from FABRIC_MCP_AUTH_URL (e.g.
https://host/server/auth). If not set, it defaults to
{MCP_SERVER_URL}/api/auth. Pass --auth-url to override at runtime.

Usage:
    fabric-vibe auth refresh [--server-url https://host:port]
                             [--auth-url   https://host/path/auth]
"""

from __future__ import annotations

import base64
import getpass
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path.cwd()

_STATE_DIR = Path.home() / ".fabric-vibecoding"
_TOKEN_FILE = _STATE_DIR / "mcp-token.json"
_REFRESH_MARGIN = 300  # refresh when fewer than 5 min remain


# ── JWT expiry helper (no external deps) ─────────────────────────────────────

def _jwt_expiry(token: str) -> float | None:
    """Extract the exp claim from a JWT payload without verifying the signature."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        padding = "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + padding).decode("utf-8"))
        return float(payload["exp"])
    except Exception:
        return None


# ── Persisted token ───────────────────────────────────────────────────────────

def _load_saved_token() -> tuple[str, float] | tuple[None, None]:
    if not _TOKEN_FILE.exists():
        return None, None
    try:
        data = json.loads(_TOKEN_FILE.read_text(encoding="utf-8"))
        return data.get("token"), float(data.get("expires_at", 0))
    except Exception:
        return None, None


def _save_token(token: str, expires_at: float) -> None:
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    _TOKEN_FILE.write_text(
        json.dumps({"token": token, "expires_at": expires_at}), encoding="utf-8"
    )
    try:
        os.chmod(_TOKEN_FILE, 0o600)
    except OSError:
        pass


# ── URL resolution ────────────────────────────────────────────────────────────

def _resolve_server_url(argv: list[str], root: Path) -> str:
    """Resolve MCP server base URL from --server-url arg, env, or .mcp.json."""
    if "--server-url" in argv:
        idx = argv.index("--server-url")
        if idx + 1 < len(argv):
            return argv[idx + 1].rstrip("/")
    url = os.environ.get("MCP_SERVER_URL", "").strip().rstrip("/")
    if url:
        return url
    mcp_json = root / ".mcp.json"
    if mcp_json.exists():
        try:
            doc = json.loads(mcp_json.read_text(encoding="utf-8-sig"))
            raw = doc.get("mcpServers", {}).get("fabric-server", {}).get("url", "")
            if raw:
                return raw.rstrip("/").removesuffix("/mcp")
        except Exception:
            pass
    return "http://127.0.0.1:8000"


def _resolve_auth_base_url(argv: list[str], server_url: str) -> str:
    """Resolve auth service base URL.

    Priority: --auth-url flag > FABRIC_MCP_AUTH_URL env var > {server_url}/api/auth.

    The base URL is the path up to but not including /login or /refresh,
    e.g. https://host/server/auth or https://host/api/auth.
    """
    if "--auth-url" in argv:
        idx = argv.index("--auth-url")
        if idx + 1 < len(argv):
            return argv[idx + 1].rstrip("/")
    url = os.environ.get("FABRIC_MCP_AUTH_URL", "").strip().rstrip("/")
    if url:
        return url
    return f"{server_url}/api/auth"


# ── API key resolution ────────────────────────────────────────────────────────

def _prompt_api_key() -> str | None:
    """Return the API key from env or an interactive prompt. Returns None to skip."""
    key = os.environ.get("FABRIC_MCP_API_KEY", "").strip()
    if key:
        return key
    print("  FABRIC_MCP_API_KEY is not set.")
    try:
        key = getpass.getpass("  Enter your MCP API key (empty to skip): ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    return key or None


# ── Token fetch / refresh ─────────────────────────────────────────────────────

def _post(url: str, body: bytes, headers: dict[str, str]) -> tuple[int, dict]:
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read().decode("utf-8"))
        except Exception:
            return exc.code, {"error": exc.reason}
    except Exception as exc:
        raise SystemExit(f"Cannot reach MCP server at {url}: {exc}") from exc


def _fetch_token(auth_base_url: str, api_key: str) -> tuple[str, float]:
    """POST to {auth_base_url}/login, return (jwt, expires_at). Exits on failure."""
    login_url = f"{auth_base_url}/login"
    status, body = _post(
        login_url,
        json.dumps({"api_key": api_key}).encode("utf-8"),
        {"Content-Type": "application/json"},
    )
    if status == 404:
        raise SystemExit(
            f"Server returned 404 for {login_url} — auth may be disabled on this server.\n"
            "Check FABRIC_MCP_API_KEY, MCP_SERVER_URL, and FABRIC_MCP_AUTH_URL."
        )
    if status != 200:
        raise SystemExit(f"Login failed ({status}): {body.get('error', body)}")
    token = body.get("token", "")
    if not token:
        raise SystemExit(f"Server returned no token: {body}")
    expires_at = body.get("expires_at") or _jwt_expiry(token) or (time.time() + 3600)
    return token, float(expires_at)


def _refresh_token(auth_base_url: str, current_token: str) -> tuple[str, float] | tuple[None, None]:
    """POST to {auth_base_url}/refresh. Returns (new_token, expires_at) or (None, None)."""
    status, body = _post(
        f"{auth_base_url}/refresh",
        b"",
        {"Content-Type": "application/json", "Authorization": f"Bearer {current_token}"},
    )
    if status != 200:
        return None, None
    token = body.get("token", "")
    if not token:
        return None, None
    expires_at = body.get("expires_at") or _jwt_expiry(token) or (time.time() + 3600)
    return token, float(expires_at)


# ── Config injection ──────────────────────────────────────────────────────────

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
        if 'Authorization = "Bearer' not in text:
            text = re.sub(
                r"(\[mcp_servers\.fabric-server\.headers\])",
                rf"\1\n{auth_line}",
                text,
            )
    else:
        text = text.rstrip() + f"\n\n[mcp_servers.fabric-server.headers]\n{auth_line}\n"
    config.write_text(text, encoding="utf-8")
    print("  Updated .codex/config.toml")


# ── Entry point ───────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    api_key = _prompt_api_key()
    if not api_key:
        print("  No API key provided — skipping auth.")
        return 0

    server_url = _resolve_server_url(argv, ROOT)
    auth_base_url = _resolve_auth_base_url(argv, server_url)
    token: str | None = None
    expires_at: float = 0.0

    saved_token, saved_expiry = _load_saved_token()
    if saved_token and saved_expiry:
        time_left = saved_expiry - time.time()
        if time_left > _REFRESH_MARGIN:
            token, expires_at = saved_token, saved_expiry
            print(f"  Reusing existing token (expires in {int(time_left // 60)} min)")
        elif time_left > 0:
            new_tok, new_exp = _refresh_token(auth_base_url, saved_token)
            if new_tok:
                token, expires_at = new_tok, new_exp  # type: ignore[assignment]
                print(f"  Token refreshed via {auth_base_url}/refresh")

    if not token:
        token, expires_at = _fetch_token(auth_base_url, api_key)
        print("  New JWT obtained from MCP server")

    _save_token(token, expires_at)
    update_mcp_json(ROOT, token)
    update_codex_config(ROOT, token)

    expiry_str = datetime.fromtimestamp(expires_at).strftime("%Y-%m-%d %H:%M:%S")
    print(f"\nMCP token written to client config. Expires: {expiry_str}")
    print("Reload your Claude Code / Codex session to pick up the new token.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
