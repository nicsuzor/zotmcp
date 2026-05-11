#!/bin/bash
# Generic entrypoint for the ZotMCP FastMCP server.
#
# Responsibilities:
# 1. Sync the ChromaDB named volume against the GCS source of truth
#    (skippable with ZOTMCP_SKIP_SYNC=1; fail-loud if the volume is empty).
# 2. Launch the MCP server in stdio (default) or http mode (MODE=http).
#
# Required runtime mounts/env:
# - A writable named volume at /chromadb (see deploy/run.sh).
# - gcloud creds: either a mounted ~/.config/gcloud or
#   GOOGLE_APPLICATION_CREDENTIALS pointing at a service-account JSON.
# - GCP auth is needed for *both* the GCS rsync and Vertex AI query embedding,
#   so there is no read-only mode that avoids these credentials.

set -eu -o pipefail

if [ "${ZOTMCP_SKIP_SYNC:-0}" = "1" ]; then
  echo "⏩ ZOTMCP_SKIP_SYNC=1 — skipping ChromaDB sync at startup." >&2
  if [ -z "$(ls -A /chromadb 2>/dev/null || true)" ]; then
    echo "❌ /chromadb is empty and sync is disabled. Mount a populated volume or unset ZOTMCP_SKIP_SYNC." >&2
    exit 1
  fi
else
  /usr/local/bin/sync-chromadb.sh
fi

# Parse hydra overrides from environment variable
HYDRA_ARGS=""
if [ -n "${HYDRA_OVERRIDES:-}" ]; then
  HYDRA_ARGS="$HYDRA_OVERRIDES"
fi

if [ "${MODE:-stdio}" = "http" ]; then
  echo "Starting MCP server in HTTP mode on port 8024..." >&2
  exec python src/zotmcp/main.py $HYDRA_ARGS
else
  echo "Starting MCP server in stdio mode for MCP clients..." >&2
  exec fastmcp run src/zotmcp/main.py $HYDRA_ARGS
fi
