# Docker Container Architecture

## Layer Structure

The Dockerfile uses a multi-stage build with smart layer caching:

```
┌─────────────────────────────────────────┐
│ 1. Base Layer (Buttermilk)             │ ← Cached forever
│    - Python, Node.js, system deps      │
│    - gcloud, gsutil tools               │
└─────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────┐
│ 2. ChromaDB Layer                       │ ← Cached MONTHLY
│    - Downloads from GCS                 │   (via CACHE_DATE)
│    - ~2-3GB of vectors                  │
│    - Only rebuilds when forced          │
└─────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────┐
│ 3. Builder Layer                        │ ← Cached per pyproject.toml
│    - Installs Python deps via uv        │
│    - FastMCP, ChromaDB, Pydantic        │
└─────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────┐
│ 4. Final Layer                          │ ← Rebuilds on code changes
│    - Copies ChromaDB (from layer 2)     │
│    - Copies venv (from layer 3)         │
│    - Copies application code            │
│    - Total: ~3-4GB                      │
└─────────────────────────────────────────┘
```

## Why `--rm` is OK

**Containers vs Images:**
- **Image**: Template/blueprint (stored on disk, ~3-4GB)
- **Container**: Running instance (ephemeral, removed with `--rm`)

**When you run:**
```bash
docker run --rm -i zotmcp:latest
```

1. Docker creates a **new container** from the **image**
2. Container runs, handles MCP requests
3. Container exits when MCP client disconnects
4. Container is removed (`--rm`)
5. **Image remains** with all the ChromaDB data

**No data loss because:**
- ChromaDB is baked into the **image** (layer 2)
- Each new container gets a fresh copy from the image
- Image layers are cached and reused

## ChromaDB Caching Strategy

### Monthly Cache (Default)

```bash
./build.sh  # Uses CACHE_DATE=2025-10
```

- ChromaDB layer cached for the entire month
- Rebuilds only when month changes (e.g., 2025-10 → 2025-11)
- Code changes don't trigger ChromaDB re-download

### Force Refresh

```bash
./build.sh --refresh-chromadb
```

- Busts the cache with a timestamp
- Forces fresh download from GCS
- Use when Zotero library is updated

### Custom Cache Period

```bash
CACHE_DATE=2025-Q4 ./build.sh
```

## Build Performance

**First build (cold cache):**
```
Layer 1 (Base):      Pulled from registry    (~30s)
Layer 2 (ChromaDB):  Download from GCS       (~5-10min, 2-3GB)
Layer 3 (Builder):   Install Python deps     (~30s)
Layer 4 (Final):     Copy files             (~10s)
Total: ~6-11 minutes
```

**Subsequent builds (warm cache, code changed):**
```
Layer 1 (Base):      Cached ✓
Layer 2 (ChromaDB):  Cached ✓ (same month)
Layer 3 (Builder):   Cached ✓ (same deps)
Layer 4 (Final):     Rebuild (code changed)  (~10s)
Total: ~10 seconds
```

**Monthly rebuild (new CACHE_DATE):**
```
Layer 1 (Base):      Cached ✓
Layer 2 (ChromaDB):  Re-download from GCS    (~5-10min)
Layer 3 (Builder):   Cached ✓
Layer 4 (Final):     Rebuild                (~10s)
Total: ~5-10 minutes
```

## Updating Workflow

### When Code Changes (Frequent)

```bash
# Edit src/main.py or src/models.py
./build.sh --push
# Takes ~10 seconds (only layer 4 rebuilds)
```

### When ChromaDB Updates (Rare)

```bash
# 1. Update ChromaDB in GCS via Buttermilk pipeline
# 2. Force refresh
./build.sh --refresh-chromadb --push
# Takes ~5-10 minutes (re-downloads ChromaDB)
```

### Monthly Maintenance (Automatic)

```bash
# On 2025-11-01, first build will automatically refresh ChromaDB
./build.sh --push
# CACHE_DATE changes from 2025-10 to 2025-11
```

## Storage Locations

**Image**: Stored in Docker's image cache
```bash
docker images | grep zotmcp
# us-central1-docker.pkg.dev/prosocial-443205/reg/zotmcp   latest   abc123   3.5GB
```

**Container**: Ephemeral, removed after each run
```bash
docker ps -a | grep zotmcp
# (empty if using --rm)
```

**Registry**: Google Artifact Registry
```
us-central1-docker.pkg.dev/prosocial-443205/reg/zotmcp:latest
```

## Cost Optimization

✅ **Efficient:**
- ChromaDB cached monthly (not every build)
- Code changes don't trigger large re-downloads
- Layer caching minimizes GCS egress

❌ **Inefficient (old approach):**
- ChromaDB copied with code (every build)
- ~2-3GB downloaded on every code change
- High GCS egress costs

## Debugging

**Check layer sizes:**
```bash
docker history us-central1-docker.pkg.dev/prosocial-443205/reg/zotmcp:latest
```

**Force cache bust:**
```bash
docker build --no-cache ...
```

**Inspect ChromaDB in image:**
```bash
docker run --rm -it zotmcp:latest bash
ls -lh .cache/zotero-prosocial-fulltext/files
```

## FAQs

**Q: Why not use a volume for ChromaDB?**
A: Volumes add complexity for end users. Baking ChromaDB into the image makes distribution simpler (just `docker pull`).

**Q: What if ChromaDB download fails during build?**
A: Build continues with a warning. Container will need ChromaDB mounted at runtime:
```bash
docker run -v /path/to/chromadb:/app/zotmcp/.cache/... zotmcp:latest
```

**Q: How do I verify ChromaDB is in the image?**
A: Run the container and check:
```bash
docker run --rm zotmcp:latest ls -la .cache/zotero-prosocial-fulltext/files
```

**Q: Can I skip ChromaDB in the image?**
A: Yes, build without CACHE_DATE and mount at runtime. But defeats the purpose of easy distribution.
