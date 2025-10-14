#!/bin/bash
# ZotMCP Startup Script
# Runs FastMCP server in stdio mode for MCP clients

set -e

# Change to app directory
cd /app/zotmcp

# Check if ChromaDB is available
if [ ! -d "/chromadb" ]; then
    echo "WARNING: ChromaDB not found at /chromadb"
    echo "The server will fail when tools are called."
    echo "Mount ChromaDB at runtime with: -v /path/to/chromadb:/chromadb"
fi

# Run in stdio mode by default (for MCP)
# Can override with HTTP mode: docker run -e MODE=http -p 8024:8024 zotmcp
if [ "${MODE}" = "http" ]; then
    echo "Starting ZotMCP in HTTP mode on :8024"
    exec python -m src.main db=deploy
else
    echo "Starting ZotMCP in stdio mode (MCP)" >&2
    exec python -m src.main db=deploy
fi
