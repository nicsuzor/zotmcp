#!/bin/bash
# Sync the local ChromaDB at /chromadb with the GCS source of truth.
#
# Used both by the entrypoint (on container start, unless ZOTMCP_SKIP_SYNC=1)
# and as a manual refresh hook (`docker exec zotmcp sync-chromadb`).
#
# Requires gcloud/gsutil and valid credentials in the container (either a
# mounted ~/.config/gcloud or GOOGLE_APPLICATION_CREDENTIALS pointing at a
# service-account JSON).

set -eu -o pipefail

CHROMADB_DIR="${CHROMADB_DIR:-/chromadb}"
CHROMADB_GCS_URI="${CHROMADB_GCS_URI:-gs://prosocial-dev/data/zotero-prosocial-fulltext/files}"
LOCK_FILE="${CHROMADB_DIR}/.sync.lock"

mkdir -p "${CHROMADB_DIR}"

if ! command -v gsutil >/dev/null 2>&1; then
  echo "❌ gsutil not found in PATH; cannot sync ChromaDB from ${CHROMADB_GCS_URI}" >&2
  echo "   Install the Google Cloud SDK in the base image, or set ZOTMCP_SKIP_SYNC=1 to bypass." >&2
  exit 2
fi

# Take a non-blocking lock: if another container/process is already syncing the
# same volume, wait for it rather than racing.
exec 9>"${LOCK_FILE}"
if ! flock -w 600 9; then
  echo "❌ Could not acquire ${LOCK_FILE} within 10min — another sync still running?" >&2
  exit 3
fi

echo "📥 Syncing ChromaDB: ${CHROMADB_GCS_URI} → ${CHROMADB_DIR}" >&2
START=$(date +%s)

# -m parallel, -r recursive. gsutil rsync is incremental: steady-state is
# cheap; only first run downloads the full ~11 GB.
if ! gsutil -m rsync -r "${CHROMADB_GCS_URI}" "${CHROMADB_DIR}"; then
  RC=$?
  # If we already have a local DB, prefer to keep running with stale data
  # rather than crash the MCP. If the volume is empty, that's fatal.
  if [ -z "$(ls -A "${CHROMADB_DIR}" 2>/dev/null | grep -v '^\.sync\.lock$' || true)" ]; then
    echo "❌ Sync failed (rc=${RC}) and ${CHROMADB_DIR} is empty. Aborting." >&2
    exit "${RC}"
  fi
  echo "⚠️  Sync failed (rc=${RC}), continuing with existing local ChromaDB." >&2
else
  ELAPSED=$(( $(date +%s) - START ))
  SIZE=$(du -sh "${CHROMADB_DIR}" 2>/dev/null | awk '{print $1}')
  echo "✅ ChromaDB sync complete in ${ELAPSED}s (size: ${SIZE})" >&2
fi
