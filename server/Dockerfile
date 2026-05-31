# syntax=docker/dockerfile:1.7

# ── build stage ───────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder
WORKDIR /build

RUN pip install --no-cache-dir --upgrade pip uv

# Project metadata + sources. Everything the server runs against lives under server/.
COPY pyproject.toml /build/pyproject.toml
COPY server /build/server

# Runtime deps only. We do NOT install ms-fabric-cli — fab-dependent tools
# live in cli/ and run on the user's laptop, not in this container.
# For FABRIC_MCP_API_KEYS_SOURCE=azure-blob, also add the 'server-azure' extra
# packages here: "azure-storage-blob>=12.19" "azure-identity>=1.16". They are
# omitted by default to keep the file-source image lean.
RUN uv pip install --system --no-cache \
    "mcp>=1.0" \
    "uvicorn>=0.30" \
    "pydantic>=2.7" \
    "networkx>=3.2" \
    "rank_bm25>=0.2.2" \
    "PyJWT>=2.8" \
    "sqlalchemy>=2.0"

# Build the knowledge graph from server/content + server/skills.
# Output: /build/dist/.graph/{graph.json, graph-bm25.pkl, materialized-graph.{html,svg}}
RUN python server/builders/build-graph.py --target . --stats

# ── runtime stage ─────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

RUN groupadd --system --gid 10001 server && \
    useradd  --system --uid 10001 --gid server --no-create-home --home /nonexistent server

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /build/server                /app/server
COPY --from=builder /build/dist/.graph           /app/dist/.graph

# Create managed content directories (volume-mounted at runtime for persistence).
RUN mkdir -p /app/server/managed/skills \
             /app/server/managed/content/rules \
             /app/server/managed/content/skill-fixes \
             /app/server/managed/content/memory && \
    chown -R server:server /app/server/managed

WORKDIR /app
USER server
EXPOSE 8000
ENV PYTHONUNBUFFERED=1 \
    PORT=8000 \
    HOST=0.0.0.0 \
    LOG_LEVEL=info \
    FABRIC_PROJECT_ROOT=/app \
    FABRIC_GRAPH_DIR=/app/dist/.graph

ENTRYPOINT ["python", "-m", "server"]
