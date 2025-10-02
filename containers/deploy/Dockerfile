# syntax=docker/dockerfile:1.7
################################
# ZotMCP Container
# MCP server for Zotero library semantic search
################################

ARG BUTTERMILK_IMAGE=us-central1-docker.pkg.dev/prosocial-443205/reg/buttermilk:dev
ARG APP_PATH="/app/zotmcp"
ARG VENV_PATH="${APP_PATH}/.venv"

################################
# BASE - Use Buttermilk container for dependencies
################################
FROM ${BUTTERMILK_IMAGE} AS base

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

# Copy venv from builder
COPY --from=builder ${VENV_PATH} ${VENV_PATH}

# Copy application code
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
