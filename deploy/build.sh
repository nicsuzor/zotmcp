#!/bin/bash
# Build ZotMCP Docker image
#
# Usage:
#   ./build.sh                        # Build locally
#   ./build.sh --push                 # Build and push to registry
#   ./build.sh --refresh-chromadb     # Force ChromaDB re-download
#
# Layer Caching Strategy:
#   - ChromaDB: Cached monthly using CACHE_DATE build arg (use --refresh-chromadb to force re-download)
#   - Python deps: Cached based on pyproject.toml changes
#

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

IMAGE_NAME="us-central1-docker.pkg.dev/prosocial-443205/reg/zotmcp"
TAG="${TAG:-latest}"

# Cache ChromaDB monthly by default
CACHE_DATE="${CACHE_DATE:-$(date +%Y-%m)}"

# Check for flags
REFRESH_CHROMADB=false
PUSH=false
for arg in "$@"; do
    if [ "$arg" = "--refresh-chromadb" ]; then
        REFRESH_CHROMADB=true
        # Use current timestamp to bust cache
        CACHE_DATE=$(date +%Y-%m-%d-%H%M%S)
    fi
    if [ "$arg" = "--push" ]; then
        PUSH=true
    fi
done

echo "🐳 Building ZotMCP Docker image..."
echo "   Image: ${IMAGE_NAME}:${TAG}"
echo "   Context: ${PROJECT_DIR}"
echo "   ChromaDB cache date: ${CACHE_DATE}"
if [ "$REFRESH_CHROMADB" = true ]; then
    echo "   ⚠️  ChromaDB will be re-downloaded"
fi
echo ""

cd "$PROJECT_DIR"

# Check if ChromaDB exists locally
if [ ! -d "$PROJECT_DIR/.cache/zotero-prosocial-fulltext/files" ]; then
    echo "❌ Error: ChromaDB not found at .cache/zotero-prosocial-fulltext/files"
    echo ""
    echo "Please download it first:"
    echo "  ./scripts/package_for_distribution.sh download"
    echo ""
    exit 1
fi

CHROMADB_SIZE=$(du -sh "$PROJECT_DIR/.cache/zotero-prosocial-fulltext" | cut -f1)
echo "   ChromaDB size: ${CHROMADB_SIZE}"
echo ""

# Build the image with cache date
docker build \
    -f deploy/Dockerfile \
    -t "${IMAGE_NAME}:${TAG}" \
    --build-arg CACHE_DATE="${CACHE_DATE}" \
    --progress=plain \
    .

echo ""
echo "✅ Build complete: ${IMAGE_NAME}:${TAG}"

# Push if requested
if [ "$PUSH" = true ]; then
    echo ""
    echo "📤 Pushing to registry..."
    docker push "${IMAGE_NAME}:${TAG}"
    echo "✅ Pushed: ${IMAGE_NAME}:${TAG}"
fi

echo ""
echo "To run:"
echo "  docker run --rm /${USER}/.config/gcloud:/root/.config/gcloud:ro -i ${IMAGE_NAME}:${TAG}"
echo ""