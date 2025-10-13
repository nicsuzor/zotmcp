#!/bin/bash
# Run ZotMCP Docker container locally (for development/testing)
#
# For production use, just run the container directly:
#   docker run --rm -v ${HOME}/.config/gcloud:/root/.config/gcloud:ro -i \
#     us-central1-docker.pkg.dev/prosocial-443205/reg/zotmcp:latest

set -e

IMAGE_NAME="us-central1-docker.pkg.dev/prosocial-443205/reg/zotmcp:latest"
MODE="${1:-stdio}"

# Standard mounts for all runs
GCLOUD_MOUNT="-v ${HOME}/.config/gcloud:/root/.config/gcloud:ro"

case "$MODE" in
    http)
        echo "🚀 Running ZotMCP in HTTP mode..."
        docker run --rm -it \
            ${GCLOUD_MOUNT} \
            -e MODE=http \
            -p 8024:8024 \
            "${IMAGE_NAME}"
        ;;

    stdio|*)
        echo "🚀 Running ZotMCP in stdio mode (MCP)..."
        docker run --rm -i \
            ${GCLOUD_MOUNT} \
            "${IMAGE_NAME}"
        ;;
esac
