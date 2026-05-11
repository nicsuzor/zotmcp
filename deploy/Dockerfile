################################
# ZotMCP - FastMCP server for Zotero library search
# Built on buttermilk base image
#
# This image deliberately does NOT bundle the ChromaDB. The DB lives at
# gs://prosocial-dev/data/zotero-prosocial-fulltext/files (~11 GB) and is
# rsynced into a named volume at /chromadb on container start by
# deploy/sync-chromadb.sh. See deploy/run.sh for the runtime invocation.
################################

FROM us-central1-docker.pkg.dev/prosocial-443205/reg/buttermilk:dev

ARG PROJECT_NAME=zotmcp
WORKDIR /app/${PROJECT_NAME}

# Copy buttermilk source (local path dep) from named build context.
# Path must match [tool.uv.sources] in pyproject.toml: `../buttermilk` —
# i.e. one level above WORKDIR=/app/zotmcp. The ChromaDB is intentionally
# NOT copied; it is mounted at runtime and synced from GCS by
# /usr/local/bin/sync-chromadb.sh.
COPY --from=buttermilk_src . /app/buttermilk

# Copy dependency files and source code (needed by uv sync).
# uv.lock MUST be copied so `uv sync --locked` installs the exact resolved
# versions. Without it, uv resolves from scratch every build and can pull
# major version bumps (e.g. fastmcp 2.x → 3.x has a breaking lifespan API
# change that hangs uvicorn startup).
COPY pyproject.toml uv.lock ./
COPY src/ ./src/

# Install dependencies from the lock — fail the build if it's stale.
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked

# Set Python paths
ENV PYTHONPATH="/app/${PROJECT_NAME}/src:${PYTHONPATH}"
ENV PATH="/app/${PROJECT_NAME}/.venv/bin:$PATH"

# Default to stdio mode for MCP clients
ENV MODE=stdio

# Expose HTTP port (only used if MODE=http)
EXPOSE 8024

# Install entrypoint + sync helper. sync-chromadb.sh is also callable manually
# inside a running container via `docker exec <id> sync-chromadb` to force a refresh.
COPY deploy/entrypoint.sh /entrypoint.sh
COPY deploy/sync-chromadb.sh /usr/local/bin/sync-chromadb.sh
RUN chmod +x /entrypoint.sh /usr/local/bin/sync-chromadb.sh \
 && ln -s /usr/local/bin/sync-chromadb.sh /usr/local/bin/sync-chromadb

# Declare the ChromaDB mount point so docker creates an empty anonymous volume
# if the caller forgets to mount a named one — but the entrypoint will fail
# loud if the directory is empty after a (skipped) sync.
VOLUME ["/chromadb"]

ENTRYPOINT ["/entrypoint.sh"]
