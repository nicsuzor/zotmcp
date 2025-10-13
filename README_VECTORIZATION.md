# Zotero Vectorization Guide

## Quick Test (10 documents)

```bash
cd /home/nic/src/writing/projects/zotmcp

# Set credentials
export ZOTERO_API_KEY="your-api-key"
export ZOTERO_LIBRARY_ID="your-library-id"

# Test with 10 documents
uv run python scripts/run_vectorization.py pipeline.max_records=10
```

## Full Vectorization

```bash
# Process all new records (existing ones skipped automatically)
uv run python scripts/run_vectorization.py
```

## How Deduplication Works

The config has this setup:

```yaml
vectoriser:
  deduplication_strategy: record_id

source:
  vector_store: ${vectoriser}  # Enables early deduplication
```

**What happens:**
1. ZotDownloader queries ChromaDB: "Does this record_id exist?"
2. **If YES** → Skips entirely (no API call, no PDF download, no processing)
3. **If NO** → Downloads PDF → Chunks → Embeds → Uploads

## Monitoring Progress

You'll see logs like:
```
🔵 Creating download task for ABC123 'New Paper Title'
Document XYZ789 already exists in vector store, skipping.
Finished Zotero processing. Processed: 5, Skipped (already exist): 45
```

## Configuration

Edit `conf/vectorize.yaml` to customize:
- `pipeline.max_records`: Limit number of records (or null for all)
- `source.download_concurrency`: Parallel downloads (default: 8)
- `vectoriser.sync_batch_size`: Batch size for ChromaDB uploads (default: 50)
- `vectoriser.deduplication_strategy`: `record_id`, `content_hash`, or `both`


The pipeline syncs to the upstream GCS location automatically.
