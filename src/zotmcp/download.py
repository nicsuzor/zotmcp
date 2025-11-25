#!/usr/bin/env python3
"""ZotMCP ChromaDB Download Script.

Downloads the Zotero vectors database from GCS to the local cache.
This is required before running the MCP server.

Usage:
    zotmcp-download
"""

import sys
from pathlib import Path

GCS_BUCKET = "prosocial-dev"
GCS_PREFIX = "data/zotero-prosocial-fulltext/files/"
CACHE_DIR = Path.home() / ".cache" / "buttermilk" / "chromadb"
VECTORS_DIR = CACHE_DIR / "gs_prosocial-dev_data_zotero-prosocial-fulltext_files"


def main() -> int:
    """Download Zotero vectors from GCS with progress bar."""
    try:
        from google.cloud import storage
        from google.auth import default
        from google.auth.exceptions import DefaultCredentialsError
    except ImportError:
        print("ERROR: google-cloud-storage not installed")
        return 1

    print("ZotMCP ChromaDB Download")
    print("=" * 50)
    print(f"Source: gs://{GCS_BUCKET}/{GCS_PREFIX}")
    print(f"Destination: {VECTORS_DIR}")
    print()

    # Check authentication
    print("Checking GCP authentication...")
    try:
        credentials, project = default()
    except DefaultCredentialsError:
        print()
        print("ERROR: Not authenticated with GCP.")
        print()
        print("Please authenticate using one of these methods:")
        print("  1. gcloud auth application-default login")
        print("  2. Set GOOGLE_APPLICATION_CREDENTIALS environment variable")
        print()
        return 1

    print("  Authenticated!")
    print()

    # Create destination directory
    VECTORS_DIR.mkdir(parents=True, exist_ok=True)

    # List blobs and calculate total size
    print("Fetching file list from GCS...")
    client = storage.Client()
    bucket = client.bucket(GCS_BUCKET)
    blobs = list(bucket.list_blobs(prefix=GCS_PREFIX))

    if not blobs:
        print("ERROR: No files found in GCS. Check your permissions.")
        print("Contact Nic to be granted access.")
        return 1

    total_size = sum(b.size for b in blobs)
    print(f"  Found {len(blobs)} files ({total_size / (1024**3):.2f} GB)")
    print()

    # Download with progress
    print("Downloading vectors...")
    downloaded = 0

    for i, blob in enumerate(blobs):
        # Skip the prefix directory marker
        if blob.name == GCS_PREFIX or blob.name.endswith("/"):
            continue

        # Calculate relative path
        rel_path = blob.name[len(GCS_PREFIX):]
        local_path = VECTORS_DIR / rel_path

        # Skip if already exists and same size
        if local_path.exists() and local_path.stat().st_size == blob.size:
            downloaded += blob.size
            continue

        # Create parent dirs
        local_path.parent.mkdir(parents=True, exist_ok=True)

        # Download
        blob.download_to_filename(str(local_path))
        downloaded += blob.size

        # Progress bar
        pct = downloaded / total_size * 100
        bar_len = 40
        filled = int(bar_len * downloaded / total_size)
        bar = "█" * filled + "░" * (bar_len - filled)
        print(f"\r  [{bar}] {pct:5.1f}% ({downloaded / (1024**3):.2f} GB)", end="", flush=True)

    print()
    print()
    print("Download complete!")
    print()

    # Verify
    local_size = sum(f.stat().st_size for f in VECTORS_DIR.rglob("*") if f.is_file())
    print(f"Verified: {local_size / (1024**3):.2f} GB in {VECTORS_DIR}")

    if local_size < total_size * 0.95:  # Allow 5% tolerance for metadata
        print("WARNING: Downloaded size seems smaller than expected")
        return 1

    print()
    print("You can now use ZotMCP!")
    print("  Run: zotmcp")

    return 0


if __name__ == "__main__":
    sys.exit(main())
