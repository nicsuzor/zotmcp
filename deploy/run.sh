#!/bin/bash
# Run ZotMCP Docker container locally (for development/testing)
#
# The ChromaDB is no longer bundled in the image. It is rsynced from
# gs://prosocial-dev/data/zotero-prosocial-fulltext/files into a named
# Docker volume (`zotmcp-chromadb` by default) on every container start.
# First start downloads the full ~11 GB; subsequent starts are incremental.
#
# Set ZOTMCP_SKIP_SYNC=1 to skip the rsync (the volume must already be
# populated). Set CHROMADB_GCS_URI to override the source bucket path.

set -e

IMAGE_NAME="${ZOTMCP_IMAGE:-us-central1-docker.pkg.dev/prosocial-443205/reg/zotmcp:latest}"
MODE="${1:-stdio}"
VOLUME_NAME="${ZOTMCP_VOLUME:-zotmcp-chromadb}"

# Create the named volume if missing (idempotent).
docker volume inspect "${VOLUME_NAME}" >/dev/null 2>&1 || docker volume create "${VOLUME_NAME}" >/dev/null

# Standard mounts for all runs:
# - gcloud creds for both GCS rsync and Vertex AI query embedding
# - named volume holding the ChromaDB across runs/rebuilds
GCLOUD_MOUNT="-v ${HOME}/.config/gcloud:/root/.config/gcloud:ro"
CHROMADB_MOUNT="-v ${VOLUME_NAME}:/chromadb"

# Forward optional overrides
EXTRA_ENV=()
[ -n "${ZOTMCP_SKIP_SYNC:-}" ] && EXTRA_ENV+=(-e "ZOTMCP_SKIP_SYNC=${ZOTMCP_SKIP_SYNC}")
[ -n "${CHROMADB_GCS_URI:-}" ] && EXTRA_ENV+=(-e "CHROMADB_GCS_URI=${CHROMADB_GCS_URI}")

case "$MODE" in
    http)
        echo "🚀 Running ZotMCP in HTTP mode (volume: ${VOLUME_NAME})..."
        docker run --rm -it \
            ${GCLOUD_MOUNT} \
            ${CHROMADB_MOUNT} \
            "${EXTRA_ENV[@]}" \
            -e MODE=http \
            -p 8024:8024 \
            "${IMAGE_NAME}"
        ;;

    stdio|*)
        echo "🚀 Running ZotMCP in stdio mode (volume: ${VOLUME_NAME})..."
        docker run --rm -i \
            ${GCLOUD_MOUNT} \
            ${CHROMADB_MOUNT} \
            "${EXTRA_ENV[@]}" \
            "${IMAGE_NAME}"
        ;;
esac
