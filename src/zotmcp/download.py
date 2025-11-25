#!/usr/bin/env python3
"""ZotMCP ChromaDB Download Script.

Downloads the Zotero vectors database from GCS to the local cache.
This is required before running the MCP server.

Usage:
    uvx --from git+https://github.com/nicsuzor/zotmcp.git zotmcp-download
    # or
    uv run python src/download.py
"""

import subprocess
import sys
from pathlib import Path


GCS_PATH = "gs://prosocial-dev/data/zotero-prosocial-fulltext/files"
CACHE_DIR = Path.home() / ".cache" / "buttermilk" / "chromadb"
VECTORS_DIR = CACHE_DIR / "gs_prosocial-dev_data_zotero-prosocial-fulltext_files"


def main() -> int:
    """Download Zotero vectors from GCS."""
    print("ZotMCP ChromaDB Download")
    print("=" * 50)
    print(f"Source: {GCS_PATH}")
    print(f"Destination: {VECTORS_DIR}")
    print()

    # Check gsutil is available
    try:
        subprocess.run(
            ["gsutil", "--version"],
            check=True,
            capture_output=True,
        )
    except FileNotFoundError:
        print("ERROR: gsutil not found. Please install Google Cloud SDK:")
        print("  https://cloud.google.com/sdk/docs/install")
        return 1
    except subprocess.CalledProcessError:
        print("ERROR: gsutil not working properly")
        return 1

    # Check authentication
    print("Checking GCP authentication...")
    result = subprocess.run(
        ["gcloud", "auth", "application-default", "print-access-token"],
        capture_output=True,
    )
    if result.returncode != 0:
        print("ERROR: Not authenticated with GCP. Please run:")
        print("  gcloud auth application-default login")
        return 1

    # Create destination directory
    VECTORS_DIR.mkdir(parents=True, exist_ok=True)

    # Sync from GCS
    print()
    print("Downloading vectors (this may take several minutes)...")
    print()

    result = subprocess.run(
        ["gsutil", "-m", "rsync", "-r", GCS_PATH, str(VECTORS_DIR)],
    )

    if result.returncode != 0:
        print()
        print("ERROR: Download failed. Check your GCP permissions.")
        print("Contact Nic to be granted access to the prosocial-dev bucket.")
        return 1

    print()
    print("Download complete!")
    print()

    # Show size
    total_size = sum(f.stat().st_size for f in VECTORS_DIR.rglob("*") if f.is_file())
    print(f"Total size: {total_size / (1024**3):.2f} GB")
    print(f"Location: {VECTORS_DIR}")
    print()
    print("You can now use ZotMCP with Claude Code.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
