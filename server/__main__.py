"""Uvicorn entrypoint — ``python -m server``.

Reads ``PORT`` (default 8000) and binds to ``0.0.0.0`` so it's reachable
from outside the container. Local-only deploys should map the port to
``127.0.0.1`` on the host to avoid LAN exposure.
"""

from __future__ import annotations

import logging
import os
import sys

import uvicorn

from .app import build_app

_LEVEL_MAP = {
    "critical": logging.CRITICAL,
    "error": logging.ERROR,
    "warning": logging.WARNING,
    "warn": logging.WARNING,
    "info": logging.INFO,
    "debug": logging.DEBUG,
}


def main() -> int:
    port = int(os.environ.get("PORT", "8000"))
    host = os.environ.get("HOST", "0.0.0.0")
    log_level = os.environ.get("LOG_LEVEL", "info").lower()

    # Configure the root logger BEFORE uvicorn.run() calls dictConfig().
    # Uvicorn's dictConfig uses disable_existing_loggers=False, so this handler
    # is preserved. Without this, server.* module loggers have no handler and
    # all messages are silently dropped.
    logging.basicConfig(
        level=_LEVEL_MAP.get(log_level, logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        stream=sys.stderr,
    )

    app = build_app()
    logging.getLogger(__name__).info("fabric-server starting on http://%s:%d", host, port)
    uvicorn.run(app, host=host, port=port, log_level=log_level)
    return 0


if __name__ == "__main__":
    sys.exit(main())
