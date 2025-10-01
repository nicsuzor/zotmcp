#!/bin/bash
# ZotMCP Distribution Script
#
# Usage:
#   ./package_for_distribution.sh          # Package source code
#   ./package_for_distribution.sh download # Download ChromaDB from GCS
#   ./package_for_distribution.sh upload   # Upload ChromaDB to GCS
#
# ChromaDB is stored at: gs://prosocial-dev/data/zotero-prosocial-fulltext/files

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
GCS_PATH="gs://prosocial-dev/data/zotero-prosocial-fulltext/files"
CACHE_DIR="$PROJECT_DIR/.cache"
VECTORS_DIR="$CACHE_DIR/zotero-prosocial-fulltext/files"

# Command: download ChromaDB from GCS
if [ "$1" == "download" ]; then
    echo "📥 Downloading Zotero library ChromaDB from GCS..."
    mkdir -p "$CACHE_DIR/zotero-prosocial-fulltext"
    gsutil -m cp -r "$GCS_PATH" "$CACHE_DIR/zotero-prosocial-fulltext/"
    echo "✅ Zotero library downloaded to $VECTORS_DIR"
    exit 0
fi

# Command: upload ChromaDB to GCS
if [ "$1" == "upload" ]; then
    if [ ! -d "$VECTORS_DIR" ]; then
        echo "❌ ChromaDB not found at $VECTORS_DIR"
        exit 1
    fi
    echo "📤 Uploading Zotero library ChromaDB to GCS..."
    gsutil -m cp -r "$VECTORS_DIR" "$(dirname $GCS_PATH)/"
    echo "✅ Zotero library uploaded to $GCS_PATH"
    exit 0
fi

# Default: package source code for distribution
DIST_NAME="zotmcp"
TIMESTAMP=$(date +%Y%m%d)
OUTPUT_DIR="$PROJECT_DIR/dist"

echo "📦 Packaging ZotMCP for distribution..."
mkdir -p "$OUTPUT_DIR"

TEMP_DIR=$(mktemp -d)
PACKAGE_DIR="$TEMP_DIR/$DIST_NAME"
mkdir -p "$PACKAGE_DIR"

# Copy source files
echo "  → Copying source code..."
cp -r "$PROJECT_DIR/src" "$PACKAGE_DIR/"
cp -r "$PROJECT_DIR/conf" "$PACKAGE_DIR/"
cp -r "$PROJECT_DIR/examples" "$PACKAGE_DIR/"
cp -r "$PROJECT_DIR/templates" "$PACKAGE_DIR/"

# Copy documentation
echo "  → Copying documentation..."
cp "$PROJECT_DIR/README.md" "$PACKAGE_DIR/"
cp "$PROJECT_DIR/pyproject.toml" "$PACKAGE_DIR/"
cp "$PROJECT_DIR/.gitignore" "$PACKAGE_DIR/"

# Copy scripts
cp -r "$PROJECT_DIR/scripts" "$PACKAGE_DIR/"

# Create the package
echo "  → Creating archive..."
cd "$TEMP_DIR"
tar -czf "$OUTPUT_DIR/${DIST_NAME}-${TIMESTAMP}.tar.gz" "$DIST_NAME/"

# Cleanup
rm -rf "$TEMP_DIR"

echo ""
echo "✅ Package created: $OUTPUT_DIR/${DIST_NAME}-${TIMESTAMP}.tar.gz"
echo ""
echo "To share:"
echo "  1. Share ${DIST_NAME}-${TIMESTAMP}.tar.gz with colleagues"
echo "  2. Recipients run: ./scripts/package_for_distribution.sh download"
echo ""
