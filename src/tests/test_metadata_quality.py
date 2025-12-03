"""Test ChromaDB metadata quality across the collection.

This test samples items from the ChromaDB collection and verifies that
citation metadata is properly populated. This helps identify issues with
the vectorization pipeline that result in "Citation not available" errors.

Relates to: GitHub issue #3 - Missing citation metadata
"""

import pytest
from buttermilk import logger
import main


pytestmark = pytest.mark.anyio


async def test_citation_metadata_quality(mcp_server_local):
    """Test that citation metadata is properly populated across the collection.

    This test:
    1. Samples a random set of items from ChromaDB (up to 500 chunks)
    2. Groups chunks by document_id (Zotero item key)
    3. Reports percentage of items with valid citation metadata
    4. Fails if fewer than 90% of unique items have valid citations

    Uses mcp_server_local: Requires direct ChromaDB collection access.
    """
    # Arrange: Get the search tool to access ChromaDB collection
    search_tool = main.get_search_tool()
    await search_tool.ensure_cache_initialized()
    collection = search_tool.collection

    # Get total count
    total_chunks = collection.count()
    logger.info(f"Total chunks in collection: {total_chunks}")

    # Sample chunks (get up to 5000 to balance coverage and speed)
    sample_size = min(5000, total_chunks)
    results = collection.get(
        limit=sample_size,
        include=["metadatas"],
    )

    # Group by document_id and check citation for each unique item
    items_by_key: dict[str, dict] = {}
    for metadata in results["metadatas"]:
        doc_id = metadata.get("document_id")
        if doc_id and doc_id not in items_by_key:
            items_by_key[doc_id] = metadata

    total_items = len(items_by_key)
    logger.info(f"Sampled {sample_size} chunks from {total_items} unique items")

    # Analyze citation quality
    valid_citations = 0
    missing_citations = []
    empty_citations = []
    placeholder_citations = []

    for doc_id, metadata in items_by_key.items():
        citation = metadata.get("citation")

        if citation is None:
            missing_citations.append(doc_id)
        elif citation == "":
            empty_citations.append(doc_id)
        elif citation in ("Citation not available", "N/A", "Unknown"):
            placeholder_citations.append(doc_id)
        else:
            valid_citations += 1

    # Calculate percentages
    valid_pct = (valid_citations / total_items * 100) if total_items > 0 else 0
    missing_pct = (len(missing_citations) / total_items * 100) if total_items > 0 else 0
    empty_pct = (len(empty_citations) / total_items * 100) if total_items > 0 else 0
    placeholder_pct = (
        (len(placeholder_citations) / total_items * 100) if total_items > 0 else 0
    )

    # Log detailed results
    logger.info(f"Citation quality report for {total_items} items:")
    logger.info(f"  ✓ Valid citations: {valid_citations} ({valid_pct:.1f}%)")
    logger.info(f"  ✗ Missing (None): {len(missing_citations)} ({missing_pct:.1f}%)")
    logger.info(f"  ✗ Empty string: {len(empty_citations)} ({empty_pct:.1f}%)")
    logger.info(
        f"  ✗ Placeholder text: {len(placeholder_citations)} ({placeholder_pct:.1f}%)"
    )

    # Log sample of problematic items for debugging
    if missing_citations:
        logger.warning(f"Sample items with missing citation: {missing_citations[:5]}")
    if empty_citations:
        logger.warning(f"Sample items with empty citation: {empty_citations[:5]}")
    if placeholder_citations:
        logger.warning(
            f"Sample items with placeholder citation: {placeholder_citations[:5]}"
        )

    # Assert: At least 90% of items should have valid citations
    assert valid_pct >= 90.0, (
        f"Only {valid_pct:.1f}% of items have valid citations. "
        f"Expected at least 90%. "
        f"Missing: {len(missing_citations)}, "
        f"Empty: {len(empty_citations)}, "
        f"Placeholder: {len(placeholder_citations)}"
    )


async def test_citation_key_metadata_coverage(mcp_server_local):
    """Test that citation_key (BetterBibTeX) metadata is present where expected.

    citation_key is optional (only present if using BetterBibTeX), but when
    present it should have a valid non-empty value.
    """
    search_tool = main.get_search_tool()
    await search_tool.ensure_cache_initialized()
    collection = search_tool.collection

    # Sample chunks
    sample_size = min(5000, collection.count())
    results = collection.get(
        limit=sample_size,
        include=["metadatas"],
    )

    # Group by document_id
    items_by_key: dict[str, dict] = {}
    for metadata in results["metadatas"]:
        doc_id = metadata.get("document_id")
        if doc_id and doc_id not in items_by_key:
            items_by_key[doc_id] = metadata

    total_items = len(items_by_key)

    # Count citation_key presence
    has_citation_key = 0
    empty_citation_keys = []

    for doc_id, metadata in items_by_key.items():
        citation_key = metadata.get("citation_key")
        if citation_key is not None:
            if citation_key == "":
                empty_citation_keys.append(doc_id)
            else:
                has_citation_key += 1

    coverage_pct = (has_citation_key / total_items * 100) if total_items > 0 else 0

    logger.info(f"citation_key coverage: {has_citation_key}/{total_items} ({coverage_pct:.1f}%)")

    if empty_citation_keys:
        logger.warning(
            f"Items with empty citation_key: {empty_citation_keys[:5]}"
        )
        # Empty citation_key when field exists is a bug
        assert len(empty_citation_keys) == 0, (
            f"Found {len(empty_citation_keys)} items with empty citation_key. "
            f"If citation_key is present, it should have a value."
        )

    # Log coverage but don't fail - citation_key is optional
    logger.info(f"citation_key is present for {coverage_pct:.1f}% of items (optional field)")


async def test_required_metadata_fields_present(mcp_server_local):
    """Test that required metadata fields are present in all chunks.

    These fields are required for basic search functionality:
    - document_id: Zotero item key
    - chunk_index: Position in document
    """
    search_tool = main.get_search_tool()
    await search_tool.ensure_cache_initialized()
    collection = search_tool.collection

    # Sample chunks
    sample_size = min(5000, collection.count())
    results = collection.get(
        limit=sample_size,
        include=["metadatas"],
    )

    required_fields = ["document_id", "chunk_index"]
    missing_fields_count: dict[str, int] = {field: 0 for field in required_fields}

    for metadata in results["metadatas"]:
        for field in required_fields:
            if field not in metadata or metadata[field] is None:
                missing_fields_count[field] += 1

    # Log results
    for field, count in missing_fields_count.items():
        pct = (count / sample_size * 100) if sample_size > 0 else 0
        logger.info(f"Field '{field}': {sample_size - count}/{sample_size} present ({100 - pct:.1f}%)")

    # Assert all required fields are present
    for field, count in missing_fields_count.items():
        assert count == 0, (
            f"Required field '{field}' missing in {count}/{sample_size} chunks"
        )


async def test_title_metadata_coverage(mcp_server_local):
    """Test that title metadata is available (either flat or nested).

    Title is essential for displaying search results meaningfully.
    """
    from zotmcp.search_utils import get_metadata_field

    search_tool = main.get_search_tool()
    await search_tool.ensure_cache_initialized()
    collection = search_tool.collection

    # Sample chunks
    sample_size = min(5000, collection.count())
    results = collection.get(
        limit=sample_size,
        include=["metadatas"],
    )

    # Group by document_id
    items_by_key: dict[str, dict] = {}
    for metadata in results["metadatas"]:
        doc_id = metadata.get("document_id")
        if doc_id and doc_id not in items_by_key:
            items_by_key[doc_id] = metadata

    total_items = len(items_by_key)

    # Check title availability
    has_title = 0
    missing_titles = []

    for doc_id, metadata in items_by_key.items():
        title = get_metadata_field(metadata, "title")
        if title and title.strip():
            has_title += 1
        else:
            missing_titles.append(doc_id)

    title_pct = (has_title / total_items * 100) if total_items > 0 else 0

    logger.info(f"Title coverage: {has_title}/{total_items} ({title_pct:.1f}%)")

    if missing_titles:
        logger.warning(f"Sample items missing title: {missing_titles[:5]}")

    # At least 95% of items should have titles
    assert title_pct >= 95.0, (
        f"Only {title_pct:.1f}% of items have titles. Expected at least 95%. "
        f"Missing titles: {len(missing_titles)}"
    )
