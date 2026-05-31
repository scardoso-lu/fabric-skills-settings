"""FastMCP app builder.

The server exposes graph, content, validate, data, and semantic-model
(uses sempy.fabric python lib). Fabric-CLI-dependent helpers plus the
deterministic lints and pre-commit aggregator live in cli/ and run on the
user's laptop as plain CLI commands (Claude invokes them via Bash).

Authentication (API-key sourcing, JWT, and the ASGI middleware) lives in
``server/auth``; this module only wires it onto the app.

The admin REST API (``/api/v1/*``) is mounted alongside the MCP app in a
parent Starlette app so both share the same auth and CORS middleware stack.
"""

from __future__ import annotations

import base64
import os
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from mcp.server.fastmcp import FastMCP
from mcp.server.streamable_http import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse
from starlette.routing import Mount, Route

from .api.routes import make_routes
from .auth import install_auth_middleware
from .auth.tokens import mint_jwt
from .tools.data import tools as data_tools
from .tools.graph import tools as graph_tools
from .tools.semantic_model import tools as semantic_model_tools
from .tools.validate import tools as validate_tools


async def _health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


async def _auth_disabled(request: Request) -> JSONResponse:
    return JSONResponse(
        {"error": "auth_not_configured",
         "message": "Authentication is not enabled on this server. "
                    "Set FABRIC_MCP_API_KEYS (and FABRIC_MCP_JWT_SECRET) to enable it."},
        status_code=503,
    )


def _server_url(request: Request) -> str:
    """Derive the public server URL from env or request headers."""
    configured = os.environ.get("MCP_SERVER_URL", "").strip().rstrip("/")
    if configured:
        return configured
    proto = request.headers.get("x-forwarded-proto", "https")
    host = request.headers.get("host", "localhost")
    return f"{proto}://{host}"


def build_app():
    """Construct the FastMCP app, register every tool, return the ASGI app.

    Auth is enabled when FABRIC_MCP_API_KEYS or FABRIC_MCP_API_KEYS_DB yield
    at least one valid API key. Clients exchange an API key for a 1-hour JWT
    via POST /auth/login (JSON body) or POST /oauth/token (OAuth2 client
    credentials). The JWT must be presented as Authorization: Bearer <token>
    on every subsequent request. When no keys are configured the server accepts
    all requests — suitable for local single-user dev.

    MCP clients that follow the 2025-03-26 spec discover auth via:
      GET /.well-known/oauth-protected-resource  → points to our OAuth2 AS
      GET /.well-known/oauth-authorization-server → token_endpoint + grant types
      POST /oauth/token (grant_type=client_credentials, client_id=<api_key>)

    The admin REST API lives at /api/v1/* alongside the MCP app.
    """
    # FastMCP defaults DNS rebinding protection to only localhost. Behind nginx
    # the Host header is the public domain — extend allowed_hosts from MCP_SERVER_URL.
    _allowed_hosts = ["127.0.0.1:*", "localhost:*", "[::1]:*", "testserver"]
    server_url_env = os.environ.get("MCP_SERVER_URL", "").strip().rstrip("/")
    if server_url_env:
        parsed_host = urlparse(server_url_env).hostname or ""
        if parsed_host and parsed_host not in _allowed_hosts:
            _allowed_hosts.append(parsed_host)
            _allowed_hosts.append(f"{parsed_host}:*")

    mcp = FastMCP(
        "fabric-server",
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=_allowed_hosts,
        ),
    )
    graph_tools.register(mcp)
    semantic_model_tools.register(mcp)
    validate_tools.register(mcp)
    data_tools.register(mcp)

    mcp_app = mcp.streamable_http_app()

    # Starlette 1.x _DefaultLifespan is a no-op — mounted sub-apps' lifespans
    # are no longer auto-called. Wire the MCP session manager explicitly.
    @asynccontextmanager
    async def _lifespan(app: Starlette):
        async with mcp.session_manager.run():
            yield

    async def _root_redirect(request: Request) -> RedirectResponse:
        return RedirectResponse(url="/api/v1/docs")

    # ── OAuth2 / MCP auth discovery ───────────────────────────────────────────

    # RFC 9728 — Protected Resource Metadata.
    # Points MCP clients at our OAuth2 AS so they can obtain tokens automatically
    # without needing `fabric-vibe auth refresh` to pre-populate config files.
    async def _protected_resource_metadata(request: Request) -> JSONResponse:
        base = _server_url(request)
        return JSONResponse(
            {
                "resource": base,
                "authorization_servers": [base],
                "bearer_methods_supported": ["header"],
                "resource_documentation": f"{base}/api/v1/docs",
            },
            headers={"Cache-Control": "no-store"},
        )

    # RFC 8414 — OAuth2 Authorization Server Metadata.
    # Tells MCP clients where to get tokens (client_credentials grant).
    # Token endpoint is advertised under /server/ so existing nginx routing
    # (location /server/ → fabric-mcp-server:8000/) handles it without any
    # additional nginx configuration.
    async def _oauth_as_metadata(request: Request) -> JSONResponse:
        base = _server_url(request)
        # /server/oauth/token → nginx strips /server/ → backend /oauth/token
        token_ep = f"{base}/server/oauth/token"
        return JSONResponse(
            {
                "issuer": base,
                "token_endpoint": token_ep,
                "grant_types_supported": ["client_credentials"],
                "token_endpoint_auth_methods_supported": ["client_secret_post", "none"],
                "response_types_supported": ["token"],
            },
            headers={"Cache-Control": "no-store"},
        )

    # RFC 6749 §4.4 — Client Credentials Grant.
    # Accepts:
    #   application/x-www-form-urlencoded  (standard OAuth2 clients, codex mcp login)
    #   application/json                    (fabric-vibe auth refresh and CLI tools)
    # The "client credential" is the API key — pass it as either client_id (no
    # client_secret needed) or as client_secret (with any client_id).
    # Also accepts Authorization: Basic base64(client_id:api_key).
    async def _oauth_token(request: Request) -> JSONResponse:
        # Access auth objects stored by install_auth_middleware.
        key_store = getattr(request.app.state, "api_key_store", None)
        jti_store_ = getattr(request.app.state, "jti_store", None)
        secret = getattr(request.app.state, "jwt_secret", None)

        if not key_store or not jti_store_ or not secret:
            return JSONResponse(
                {"error": "server_error",
                 "error_description": "Auth not configured on this server"},
                status_code=503,
            )

        # Parse credentials from body or Authorization header.
        content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
        grant_type = client_id = client_secret = ""

        if content_type == "application/x-www-form-urlencoded":
            try:
                form = await request.form()
                grant_type = form.get("grant_type", "")
                client_id = form.get("client_id", "")
                client_secret = form.get("client_secret", "")
            except Exception:
                return JSONResponse({"error": "invalid_request"}, status_code=400)
        else:
            # JSON body (our own CLI) or empty body.
            try:
                body_bytes = await request.body()
                if body_bytes.strip():
                    import json as _json
                    body = _json.loads(body_bytes)
                    grant_type = body.get("grant_type", "client_credentials")
                    client_id = body.get("client_id", body.get("api_key", ""))
                    client_secret = body.get("client_secret", "")
                else:
                    grant_type = "client_credentials"
            except Exception:
                return JSONResponse({"error": "invalid_request"}, status_code=400)

        # Authorization: Basic base64(client_id:client_secret) — RFC 6749 §2.3.1
        auth_header = request.headers.get("authorization", "")
        if auth_header.lower().startswith("basic "):
            try:
                decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
                basic_id, _, basic_secret = decoded.partition(":")
                client_id = client_id or basic_id
                client_secret = client_secret or basic_secret
            except Exception:
                pass

        if grant_type and grant_type != "client_credentials":
            return JSONResponse(
                {"error": "unsupported_grant_type",
                 "error_description": "Only client_credentials is supported"},
                status_code=400,
            )

        # The API key may come from client_secret (with email as client_id) or
        # from client_id directly (no client_secret — the "none" auth method).
        api_key = (client_secret or client_id).strip()
        if not api_key:
            return JSONResponse(
                {"error": "invalid_client",
                 "error_description": "Provide your API key as client_id or client_secret"},
                status_code=401,
                headers={"WWW-Authenticate": 'Bearer error="invalid_client"'},
            )

        if api_key not in key_store:
            return JSONResponse(
                {"error": "invalid_client",
                 "error_description": "Invalid API key"},
                status_code=401,
                headers={"WWW-Authenticate": 'Bearer error="invalid_client"'},
            )

        token, expiry = mint_jwt("client", secret, jti_store_)
        return JSONResponse(
            {
                "access_token": token,
                "token_type": "bearer",
                "expires_in": 3600,
                "expires_at": expiry,  # extra field for fabric-vibe compat
            },
            headers={"Cache-Control": "no-store"},
        )

    # ── Starlette app ─────────────────────────────────────────────────────────

    app = Starlette(
        routes=[
            Route("/", _root_redirect, methods=["GET"]),
            Route("/health", _health, methods=["GET"]),
            # OAuth2 discovery (unauthenticated — bypassed by FabricAuthMiddleware)
            Route("/.well-known/oauth-protected-resource", _protected_resource_metadata, methods=["GET"]),
            Route("/.well-known/oauth-authorization-server", _oauth_as_metadata, methods=["GET"]),
            Route("/oauth/token", _oauth_token, methods=["POST"]),
            # Legacy JSON auth endpoint (also handled by FabricAuthMiddleware when
            # auth is enabled; these fallbacks fire only when auth is disabled).
            Route("/auth/login", _auth_disabled, methods=["POST"]),
            Route("/auth/refresh", _auth_disabled, methods=["POST"]),
            Mount("/api", routes=make_routes()),
            Mount("/", app=mcp_app),
        ],
        lifespan=_lifespan,
    )

    # FabricAuthMiddleware added first (inner); CORSMiddleware added last (outermost).
    install_auth_middleware(app)

    origins_raw = os.environ.get("FABRIC_CORS_ORIGINS", "").strip()
    allow_origins = [o.strip() for o in origins_raw.split(",") if o.strip()] if origins_raw else []
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept"],
        expose_headers=["Mcp-Session-Id"],
    )
    return app
