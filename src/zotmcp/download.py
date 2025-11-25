#!/usr/bin/env python3
"""ZotMCP ChromaDB Download Script.

Downloads the Zotero vectors database from GCS to the local cache.
Uses parallel downloads for speed.

Usage:
    zotmcp-download
"""

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

GCS_BUCKET = "prosocial-dev"
GCS_PREFIX = "data/zotero-prosocial-fulltext/files/"
CACHE_DIR = Path.home() / ".cache" / "buttermilk" / "chromadb"
VECTORS_DIR = CACHE_DIR / "gs_prosocial-dev_data_zotero-prosocial-fulltext_files"
MAX_WORKERS = 8  # Parallel download threads


def main() -> int:
    """Download Zotero vectors from GCS with parallel transfers."""
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

    # Filter out directory markers
    blobs = [b for b in blobs if not b.name.endswith("/") and b.name != GCS_PREFIX]

    total_size = sum(b.size for b in blobs)
    print(f"  Found {len(blobs)} files ({total_size / (1024**3):.2f} GB)")
    print()

    # Check which files need downloading
    to_download = []
    skipped_size = 0
    for blob in blobs:
        rel_path = blob.name[len(GCS_PREFIX):]
        local_path = VECTORS_DIR / rel_path
        if local_path.exists() and local_path.stat().st_size == blob.size:
            skipped_size += blob.size
        else:
            to_download.append(blob)

    if skipped_size > 0:
        print(f"  Skipping {skipped_size / (1024**3):.2f} GB (already downloaded)")

    if not to_download:
        print("  All files already downloaded!")
        print()
        print("You can now use ZotMCP!")
        return 0

    download_size = sum(b.size for b in to_download)
    print(f"  Downloading {len(to_download)} files ({download_size / (1024**3):.2f} GB)")
    print(f"  Using {MAX_WORKERS} parallel connections")
    print()

    # Progress tracking
    downloaded = [skipped_size]  # Use list for mutable closure
    lock = Lock()

    def download_blob(blob):
        """Download a single blob."""
        rel_path = blob.name[len(GCS_PREFIX):]
        local_path = VECTORS_DIR / rel_path
        local_path.parent.mkdir(parents=True, exist_ok=True)
        blob.download_to_filename(str(local_path))
        with lock:
            downloaded[0] += blob.size
        return blob.size

    def update_progress():
        pct = downloaded[0] / total_size * 100
        bar_len = 40
        filled = int(bar_len * downloaded[0] / total_size)
        bar = "█" * filled + "░" * (bar_len - filled)
        print(f"\r  [{bar}] {pct:5.1f}% ({downloaded[0] / (1024**3):.2f} GB)", end="", flush=True)

    # Parallel download
    print("Downloading vectors...")
    update_progress()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(download_blob, blob): blob for blob in to_download}
        for future in as_completed(futures):
            future.result()  # Raise any exceptions
            update_progress()

    print()
    print()
    print("Download complete!")
    print()

    # Verify
    local_size = sum(f.stat().st_size for f in VECTORS_DIR.rglob("*") if f.is_file())
    print(f"Verified: {local_size / (1024**3):.2f} GB in {VECTORS_DIR}")

    if local_size < total_size * 0.95:
        print("WARNING: Downloaded size seems smaller than expected")
        return 1

    print()
    print("You can now use ZotMCP!")
    print("  Run: zotmcp")

    return 0


if __name__ == "__main__":
    sys.exit(main())
