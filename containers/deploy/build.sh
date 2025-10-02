#!/bin/bash
# Build ZotMCP Docker image
#
# Usage:
#   ./build.sh              # Build locally
#   ./build.sh --push       # Build and push to registry

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"

IMAGE_NAME="us-central1-docker.pkg.dev/prosocial-443205/reg/zotmcp"
TAG="${TAG:-latest}"

echo "🐳 Building ZotMCP Docker image..."
echo "   Image: ${IMAGE_NAME}:${TAG}"
echo "   Context: ${PROJECT_DIR}"
echo ""

cd "$PROJECT_DIR"

# Build the image
docker build \
    -f containers/deploy/Dockerfile \
    -t "${IMAGE_NAME}:${TAG}" \
    --progress=plain \
    .

echo ""
echo "✅ Build complete: ${IMAGE_NAME}:${TAG}"

# Push if requested
if [ "$1" = "--push" ]; then
    echo ""
    echo "📤 Pushing to registry..."
    docker push "${IMAGE_NAME}:${TAG}"
    echo "✅ Pushed: ${IMAGE_NAME}:${TAG}"
fi

echo ""
echo "To run locally:"
echo "  docker run --rm -i ${IMAGE_NAME}:${TAG}"
echo ""
echo "To run with ChromaDB from GCS:"
echo "  docker run --rm -i -v \$(pwd)/.cache:/app/zotmcp/.cache ${IMAGE_NAME}:${TAG}"
echo ""
echo "To run in HTTP mode:"
echo "  docker run --rm -e MODE=http -p 8024:8024 ${IMAGE_NAME}:${TAG}"
