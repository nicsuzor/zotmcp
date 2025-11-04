#!/bin/bash
# Generic entrypoint for FastMCP applications
#
# Supports two modes:
# - stdio (default): For MCP client integration
# - http: Run as HTTP server on port 8024
#
# Set MODE environment variable to switch modes

# Parse hydra overrides from environment variable
HYDRA_ARGS=""
if [ -n "$HYDRA_OVERRIDES" ]; then
  HYDRA_ARGS="$HYDRA_OVERRIDES"
fi

if [ "$MODE" = "http" ]; then
  echo "Starting MCP server in HTTP mode on port 8024..." >&2
  exec python src/main.py $HYDRA_ARGS
else
  echo "Starting MCP server in stdio mode for MCP clients..." >&2
  exec fastmcp run src/main.py $HYDRA_ARGS
fi
