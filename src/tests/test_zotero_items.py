"""Tests for ZoteroItemSource - fetches specific Zotero items by key.

This Source class is used for reprocessing specific documents (e.g., corrupt ones)
without iterating through the entire Zotero library.
"""
import pytest
from pathlib import Path
from buttermilk._core.types import BaseRecord


@pytest.mark.asyncio
async def test_zotero_item_source_reads_keys_from_file():
    """Test ZoteroItemSource reads item keys from text file."""
    # Arrange
    from src.zotero_items import ZoteroItemSource

    # Create test file with sample keys
    test_file = Path(__file__).parent / "fixtures" / "test_item_keys.txt"
    test_file.parent.mkdir(exist_ok=True)
    test_file.write_text("KEY1\nKEY2\n  KEY3  \n\nKEY4\n")

    # Act
    source = ZoteroItemSource(
        library_id="test_library",
        item_keys_file=str(test_file)
    )

    # Assert
    assert source.item_keys == ["KEY1", "KEY2", "KEY3", "KEY4"]
    assert len(source.item_keys) == 4


@pytest.mark.asyncio
async def test_zotero_item_source_fetches_items_by_key(bm_vectorize):
    """Test ZoteroItemSource fetches specific items from Zotero API."""
    # Arrange
    from src.zotero_items import ZoteroItemSource

    # Use the first 2 keys from documents_to_remove_ids.txt
    test_file = Path(__file__).parent.parent.parent / "documents_to_remove_ids.txt"
    keys = test_file.read_text().strip().split("\n")[:2]

    # Create temp file with just 2 keys
    temp_file = Path(__file__).parent / "fixtures" / "temp_keys.txt"
    temp_file.parent.mkdir(exist_ok=True)
    temp_file.write_text("\n".join(keys))

    # Act
    import os
    source = ZoteroItemSource(
        library_id=os.getenv("ZOTERO_LIBRARY_ID"),
        item_keys_file=str(temp_file)
    )

    records = []
    async for record in source.fetch_items():
        records.append(record)

    # Assert
    assert len(records) == 2, f"Expected 2 records, got {len(records)}"

    # Verify records have expected structure
    for record in records:
        assert isinstance(record, BaseRecord)
        assert record.record_id in keys
        assert "zotero_item" in record.metadata
        assert "title" in record.metadata["zotero_item"]

    # Cleanup
    temp_file.unlink(missing_ok=True)
