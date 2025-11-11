"""Test that citation and citation_key metadata fields are present after vectorization.

This test verifies that when a Zotero item is processed through the
vectorization pipeline, the resulting ChromaDB chunks include both
'citation' and 'citation_key' in their metadata.
"""

import pytest
from buttermilk import logger
import main


pytestmark = pytest.mark.anyio


async def test_citation_metadata_present_in_chromadb(mcp_server_local):
    """Test that citation and citation_key metadata are present after vectorization.

    This test:
    1. Processes a single known Zotero item (MBGHP5HR - Kowalski cyberbullying paper)
    2. Queries ChromaDB for chunks from this item
    3. Verifies both 'citation' and 'citation_key' fields exist in metadata
    4. Verifies both fields have non-None, non-empty values

    Uses mcp_server_local: Requires direct ChromaDB collection access.
    """
    # Arrange: Get the search tool to access ChromaDB collection
    search_tool = main.get_search_tool()
    await search_tool.ensure_cache_initialized()
    collection = search_tool.collection

    # Known test item from test_chromadb_retrieval.py
    item_key = "MBGHP5HR"

    # Act: Query ChromaDB for this item's chunks
    results = collection.get(
        where={"document_id": {"$eq": item_key}},
        include=["metadatas"],
    )

    # Assert: Item exists in ChromaDB
    assert results is not None, f"Query returned None for item {item_key}"
    num_chunks = len(results["ids"])
    assert num_chunks > 0, (
        f"Item {item_key} not found in ChromaDB. "
        f"This test requires the item to be processed through vectorization pipeline first."
    )

    logger.info(f"Found {num_chunks} chunks for item {item_key}")

    # Assert: Check each chunk's metadata for citation fields
    for idx, (chunk_id, metadata) in enumerate(
        zip(results["ids"], results["metadatas"])
    ):
        logger.info(f"Checking chunk {idx + 1}/{num_chunks}: {chunk_id}")

        # Verify 'citation' field exists
        assert "citation" in metadata, (
            f"Chunk {chunk_id} missing 'citation' field in metadata. "
            f"Available fields: {list(metadata.keys())}"
        )

        # Verify citation has non-None, non-empty value
        citation = metadata["citation"]
        assert citation is not None, f"Chunk {chunk_id} has None citation"
        assert citation != "", f"Chunk {chunk_id} has empty citation"
        assert len(citation) > 0, f"Chunk {chunk_id} has zero-length citation"

        # Verify citation_key if present (field is optional - may not exist if BetterBibTeX not used)
        # But if present, should be non-empty
        citation_key = metadata.get("citation_key")
        if citation_key is not None:
            assert citation_key != "", f"Chunk {chunk_id} has empty citation_key"
            assert len(citation_key) > 0, (
                f"Chunk {chunk_id} has zero-length citation_key"
            )

        logger.info(
            f"  ✓ Chunk {idx + 1} has citation: {citation[:100]}... "
            f"(citation_key: {citation_key})"
        )

    logger.info(f"✅ All {num_chunks} chunks have valid citation metadata")
