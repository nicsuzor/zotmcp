# Corruption Removal and Reprocessing Workflow

This guide describes the complete workflow for removing corrupted documents and reprocessing them.

## Overview

The workflow consists of three main steps:
1. **Remove** corrupted documents from ChromaDB
2. **Clear** cached files for those documents
3. **Reprocess** documents individually through the pipeline

## Prerequisites

- Document IDs to remove listed in `documents_to_remove_ids.txt` (one per line)
- Current file contains 15 corrupt document IDs

## Step 1: Remove Corrupted Documents from ChromaDB

Remove all chunks associated with corrupt documents from the ChromaDB collection.

### Dry-run (see what would be deleted):
```bash
uv run python scripts/remove_corrupt_docs.py --input documents_to_remove_ids.txt
```

### Execute (actually delete):
```bash
uv run python scripts/remove_corrupt_docs.py --input documents_to_remove_ids.txt --execute
```

**Expected output:**
- Total documents processed: 15
- Documents found in DB: 15
- Total chunks affected: ~14,791

## Step 2: Clear Cached Files

Clear cached PDFs, embeddings, and records for the corrupt documents.

### Dry-run (see what would be deleted):
```bash
uv run python scripts/clear_caches.py --input documents_to_remove_ids.txt
```

### Execute (actually delete):
```bash
uv run python scripts/clear_caches.py --input documents_to_remove_ids.txt --execute
```

**Expected output:**
- Cache files affected:
  - PDFs: 0 (already removed or not cached)
  - Embeddings: 0 (generated on-the-fly)
  - Records: ~23 (record cache files)

## Step 3: Reprocess Documents Individually

Process each document through the full pipeline with the new 80% quality threshold.

### Process a single document:
```bash
uv run python scripts/process_single_doc.py 8ZBKLI6J
```

### Process all 15 documents:
```bash
# Read from documents_to_remove_ids.txt and process each
while read doc_id; do
  echo "Processing $doc_id..."
  uv run python scripts/process_single_doc.py "$doc_id"
  echo "---"
done < documents_to_remove_ids.txt
```

**Pipeline stages (7 total):**
1. `ZoteroDownloadProcessor` - Download PDF from Zotero
2. `PDFToTextProcessor` - Extract text from PDF
3. `Citator` - Generate citation using LLM
4. `SemanticSplitter` - Chunk text semantically
5. `QualityFilterProcessor` - Filter if corruption >= 80%
6. `EmbeddingGenerator` - Generate embeddings
7. `ChromaDBEmbeddings` - Store in ChromaDB

**Expected outcomes:**
- Clean documents: Successfully processed and stored
- Still-corrupt documents (>= 80%): Filtered at QualityFilterProcessor stage
- Invalid documents: May fail at ZoteroDownloadProcessor (missing metadata)

## Configuration

### Quality Threshold

The corruption threshold is now configurable in `conf/vectorize.yaml`:

```yaml
- _target_: src.quality_processor.QualityFilterProcessor
  corruption_threshold: 80.0  # Changed from 95.0
  pattern_threshold: 80.0
```

**Interpretation:**
- Documents with >= 80% corrupt chunks are filtered out
- Documents with < 80% corrupt chunks are kept and processed
- This is more aggressive than the previous 95% threshold

## Complete Workflow Example

```bash
# 1. Remove from ChromaDB (execute mode)
uv run python scripts/remove_corrupt_docs.py --input documents_to_remove_ids.txt --execute

# 2. Clear caches (execute mode)
uv run python scripts/clear_caches.py --input documents_to_remove_ids.txt --execute

# 3. Reprocess all documents
while read doc_id; do
  echo "=== Processing $doc_id ==="
  uv run python scripts/process_single_doc.py "$doc_id"
  echo ""
done < documents_to_remove_ids.txt
```

## Monitoring Progress

Each script provides detailed output:

### Remove script:
- Documents found/missing in DB
- Total chunks affected
- Dry-run vs execute mode confirmation

### Cache script:
- Files found by cache type
- Total files affected
- Dry-run vs execute mode confirmation

### Pipeline script:
- Stages completed
- Success/failure status
- Quality metrics (chunk count)
- Filtering reason (if filtered)

## Safety Features

All scripts include:
- **Dry-run mode by default**: Must explicitly use `--execute` flag
- **Clear reporting**: Shows exactly what will be affected
- **Error handling**: Reports failures without stopping
- **Fail-fast**: No silent failures or defensive defaults

## Troubleshooting

### Document fails at ZoteroDownloadProcessor
- Cause: Invalid or missing metadata in Zotero
- Action: Fix metadata in Zotero library first

### Document filtered at QualityFilterProcessor
- Cause: Still >= 80% corrupt after reprocessing
- Action: Document may be permanently corrupt, consider manual review

### ChromaDB connection issues
- Cause: Database not accessible
- Action: Check `db=dev` config in conf/zotero.yaml

## Files Created/Modified

### Configuration:
- `conf/vectorize.yaml` - Quality threshold changed to 80%

### Scripts:
- `scripts/remove_corrupt_docs.py` - ChromaDB document removal
- `scripts/clear_caches.py` - Cache file clearing
- `scripts/process_single_doc.py` - Single-document pipeline

### Input Data:
- `documents_to_remove_ids.txt` - 15 corrupt document IDs

## Next Steps

After running the workflow:

1. **Verify removal**: Run corruption diagnostic to confirm documents removed
   ```bash
   uv run python scripts/diagnose_corruption.py --limit 0
   ```

2. **Check reprocessing results**: Review logs for success/failure counts

3. **Monitor quality**: Check if reprocessed documents pass quality threshold

4. **Repeat if needed**: May need multiple cycles for borderline documents
