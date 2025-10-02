# syntax=docker/dockerfile:1.7
################################
# ZotMCP Container
# MCP server for Zotero library semantic search
################################

ARG BUTTERMILK_IMAGE=us-central1-docker.pkg.dev/prosocial-443205/reg/buttermilk:dev
ARG APP_PATH="/app/zotmcp"
ARG VENV_PATH="${APP_PATH}/.venv"
ARG GCS_CHROMADB_PATH="gs://prosocial-dev/data/zotero-prosocial-fulltext/files"

################################
# BASE - Use Buttermilk container for dependencies
################################
FROM ${BUTTERMILK_IMAGE} AS base

################################
# CHROMADB-DOWNLOADER - Use host's gcloud to download ChromaDB
# This runs on the host machine using your credentials
################################
FROM google/cloud-sdk:slim AS chromadb-downloader
ARG GCS_CHROMADB_PATH
ARG CACHE_DATE
ARG APP_PATH="/app/zotmcp"

WORKDIR ${APP_PATH}

# Download ChromaDB from GCS using host's gcloud credentials
# The --mount=type=bind mounts your ~/.config/gcloud from host (read-only)
RUN --mount=type=bind,source=/home/nic/.config/gcloud,target=/root/.config/gcloud,readonly \
    mkdir -p .cache/zotero-prosocial-fulltext && \
    gsutil -m cp -r ${GCS_CHROMADB_PATH} .cache/zotero-prosocial-fulltext/ && \
    echo "✅ ChromaDB downloaded successfully (cache date: ${CACHE_DATE})"

################################
# CHROMADB - Static layer with downloaded data
# This layer is cached monthly and only rebuilds if CACHE_DATE changes
################################
FROM scratch AS chromadb-layer
ARG APP_PATH="/app/zotmcp"

# Copy the downloaded ChromaDB from the downloader stage
COPY --from=chromadb-downloader ${APP_PATH}/.cache ${APP_PATH}/.cache

################################
# BUILDER - Install zotmcp dependencies
################################
FROM base AS builder
ARG APP_PATH
ARG VENV_PATH

WORKDIR /tmp/build

# Copy only requirements first for layer caching
COPY pyproject.toml ./

# Create minimal requirements.txt from pyproject.toml
RUN python -c "import tomllib; \
    data = tomllib.load(open('pyproject.toml', 'rb')); \
    deps = data['project']['dependencies']; \
    print('\n'.join(deps))" > requirements.txt

# Install zotmcp dependencies into new venv
RUN --mount=type=cache,target=/root/.cache/uv \
    uv venv ${VENV_PATH} --seed && \
    . ${VENV_PATH}/bin/activate && \
    uv pip install -r requirements.txt

################################
# FINAL - Runtime image
################################
FROM base AS zotmcp
ARG APP_PATH
ARG VENV_PATH

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="${VENV_PATH}/bin:$PATH"

# Create app directory
RUN mkdir -p ${APP_PATH}
WORKDIR ${APP_PATH}

# Copy ChromaDB from cached layer (early - won't change often)
COPY --from=chromadb-layer ${APP_PATH}/.cache ${APP_PATH}/.cache

# Copy venv from builder
COPY --from=builder ${VENV_PATH} ${VENV_PATH}

# Copy application code (late - changes frequently)
COPY src/ ${APP_PATH}/src/
COPY conf/ ${APP_PATH}/conf/
COPY templates/ ${APP_PATH}/templates/

# Copy startup script
COPY containers/deploy/startup.sh /usr/local/bin/startup.sh
RUN chmod +x /usr/local/bin/startup.sh

# Expose port for HTTP mode (optional)
EXPOSE 8024

# Default: Run in stdio mode for MCP
CMD ["/usr/local/bin/startup.sh"]
