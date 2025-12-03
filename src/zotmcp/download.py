#!/usr/bin/env python3
"""ZotMCP ChromaDB Download Script.

Downloads the Zotero vectors database from GCS to the local cache.
Uses parallel sliced downloads for speed.
Includes browser-based OAuth if no credentials are found.

Usage:
    zotmcp-download
"""

import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

GCS_PROJECT = "prosocial-dev"  # GCP project ID (required, no defaults)
GCS_BUCKET = "prosocial-dev"
GCS_PREFIX = "data/zotero-prosocial-fulltext/files/"
CACHE_DIR = Path.home() / ".cache" / "buttermilk" / "chromadb"
VECTORS_DIR = CACHE_DIR / "gs_prosocial-dev_data_zotero-prosocial-fulltext_files"
MAX_WORKERS = 16  # Parallel download threads
CHUNK_SIZE = 32 * 1024 * 1024  # 32MB chunks for sliced downloads
SLICE_THRESHOLD = 100 * 1024 * 1024  # Slice files larger than 100MB

# OAuth client ID for installed apps (public, not secret)
# This is the same client ID used by gcloud CLI
OAUTH_CLIENT_ID = "764086051850-6qr4p6gpi6hn506pt8ejuq83di341hur.apps.googleusercontent.com"
OAUTH_CLIENT_SECRET = "d-FL95Q19q7MQmFpd7hHD0Ty"
SCOPES = ["https://www.googleapis.com/auth/devstorage.read_only"]


def get_adc_path() -> Path:
    """Get the Application Default Credentials file path."""
    if sys.platform == "win32":
        return Path.home() / "AppData" / "Roaming" / "gcloud" / "application_default_credentials.json"
    return Path.home() / ".config" / "gcloud" / "application_default_credentials.json"


def do_oauth_flow():
    """Run browser-based OAuth and save as ADC."""
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("ERROR: google-auth-oauthlib not installed")
        print("Run: pip install google-auth-oauthlib")
        return None

    print("Opening browser for Google authentication...")
    print("(Use the email address Nic added to the project)")
    print()

    client_config = {
        "installed": {
            "client_id": OAUTH_CLIENT_ID,
            "client_secret": OAUTH_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    credentials = flow.run_local_server(port=0)

    # Save as ADC
    adc_path = get_adc_path()
    adc_path.parent.mkdir(parents=True, exist_ok=True)

    adc_data = {
        "client_id": OAUTH_CLIENT_ID,
        "client_secret": OAUTH_CLIENT_SECRET,
        "refresh_token": credentials.refresh_token,
        "type": "authorized_user",
    }
    adc_path.write_text(json.dumps(adc_data, indent=2))
    print(f"Credentials saved to {adc_path}")
    print()

    return credentials


def main() -> int:
    """Download Zotero vectors from GCS with parallel sliced transfers."""
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
    credentials = None
    try:
        credentials, _ = default()  # Ignore project from ADC, use GCS_PROJECT constant
    except DefaultCredentialsError:
        print("  No existing credentials found.")
        print()
        credentials = do_oauth_flow()
        if not credentials:
            return 1

    print("  Authenticated!")
    print()

    # Create destination directory
    VECTORS_DIR.mkdir(parents=True, exist_ok=True)

    # List blobs and calculate total size
    print("Fetching file list from GCS...")
    # Explicitly pass project and credentials (fail-fast, no environment defaults)
    # Note: Do NOT set quota_project_id - it causes "User project specified in the request is invalid"
    # errors for users who aren't project members. The bucket is not requester-pays.
    client = storage.Client(
        project=GCS_PROJECT,
        credentials=credentials,
    )
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
    print(f"  Using {MAX_WORKERS} parallel connections with sliced downloads")
    print()

    # Progress tracking
    downloaded = [skipped_size]  # Use list for mutable closure
    lock = Lock()

    def update_progress(added_bytes=0):
        with lock:
            downloaded[0] += added_bytes
            pct = downloaded[0] / total_size * 100
            bar_len = 40
            filled = int(bar_len * downloaded[0] / total_size)
            bar = "█" * filled + "░" * (bar_len - filled)
            print(f"\r  [{bar}] {pct:5.1f}% ({downloaded[0] / (1024**3):.2f} GB)", end="", flush=True)

    def download_blob_sliced(blob):
        """Download a blob using sliced/chunked download for large files."""
        rel_path = blob.name[len(GCS_PREFIX):]
        local_path = VECTORS_DIR / rel_path
        local_path.parent.mkdir(parents=True, exist_ok=True)

        if blob.size > SLICE_THRESHOLD:
            # Sliced download for large files
            with open(local_path, "wb") as f:
                start = 0
                while start < blob.size:
                    end = min(start + CHUNK_SIZE, blob.size)
                    chunk = blob.download_as_bytes(start=start, end=end - 1)
                    f.write(chunk)
                    update_progress(len(chunk))
                    start = end
        else:
            # Regular download for small files
            blob.download_to_filename(str(local_path))
            update_progress(blob.size)

        return blob.size

    # Parallel download
    print("Downloading vectors...")
    update_progress()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(download_blob_sliced, blob): blob for blob in to_download}
        for future in as_completed(futures):
            future.result()  # Raise any exceptions

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
    print("Add to your Claude config - see README.md for instructions")

    return 0


if __name__ == "__main__":
    sys.exit(main())
