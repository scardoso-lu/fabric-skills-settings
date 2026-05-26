"""FastMCP app builder.

The server exposes graph, content, validate, data, and semantic-model
(uses sempy.fabric python lib). Fabric-CLI-dependent helpers plus the
deterministic lints and pre-commit aggregator live in cli/ and run on the
user's laptop as plain CLI commands (Claude invokes them via Bash).
"""

from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP
from starlette.middleware.cors import CORSMiddleware

from .tools.data import tools as data_tools
from .tools.graph import tools as graph_tools
from .tools.semantic_model import tools as semantic_model_tools
from .tools.validate import tools as validate_tools


def build_app():
    """Construct the FastMCP app, register every tool, return the ASGI app.

    Returned object is suitable for ``uvicorn.run(app, ...)``.

    Wraps the streamable-HTTP app with CORS middleware so browser-style MCP
    clients (which send OPTIONS preflight before POST) can connect. Allowed
    origins are configurable via FABRIC_CORS_ORIGINS (comma-separated);
    defaults to "*" for local dev — tighten for any deployment beyond
    127.0.0.1.
    """
    mcp = FastMCP("fabric-server")
    graph_tools.register(mcp)
    semantic_model_tools.register(mcp)
    validate_tools.register(mcp)
    data_tools.register(mcp)

    app = mcp.streamable_http_app()
    origins_raw = os.environ.get("FABRIC_CORS_ORIGINS", "*").strip()
    allow_origins = [o.strip() for o in origins_raw.split(",") if o.strip()] or ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["Mcp-Session-Id"],
    )
    return app
