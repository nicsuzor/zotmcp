# Reprocessing Pipeline

Thin wrapper around buttermilk vectorization pipeline for reprocessing specific documents with forced fresh extraction.

## Quick Start

```bash
# Reprocess corrupt documents (uses default corrupt_documents_66pct.txt)
uv run python scripts/reprocess.py

# Reprocess custom list
uv run python scripts/reprocess.py my_items.txt

# Use local dev database
uv run python scripts/reprocess.py --db=dev
```

## What It Does

The reprocessing pipeline:

1. **Forces fresh processing** - Ignores all caches (`force_reprocess: true`)
2. **Reads document IDs** - From specified file (one ID per line)
3. **Runs full pipeline** - All 7 stages from download to embedding storage:
   - `ZoteroDownloadProcessor` - Download PDFs from Zotero
   - `PDFToTextProcessor` - Extract text using pdftotext
   - `Citator` - Generate citations via LLM
   - `SemanticSplitter` - Chunk text (500 chars, 200 overlap)
   - `QualityFilterProcessor` - Filter if ≥66% corrupt
   - `EmbeddingGenerator` - Generate embeddings
   - `ChromaDBEmbeddings` - Store in vector database

## Configuration

**File**: `conf/reprocess.yaml`

Key settings:

```yaml
reprocess:
  items_file: corrupt_documents_66pct.txt # Override with CLI arg

pipeline:
  force_reprocess: true # Ignore all caches
  enable_record_cache: false # No per-processor caching

vectoriser:
  deduplication_strategy: none # Don't skip existing records
  enable_record_cache: false # No vectorizer caching
```

## Known Issue: Zotero Fulltext Bypass

⚠️ **CRITICAL BUG** (tracked in `BUTTERMILK_BUG_REPORT.md`):

`ZoteroDownloadProcessor` skips PDF download if Zotero has pre-indexed fulltext:

```
"Skipping PDF download for UI3WDWLE - already have fulltext with 67217 chars"
```

**Impact**: Documents with Zotero fulltext will **not** get fresh PDF extraction, defeating the purpose of reprocessing.

**Workaround**: Until buttermilk adds `force_pdf_download` parameter, manually delete Zotero fulltext cache before reprocessing.

**Test case**: Document ID `UI3WDWLE` demonstrates this issue - it "succeeded" by recycling corrupt Zotero text instead of extracting from PDF.

## Architecture

```
scripts/reprocess.py (thin wrapper)
    ↓
buttermilk.runner.cli
    ↓
conf/reprocess.yaml
    ↓
src.zotero_items.ZoteroItemSource (reads items_file)
    ↓
7-stage vectorization pipeline
    ↓
ChromaDB storage
```

## Comparison: reprocess.py vs run_reprocess.py

| File                       | Purpose                           | Interface                              |
| -------------------------- | --------------------------------- | -------------------------------------- |
| `scripts/reprocess.py`     | **NEW** - Thin CLI wrapper        | Command-line args, uses buttermilk CLI |
| `scripts/run_reprocess.py` | Legacy - Direct Python invocation | Hardcoded config, uses Hydra compose   |

**Use `reprocess.py`** - It's cleaner, more flexible, and easier to maintain.

## Full Workflow Example

```bash
# 1. Scan for corruption (generates corrupt_documents_66pct.txt)
uv run python scripts/diagnose_corruption.py --limit 0 --output corruption_scan.json
cat corruption_scan.json | jq -r '.corrupted_documents[].document_id' > corrupt_documents_66pct.txt

# 2. Remove from ChromaDB
uv run python scripts/remove_corrupt_docs.py --input corrupt_documents_66pct.txt --execute

# 3. Clear caches
uv run python scripts/clear_caches.py --input corrupt_documents_66pct.txt --execute

# 4. Reprocess with fresh extraction
uv run python scripts/reprocess.py corrupt_documents_66pct.txt --db=dev
```

## Cache Control Details

### Pipeline-Level Caching

- `force_reprocess: true` - Ignores processor-level caches
- `enable_record_cache: false` - Disables per-processor record cache

### Vectorizer-Level Caching

- `deduplication_strategy: none` - Doesn't skip existing embeddings
- `enable_record_cache: false` - No record cache for vectorizer

### What Still Gets Cached

- Downloaded PDFs in `~/.cache/buttermilk/zotero/items/` (cleared by `clear_caches.py`)
- LLM citation calls may be cached by buttermilk's LLM layer

## Monitoring Progress

The script runs buttermilk CLI which provides progress output:

```
Pipeline: zotero_reprocessing • Processed: 5 Skipped: 2 Failed: 1
```

For detailed logs, check buttermilk's log files in `/tmp/bm_zotmcp_exec-*.jsonl`

## Dependencies

- **buttermilk** - Pipeline framework
- **click** - CLI argument parsing
- **pdftotext** - System dependency for PDF extraction (install: `apt install poppler-utils`)
- **langdetect** - Python dependency for corruption detection

## See Also

- `WORKFLOW_GUIDE.md` - Complete corruption removal and reprocessing workflow
- `BUTTERMILK_BUG_REPORT.md` - Zotero fulltext bypass issue
- `README_VECTORIZATION.md` - Vectorization pipeline overview
- `CORRUPTION_DETECTION_IMPROVEMENTS.md` - Corruption detection methodology
