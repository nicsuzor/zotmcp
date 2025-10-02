# ZotMCP Scripts

## update_vectors.sh - Update Zotero Library Vectors

Updates the ChromaDB vector database with latest items from Zotero.

### What it does:

1. **Fetches** latest items from Zotero API (metadata only)
2. **Downloads** PDFs that are new or changed (skips existing)
3. **Extracts** text from PDFs (cached to avoid re-processing)
4. **Generates** citations using Gemini Flash
5. **Chunks** text into ~1000 token segments
6. **Creates** embeddings using gemini-embedding-001
7. **Uploads** to ChromaDB (local + syncs to GCS)

### Prerequisites:

```bash
# Required environment variables
export ZOTERO_LIBRARY_ID="your_library_id"
export ZOTERO_API_KEY="your_api_key"

# Optional
export ZOTERO_LOCAL="false"  # Set to "true" for local-only testing
```

### Usage:

```bash
# Update vectors
./scripts/update_vectors.sh
```

### What gets updated:

- **Only changed items**: PDFs are only downloaded if modified
- **Cached text extraction**: Already-processed PDFs are skipped
- **Deduplication**: ChromaDB deduplicates by record_id and content_hash
- **Incremental sync**: GCS rsync only uploads changed files

### Performance:

| Scenario | Time | API Calls |
|----------|------|-----------|
| **No changes** | ~2-5 min | Zotero API only |
| **Few new items** | ~10-20 min | API + LLM citations + embeddings |
| **Many updates** | ~1-2 hours | Full pipeline |

### Costs:

**Zotero API**: Free (rate limited)
**PDF downloads**: Bandwidth only
**LLM citations**: ~$0.001 per item (Gemini Flash)
**Embeddings**: ~$0.001 per item (gemini-embedding-001)

**Estimate**: ~$0.002 per new item

### After updating:

```bash
# 1. Test locally
python src/main.py

# 2. Rebuild Docker image
cd containers/deploy
./build.sh --refresh-chromadb --push

# 3. Users pull new image
docker pull us-central1-docker.pkg.dev/prosocial-443205/reg/zotmcp:latest
```

### Troubleshooting:

**"ZOTERO_LIBRARY_ID not set"**
→ Export the environment variable or add to ~/.bashrc

**"Permission denied (GCS)"**
→ Run `gcloud auth application-default login`

**"PDF download failed"**
→ Check Zotero API key has read permissions

**"Out of memory"**
→ Reduce `pipeline.concurrency` in conf/vectorize.yaml

### Advanced options:

Edit `conf/vectorize.yaml` to customize:
- `max_records`: Limit number of items to process
- `concurrency`: Parallel processing (default: 5)
- `chunk_size`: Text chunk size (default: 1000)
- `embedding_batch_size`: Batch size for embeddings (default: 100)

## package_for_distribution.sh

See main README for usage.
