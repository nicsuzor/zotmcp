#!/bin/bash
# Update Zotero library vectors
#
# This script runs the vectorization pipeline to:
# - Fetch latest items from Zotero API
# - Download new/changed PDFs only
# - Extract text and generate citations
# - Create/update embeddings
# - Sync to ChromaDB (local and GCS)
#
# Usage:
#   ./update_vectors.sh

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Required environment variables
: "${ZOTERO_LIBRARY_ID:?Error: ZOTERO_LIBRARY_ID not set}"
: "${ZOTERO_API_KEY:?Error: ZOTERO_API_KEY not set}"

# Optional with defaults
ZOTERO_LOCAL="${ZOTERO_LOCAL:-false}"

echo "🔄 Updating Zotero library vectors"
echo "   Library ID: ${ZOTERO_LIBRARY_ID}"
echo "   Local mode: ${ZOTERO_LOCAL}"
echo ""

cd "$PROJECT_DIR"

# Run vectorization pipeline using Buttermilk
echo "📚 Running vectorization pipeline..."
echo ""

python -m buttermilk.pipeline.runner \
    --config-path conf \
    --config-name vectorize

echo ""
echo "✅ Vectorization complete!"
echo ""

# Show stats
VECTORS_DIR="$HOME/.cache/zotmcp/zotero-prosocial-fulltext/files"
if [ -d "$VECTORS_DIR" ]; then
    echo "📊 Local ChromaDB:"
    du -sh "$VECTORS_DIR"
fi

echo ""
echo "🎉 Done! The vectors have been synced to GCS by the pipeline."
echo ""
echo "Next steps:"
echo "  1. Test locally: python src/main.py"
echo "  2. Rebuild Docker: ./containers/deploy/build.sh --refresh-chromadb --push"
