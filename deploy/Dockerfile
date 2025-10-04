################################
# ZotMCP - FastMCP server for Zotero library search
# Built on buttermilk base image
################################

FROM us-central1-docker.pkg.dev/prosocial-443205/reg/buttermilk:latest

ARG PROJECT_NAME=zotmcp
ARG CACHE_DATE
WORKDIR /app/${PROJECT_NAME}

# Copy Zotero ChromaDB cache from local build context
COPY .cache/zotero-prosocial-fulltext .cache/zotero-prosocial-fulltext

# Install dependencies
COPY pyproject.toml ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync

# Copy application code
COPY src/ ./src/

# Copy configuration
COPY conf/ ./conf/

# Set Python paths
ENV PYTHONPATH="/app/${PROJECT_NAME}/src:/src/buttermilk:${PYTHONPATH}"
ENV PATH="/src/buttermilk/.venv/bin:/app/${PROJECT_NAME}/.venv/bin:$PATH"

# Default to stdio mode for MCP clients
ENV MODE=stdio

# Expose HTTP port (only used if MODE=http)
EXPOSE 8024

# Copy and set entrypoint
COPY deploy/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
