"""Test corruption detection on actual ChromaDB chunks.

This validates that our enhanced detection catches the corruption we observed
in real chunks from the database.
"""

import pytest
from buttermilk import logger
import main
from text_quality import detect_text_corruption, is_document_corrupt


@pytest.mark.parametrize(
    "item_key,expect_any_corruption",
    [
        ("MBGHP5HR", True),  # Has corruption in some chunks
        ("EFWDZDU2", True),  # Has corruption in some chunks
        ("IU2WFSYE", True),  # Has corruption in some chunks
        ("UFEQ4F94", False),  # Known clean item
    ],
)
async def test_real_item_corruption_detection(
    mcp_server_local, item_key, expect_any_corruption
):
    """Test that corruption detection works on real ChromaDB items.

    Checks all chunks for an item and verifies whether any corruption is found.

    Uses mcp_server_local: Tests require direct ChromaDB collection access.
    """
    # Get the search tool to access the collection
    search_tool = main.get_search_tool()
    await search_tool.ensure_cache_initialized()
    collection = search_tool.collection

    # Query for this specific item
    results = collection.get(
        where={"document_id": {"$eq": item_key}}, include=["documents", "metadatas"]
    )

    # Verify we got results
    assert len(results["ids"]) > 0, f"Item {item_key} not found in ChromaDB"

    # Check all chunks for corruption
    corrupted_chunks = 0
    total_chunks = len(results["documents"])

    for idx, (chunk_text, chunk_id) in enumerate(
        zip(results["documents"], results["ids"])
    ):
        corruption_result = detect_text_corruption(chunk_text)

        if corruption_result["is_corrupted"]:
            corrupted_chunks += 1
            # Log first corrupted chunk for debugging
            if corrupted_chunks == 1:
                logger.info(
                    f"\nItem {item_key} - First corrupted chunk {idx} (ID: {chunk_id}):"
                )
                logger.info(
                    f"  corruption_percentage: {corruption_result['corruption_percentage']:.1f}%"
                )
                logger.info(f"  cid_count: {corruption_result['cid_count']}")
                logger.info(
                    f"  newline_ratio: {corruption_result['newline_ratio']:.1f}%"
                )
                logger.info(
                    f"  avg_line_length: {corruption_result['avg_line_length']:.1f}"
                )
                logger.info(
                    f"  detected_language: {corruption_result['detected_language']}"
                )

    has_corruption = corrupted_chunks > 0
    logger.info(
        f"\nItem {item_key}: {corrupted_chunks}/{total_chunks} chunks corrupted"
    )

    # Assert expected corruption status
    assert has_corruption == expect_any_corruption, (
        f"Expected item {item_key} to {'have' if expect_any_corruption else 'not have'} corruption, "
        f"but found {corrupted_chunks}/{total_chunks} corrupted chunks"
    )


async def test_diagnostic_scan_sample_with_enhanced_detection(mcp_server_local):
    """Run diagnostic on a small sample to verify enhanced detection catches more corruption.

    Uses mcp_server_local: Tests require direct ChromaDB collection access.
    """
    search_tool = main.get_search_tool()
    await search_tool.ensure_cache_initialized()
    collection = search_tool.collection

    # Test items we know have issues
    test_items = ["MBGHP5HR", "EFWDZDU2", "IU2WFSYE"]
    corruption_found = 0

    for item_key in test_items:
        results = collection.get(
            where={"document_id": {"$eq": item_key}}, include=["documents", "metadatas"]
        )

        if len(results["ids"]) == 0:
            logger.warning(f"Item {item_key} not found")
            continue

        # Check all chunks for this item
        item_corrupted = False
        for doc in results["documents"]:
            result = detect_text_corruption(doc)
            if result["is_corrupted"]:
                item_corrupted = True
                break

        if item_corrupted:
            corruption_found += 1
            logger.info(f"✓ Item {item_key} correctly detected as corrupted")
        else:
            logger.warning(
                f"✗ Item {item_key} NOT detected as corrupted (may be false negative)"
            )

    # We expect to find corruption in at least some of these items
    assert corruption_found > 0, (
        "Enhanced detection should find corruption in known bad items"
    )
    logger.info(
        f"\nEnhanced detection found corruption in {corruption_found}/{len(test_items)} test items"
    )


@pytest.mark.parametrize(
    "item_key,expected_is_corrupt,expected_corruption_rate",
    [
        ("MBGHP5HR", False, 65.0),  # 65% corrupt → just below 66% threshold
        ("EFWDZDU2", True, 66.7),  # 67% corrupt → just above 66% threshold
        ("IU2WFSYE", False, 3.6),  # 3.6% corrupt → well below threshold
        ("UFEQ4F94", False, 0.0),  # 0% corrupt → clean
    ],
)
async def test_document_level_corruption_detection(
    mcp_server_local, item_key, expected_is_corrupt, expected_corruption_rate
):
    """Test document-level corruption detection using is_document_corrupt().

    Validates that is_document_corrupt() correctly identifies corrupt documents
    using real ChromaDB items with known corruption rates.

    Uses mcp_server_local: Tests require direct ChromaDB collection access.

    Args:
        item_key: Zotero item key to test
        expected_is_corrupt: Expected document-level corruption decision at 66% threshold
        expected_corruption_rate: Approximate expected corruption percentage
    """
    # Get the search tool to access the collection
    search_tool = main.get_search_tool()
    await search_tool.ensure_cache_initialized()
    collection = search_tool.collection

    # Query for this specific item
    results = collection.get(
        where={"document_id": {"$eq": item_key}}, include=["documents", "metadatas"]
    )

    # Verify we got results
    assert len(results["ids"]) > 0, f"Item {item_key} not found in ChromaDB"

    # Get all chunks for this document
    chunks = results["documents"]

    # Call is_document_corrupt with 66% threshold (default)
    doc_result = is_document_corrupt(chunks, threshold=66.0)

    # Log the results
    logger.info(f"\nDocument-level analysis for {item_key}:")
    logger.info(f"  is_corrupt: {doc_result['is_corrupt']}")
    logger.info(f"  corruption_rate: {doc_result['corruption_rate']:.1f}%")
    logger.info(
        f"  corrupted_chunks: {doc_result['corrupted_chunks']}/{doc_result['total_chunks']}"
    )
    logger.info(f"  threshold: {doc_result['threshold']}")

    # Verify document-level decision matches expected
    assert doc_result["is_corrupt"] == expected_is_corrupt, (
        f"Expected item {item_key} to be {'corrupt' if expected_is_corrupt else 'clean'}, "
        f"but is_document_corrupt returned {doc_result['is_corrupt']} "
        f"(corruption_rate: {doc_result['corruption_rate']:.1f}% vs threshold: {doc_result['threshold']})"
    )

    # Verify corruption rate is approximately as expected (within ±10%)
    rate_diff = abs(doc_result["corruption_rate"] - expected_corruption_rate)
    assert rate_diff <= 10.0, (
        f"Expected corruption rate around {expected_corruption_rate}%, "
        f"but got {doc_result['corruption_rate']:.1f}%"
    )
