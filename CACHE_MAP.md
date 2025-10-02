# ZotMCP Cache Locations

All caches are under `.cache/` in the project root to avoid duplication and make cleanup easy.

## Directory Structure

```
projects/zotmcp/
└── .cache/                                    # All caches here
    ├── zotero/
    │   ├── items/                             # Downloaded PDFs
    │   │   └── {item_key}.pdf
    │   └── embeddings/                        # Arrow cache for embeddings
    │       └── *.arrow
    │
    └── zotero-prosocial-fulltext/
        └── files/                             # ChromaDB vector database
            ├── chroma.sqlite3
            ├── {uuid}/                        # Collection data
            └── ...
```

## Cache Usage by Component

### 1. MCP Server (`src/main.py`)

**Reads:**
- `.cache/zotero-prosocial-fulltext/files` - ChromaDB vectors

**Config:** `conf/zotero.yaml`
```yaml
persist_directory: .cache/zotero-prosocial-fulltext/files
```

### 2. Vectorization Pipeline (`conf/vectorize.yaml`)

**Writes:**
- `.cache/zotero/items/` - Downloaded PDFs
- `.cache/zotero/embeddings/` - Arrow cache
- `.cache/zotero-prosocial-fulltext/files` - ChromaDB vectors

**Config:**
```yaml
bm:
  session_info:
    cache_dir: .cache                          # Buttermilk cache

pipeline:
  source:
    save_dir: .cache/zotero/items             # PDF downloads

vectoriser:
  persist_directory: gs://...                 # Syncs to GCS
  arrow_save_dir: .cache/zotero/embeddings    # Embedding cache
```

### 3. Docker Build

**Copies:**
- `.cache/zotero-prosocial-fulltext/` → baked into image

**Dockerfile:**
```dockerfile
COPY .cache/zotero-prosocial-fulltext ${APP_PATH}/.cache/zotero-prosocial-fulltext
```

### 4. Download/Upload Scripts

**`scripts/package_for_distribution.sh`:**
```bash
download: gs://... → .cache/zotero-prosocial-fulltext/files
upload:   .cache/zotero-prosocial-fulltext/files → gs://...
```

## Cache Lifecycle

### Initial Setup

```bash
# Download ChromaDB from GCS
./scripts/package_for_distribution.sh download
# Creates: .cache/zotero-prosocial-fulltext/files/
```

### Update Cycle

```bash
# 1. Run vectorization (updates all caches)
./scripts/update_vectors.sh
# Updates:
#   .cache/zotero/items/                    (new PDFs)
#   .cache/zotero/embeddings/               (new embeddings)
#   .cache/zotero-prosocial-fulltext/files/ (new vectors)
# Syncs to: gs://prosocial-dev/data/zotero-prosocial-fulltext/files

# 2. Build Docker with updated ChromaDB
./deploy/build.sh --refresh-chromadb --push

# 3. Users pull new image (ChromaDB baked in)
docker pull us-central1-docker.pkg.dev/prosocial-443205/reg/zotmcp:latest
```

### Local Development

```bash
# Use local ChromaDB for testing
python src/main.py
# Reads: .cache/zotero-prosocial-fulltext/files/
```

## Cache Sizes

| Directory | Size | Contents |
|-----------|------|----------|
| `.cache/zotero/items/` | ~500MB - 2GB | Downloaded PDFs |
| `.cache/zotero/embeddings/` | ~100MB | Arrow embedding cache |
| `.cache/zotero-prosocial-fulltext/files/` | ~2-3GB | ChromaDB vectors |
| **Total** | **~3-5GB** | |

## Cache Cleanup

**Safe to delete:**
```bash
# PDFs (will re-download if needed)
rm -rf .cache/zotero/items/

# Embedding cache (will regenerate if needed)
rm -rf .cache/zotero/embeddings/
```

**⚠️ Don't delete unless you know what you're doing:**
```bash
# ChromaDB vectors (expensive to regenerate)
rm -rf .cache/zotero-prosocial-fulltext/files/
```

**Full clean (for fresh start):**
```bash
rm -rf .cache/
./scripts/package_for_distribution.sh download
```

## Gitignore

All caches are excluded:
```gitignore
.cache/
```

## No Duplication

**Before (multiple locations):**
- ❌ `~/.cache/zotmcp/`
- ❌ `~/.cache/zotero/`
- ❌ `.cache/zot/files/`
- ❌ `data/osb_vectors/`

**After (unified):**
- ✅ `.cache/` (everything here)

This makes it easy to:
- Clean up: `rm -rf .cache/`
- Backup: `tar -czf cache-backup.tar.gz .cache/`
- Check size: `du -sh .cache/`
