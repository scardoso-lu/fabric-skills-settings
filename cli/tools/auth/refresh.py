#!/usr/bin/env python3
"""Fetch a short-lived JWT from the MCP server using FABRIC_MCP_API_KEY.

Saves the JWT into the Claude and Codex MCP client configuration files so
Claude Code and Codex pick it up on next session load. The token is reused
until close to expiry, then refreshed automatically. Run `fabric-vibe auth
refresh` any time you need a fresh token.

Usage:
    fabric-vibe auth refresh [--server-url https://host:port]
"""

from __future__ import annotations

import base64
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


# ── Server URL resolution ─────────────────────────────────────────────────────

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


def _fetch_token(server_url: str, api_key: str) -> tuple[str, float]:
    """POST to /auth/login, return (jwt, expires_at). Exits on failure."""
    status, body = _post(
        f"{server_url}/auth/login",
        json.dumps({"api_key": api_key}).encode("utf-8"),
        {"Content-Type": "application/json"},
    )
    if status == 404:
        raise SystemExit(
            "Server returned 404 for /auth/login — auth may be disabled on this server.\n"
            "If the server requires authentication, check FABRIC_MCP_API_KEY and MCP_SERVER_URL."
        )
    if status != 200:
        raise SystemExit(f"Login failed ({status}): {body.get('error', body)}")
    token = body.get("token", "")
    if not token:
        raise SystemExit(f"Server returned no token: {body}")
    expires_at = body.get("expires_at") or _jwt_expiry(token) or (time.time() + 3600)
    return token, float(expires_at)


def _refresh_token(server_url: str, current_token: str) -> tuple[str, float] | tuple[None, None]:
    """POST to /auth/refresh. Returns (new_token, expires_at) or (None, None) on failure."""
    status, body = _post(
        f"{server_url}/auth/refresh",
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

    api_key = os.environ.get("FABRIC_MCP_API_KEY", "").strip()
    if not api_key:
        print(
            "  FABRIC_MCP_API_KEY is not set.\n"
            "  If your MCP server requires authentication, ask the admin for an API key\n"
            "  and set it in your shell profile:\n"
            "    export FABRIC_MCP_API_KEY=<key>\n"
            "  then re-run: fabric-vibe auth refresh\n"
            "  If running locally without server auth, no token is needed."
        )
        return 0

    server_url = _resolve_server_url(argv, ROOT)
    token: str | None = None
    expires_at: float = 0.0

    saved_token, saved_expiry = _load_saved_token()
    if saved_token and saved_expiry:
        time_left = saved_expiry - time.time()
        if time_left > _REFRESH_MARGIN:
            token, expires_at = saved_token, saved_expiry
            print(f"  Reusing existing token (expires in {int(time_left // 60)} min)")
        elif time_left > 0:
            new_tok, new_exp = _refresh_token(server_url, saved_token)
            if new_tok:
                token, expires_at = new_tok, new_exp  # type: ignore[assignment]
                print("  Token refreshed via /auth/refresh")

    if not token:
        token, expires_at = _fetch_token(server_url, api_key)
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
