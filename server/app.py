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


def build_app():
    """Construct the FastMCP app, register every tool, return the ASGI app.

    Auth is enabled when the configured key source (FABRIC_MCP_API_KEYS_SOURCE:
    file or azure-blob) or FABRIC_MCP_API_KEYS yields at least one valid API key.
    Clients call POST /auth/login with {"api_key": "..."}
    to receive a 1-hour JWT. The JWT must be presented as Authorization: Bearer <token>
    on every subsequent request. Clients refresh via POST /auth/refresh (old JTI is
    revoked, blocking replay of the superseded token). When no API keys are configured
    the server accepts all requests — suitable for local single-user dev.

    The admin REST API lives at /api/v1/* and is mounted in a parent Starlette app
    alongside the MCP app so both share auth + CORS middleware.
    """
    # FastMCP defaults DNS rebinding protection to enabled with only localhost
    # in the allowed-hosts list. Behind a reverse proxy (nginx), the Host header
    # is the public domain, not localhost — so any /mcp request from outside would
    # get a 421. Extend the list with the configured public hostname.
    _allowed_hosts = ["127.0.0.1:*", "localhost:*", "[::1]:*", "testserver"]
    server_url = os.environ.get("MCP_SERVER_URL", "").strip().rstrip("/")
    if server_url:
        parsed_host = urlparse(server_url).hostname or ""
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

    # Starlette 1.x _DefaultLifespan is a no-op — mounted sub-apps' lifespans are
    # no longer called automatically. Wire the MCP session manager explicitly so
    # POST /mcp doesn't crash with "Task group is not initialized. Make sure to use run()."
    @asynccontextmanager
    async def _lifespan(app: Starlette):
        async with mcp.session_manager.run():
            yield

    async def _root_redirect(request: Request) -> RedirectResponse:
        return RedirectResponse(url="/api/v1/docs")

    # RFC 9728 Protected Resource Metadata — tells MCP 2025-03-26 clients that
    # this server uses Bearer token auth with no OAuth2 authorization server.
    # Clients probe this after getting 401 + WWW-Authenticate: Bearer and use
    # the pre-configured Bearer token from their .mcp.json instead of OAuth2.
    async def _protected_resource_metadata(request: Request) -> JSONResponse:
        server_url = os.environ.get("MCP_SERVER_URL", "").strip().rstrip("/")
        if not server_url:
            # Derive from request headers when MCP_SERVER_URL is not set.
            headers = dict(request.headers)
            proto = headers.get("x-forwarded-proto", "https")
            host = headers.get("host", "localhost")
            server_url = f"{proto}://{host}"
        return JSONResponse(
            {
                "resource": server_url,
                "bearer_methods_supported": ["header"],
                "resource_documentation": f"{server_url}/api/v1/docs",
            },
            headers={"Cache-Control": "no-store"},
        )

    # Parent Starlette app: /api routes handled directly, everything else forwarded to MCP.
    # Route("/") must appear before Mount("/") so an exact GET / match redirects to docs.
    # /health is unauthenticated (used by Docker healthcheck).
    # /auth/* routes are fallbacks when auth middleware is not installed; when the
    # middleware IS installed it intercepts these paths before routing.
    app = Starlette(
        routes=[
            Route("/", _root_redirect, methods=["GET"]),
            Route("/health", _health, methods=["GET"]),
            Route("/auth/login", _auth_disabled, methods=["POST"]),
            Route("/auth/refresh", _auth_disabled, methods=["POST"]),
            Route("/.well-known/oauth-protected-resource", _protected_resource_metadata, methods=["GET"]),
            Mount("/api", routes=make_routes()),
            Mount("/", app=mcp_app),
        ],
        lifespan=_lifespan,
    )

    # FabricAuthMiddleware added first (inner); CORSMiddleware added last (outermost).
    install_auth_middleware(app)

    origins_raw = os.environ.get("FABRIC_CORS_ORIGINS", "").strip()
    # Default deny-all when not configured. Set FABRIC_CORS_ORIGINS=* only for
    # single-user local dev without authentication.
    allow_origins = [o.strip() for o in origins_raw.split(",") if o.strip()] if origins_raw else []
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept"],
        expose_headers=["Mcp-Session-Id"],
    )
    return app
