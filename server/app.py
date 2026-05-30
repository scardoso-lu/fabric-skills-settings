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

from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse
from starlette.routing import Mount, Route

from .api.routes import make_routes
from .auth import install_auth_middleware
from .tools.data import tools as data_tools
from .tools.graph import tools as graph_tools
from .tools.semantic_model import tools as semantic_model_tools
from .tools.validate import tools as validate_tools


def _resource_server_url() -> str:
    configured = os.environ.get("MCP_SERVER_URL", "").strip().rstrip("/")
    if configured:
        return configured
    host = os.environ.get("HOST", "127.0.0.1").strip() or "127.0.0.1"
    port = os.environ.get("PORT", "8000").strip() or "8000"
    public_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    return f"http://{public_host}:{port}"


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
    mcp = FastMCP("fabric-server")
    graph_tools.register(mcp)
    semantic_model_tools.register(mcp)
    validate_tools.register(mcp)
    data_tools.register(mcp)

    mcp_app = mcp.streamable_http_app()

    async def _root_redirect(request: Request) -> RedirectResponse:
        return RedirectResponse(url="/api/v1/docs")

    # Parent Starlette app: /api routes handled directly, everything else forwarded to MCP.
    # Route("/") must appear before Mount("/") so an exact GET / match redirects to docs.
    app = Starlette(routes=[
        Route("/", _root_redirect, methods=["GET"]),
        Mount("/api", routes=make_routes()),
        Mount("/", app=mcp_app),
    ])

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
