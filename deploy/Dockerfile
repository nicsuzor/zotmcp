################################
# ZotMCP - FastMCP server for Zotero library search
# Built on buttermilk base image
################################

FROM us-central1-docker.pkg.dev/prosocial-443205/reg/buttermilk:dev

ARG PROJECT_NAME=zotmcp
ARG CACHE_DATE
WORKDIR /app/${PROJECT_NAME}

# Copy Zotero ChromaDB cache from local build context
COPY --from=cache . /chromadb

# Copy dependency metadata first (for caching)
COPY pyproject.toml ./

# Install dependencies without the project package
# This layer will be cached unless dependencies change
RUN --mount=type=cache,target=/root/.cache/uv uv sync --no-install-project

# Update buttermilk (it changes frequently in development)
# Do this before copying source so source changes don't force buttermilk reinstall
RUN uv sync --no-cache --reinstall-package buttermilk

# NOW copy source code (changing this won't invalidate dependency layers above)
COPY src/ ./src/

# Install only the local package (fast, since deps already installed)
RUN uv pip install --no-deps -e .

# Copy configuration
COPY conf/ ./conf/

# Set Python paths
ENV PYTHONPATH="/app/${PROJECT_NAME}/src:${PYTHONPATH}"
ENV PATH="/app/${PROJECT_NAME}/.venv/bin:$PATH"

# Default to stdio mode for MCP clients
ENV MODE=stdio

# Expose HTTP port (only used if MODE=http)
EXPOSE 8024

# Copy and set entrypoint
COPY deploy/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
