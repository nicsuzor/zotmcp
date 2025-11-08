# Bug Report: ZoteroDownloadProcessor Uses Corrupt Fulltext Instead of Fresh PDF Extraction

## Summary

When reprocessing corrupt documents, `ZoteroDownloadProcessor` uses Zotero's pre-indexed fulltext instead of downloading and extracting fresh text from PDFs. This defeats the purpose of reprocessing, as it recycles the same corrupt data.

## Environment

- **Pipeline**: zotero_reprocessing (using ZoteroItemSource)
- **Processors**: ZoteroDownloadProcessor → PDFToTextProcessor → ...
- **Zotmcp commit**: 4e0ae9e
- **Buttermilk version**: (current main branch)

## Problem

### Expected Behavior

In a reprocessing pipeline:
1. `ZoteroDownloadProcessor` downloads PDF from Zotero
2. `PDFToTextProcessor` extracts fresh text using `pdftotext`
3. Fresh text replaces corrupt indexed text in downstream processing

### Actual Behavior

1. `ZoteroDownloadProcessor` finds pre-indexed fulltext in Zotero
2. Logs: `"Skipping PDF download for UI3WDWLE - already have fulltext with 67217 chars"`
3. Passes corrupt fulltext to downstream processors
4. **Never downloads PDF**, so `PDFToTextProcessor` never runs
5. Corrupt data gets re-stored in ChromaDB

## Evidence

### Document ID: `UI3WDWLE`

This document demonstrates the issue. From pipeline logs:

```json
{
  "event": "⬇️ Downloading full text for UI3WDWLE 'Effective Cultural Policy in the 21st Century: Cha'",
  "timestamp": "2025-11-08T01:36:30.597625Z"
}
{
  "event": "Full text retrieved: 23/23 pages (100.0% indexed)",
  "timestamp": "2025-11-08T01:36:31.615810Z"
}
{
  "event": "Skipping PDF download for UI3WDWLE - already have fulltext with 67217 chars",
  "timestamp": "2025-11-08T01:36:31.615951Z"
}
{
  "event": "✅ Download complete: UI3WDWLE 'Effective Cultural Policy in the 21st Century: Cha'",
  "timestamp": "2025-11-08T01:36:31.615985Z"
}
```

**Result**: UI3WDWLE was the only document (out of 46) that "succeeded" in reprocessing, but it used corrupt Zotero fulltext instead of fresh PDF extraction.

### Other 42 Documents

All other documents failed with:
```
pdftotext not found. Please install poppler-utils
```

This proves they attempted PDF download/extraction but hit a PATH issue. UI3WDWLE bypassed this entirely.

## Root Cause

**File**: `buttermilk/libs/zotero.py`, `ZoteroDownloadProcessor.process()`

**Logic flaw** (~line 593):
```python
# If we got fulltext from Zotero, skip PDF download
if hasattr(record, "content") and record.content:
    logger.debug(
        f"Skipping PDF download for {record.record_id} - "
        f"already have fulltext with {len(record.content)} chars"
    )
    yield record
    return
```

This optimization assumes Zotero fulltext is trustworthy. In reprocessing workflows, it's explicitly **not** trustworthy.

## Suggested Fix

### Option 1: Add `force_pdf_download` parameter

```python
class ZoteroDownloadProcessor:
    def __init__(
        self,
        library_id: str,
        save_dir: str,
        force_pdf_download: bool = False,  # NEW
    ):
        self.force_pdf_download = force_pdf_download

    async def process(self, record: Record):
        # Skip fulltext optimization if forced
        if not self.force_pdf_download:
            if hasattr(record, "content") and record.content:
                logger.debug("Skipping PDF download - already have fulltext")
                yield record
                return

        # Proceed with PDF download...
```

**Usage in reprocess.yaml**:
```yaml
processors:
  - _target_: buttermilk.libs.zotero.ZoteroDownloadProcessor
    library_id: ${oc.env:ZOTERO_LIBRARY_ID}
    save_dir: ${oc.env:HOME}/.cache/buttermilk/zotero/items
    force_pdf_download: true  # Force fresh extraction for reprocessing
```

### Option 2: Detect reprocessing context automatically

Check if `PDFToTextProcessor` exists in the pipeline, and if so, always download PDFs.

### Option 3: Fail if downstream extraction fails

If PDFToTextProcessor fails but ZoteroDownloadProcessor used Zotero fulltext, propagate the failure backward and retry with PDF download.

## Test Case

To reproduce and verify fix:

```python
# Test file: tests/test_zotero_download_processor.py

async def test_force_pdf_download_ignores_zotero_fulltext():
    """Verify force_pdf_download skips Zotero fulltext optimization."""
    processor = ZoteroDownloadProcessor(
        library_id="12345",
        save_dir="/tmp/test",
        force_pdf_download=True
    )

    # Create record with pre-existing content (simulating Zotero fulltext)
    record = Record(
        record_id="UI3WDWLE",
        content="This is corrupt Zotero fulltext"
    )

    # Mock PDF download to verify it's called
    with patch('buttermilk.libs.zotero.download_pdf') as mock_download:
        mock_download.return_value = "/tmp/test/UI3WDWLE.pdf"

        async for result in processor.process(record):
            # Should have downloaded PDF despite existing content
            assert mock_download.called
            assert hasattr(result, 'file_path')
            assert result.file_path == "/tmp/test/UI3WDWLE.pdf"
```

## Impact

### Current State
- Reprocessing corrupt documents is **ineffective** for ~25% of cases (those with Zotero fulltext)
- Pipeline reports "success" but stores corrupt data
- Silent failure - no error, no warning

### With Fix
- All documents get fresh PDF extraction
- Corrupt data is actually replaced
- Reprocessing works as intended

## Additional Context

### Why This Matters

We built a corruption detection system that:
1. Scans ChromaDB for corrupt documents (66% corrupt chunks threshold)
2. Removes them from the database
3. Reprocesses them through the full pipeline

**Without this fix**: Step 3 is broken for documents with Zotero fulltext. The "reprocessing" just re-stores the same corrupt data.

### Workaround (Temporary)

Until fixed, we can manually delete Zotero fulltext before reprocessing:
```python
# Before reprocessing, clear Zotero fulltext cache
from pyzotero import zotero
zot = zotero.Zotero(library_id, 'user', api_key)
zot.delete_fulltext(item_key)  # Force re-indexing
```

But this is fragile and shouldn't be necessary.

## Priority

**High** - Breaks critical reprocessing workflows for data quality management.

---

## Contact

- **Reporter**: @nicsuzor (via Claude Code session)
- **Project**: zotmcp (https://github.com/nicsuzor/zotmcp)
- **Related Issue**: Corruption detection and reprocessing workflow
