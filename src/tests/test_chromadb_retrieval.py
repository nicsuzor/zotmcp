"""Test direct ChromaDB retrieval of specific items.

This test suite is designed to verify that items can be retrieved from
the live ChromaDB collection and to inspect the quality of their content.
"""

import pytest
from buttermilk import logger
import main


# Test data: (document_id, expected_severity, description)
# Note: document_id is the metadata field containing the Zotero item key
TEST_ITEMS = [
    # Items from corruption diagnostic - low severity
    ("IU2WFSYE", "low", "Low corruption item from report"),
    ("MBGHP5HR", "low", "Kowalski cyberbullying paper - from suzor search"),
    ("EFWDZDU2", "low", "Fung transparency book - from suzor search"),
    # Known existing item from discovery test
    ("UFEQ4F94", "exists", "Cable TV vertical integration paper - known to exist"),
]


async def test_discover_chromadb_metadata_structure(mcp_server_local):
    """Test to discover what metadata fields exist in ChromaDB.

    This helps us understand the relationship between document_id, item_key,
    and other metadata fields.
    """
    search_tool = main.get_search_tool()
    await search_tool.ensure_cache_initialized()
    collection = search_tool.collection

    # Get a few sample records
    # Note: IDs are always returned, don't need to include them
    results = collection.get(limit=5, include=["documents", "metadatas"])

    assert len(results["ids"]) > 0, "No records found in ChromaDB"

    logger.info(f"Found {len(results['ids'])} sample records")

    for idx, (chunk_id, doc, meta) in enumerate(
        zip(results["ids"], results["documents"], results["metadatas"])
    ):
        logger.info(f"\nRecord {idx + 1}:")
        logger.info(f"  Chunk ID: {chunk_id}")
        logger.info(f"  Metadata keys: {list(meta.keys())}")
        logger.info(f"  document_id: {meta.get('document_id')}")
        logger.info(
            f"  zotero_data: {meta.get('zotero_data', {})[:200] if isinstance(meta.get('zotero_data'), str) else meta.get('zotero_data')}"
        )
        logger.info(f"  Doc preview: {doc[:100] if doc else '(empty)'}...")


@pytest.mark.parametrize(
    "item_key,expected_severity,description",
    TEST_ITEMS or [("skip", "skip", "No test items")],
)
async def test_retrieve_item_from_chromadb(
    mcp_server_local, item_key, expected_severity, description
):
    """Test that we can retrieve specific items from ChromaDB.

    This test queries ChromaDB directly for known item keys and inspects:
    - Whether the item exists in ChromaDB
    - How many chunks it has
    - The content quality of those chunks

    Uses mcp_server_local: Tests require direct ChromaDB collection access.
    """
    # Get the search tool to access the collection
    search_tool = main.get_search_tool()
    await search_tool.ensure_cache_initialized()
    collection = search_tool.collection

    # Query for this specific item using document_id metadata field
    results = collection.get(
        where={"document_id": {"$eq": item_key}}, include=["documents", "metadatas"]
    )

    # Basic assertions
    assert results is not None, f"Query returned None for item {item_key}"

    num_chunks = len(results["ids"])
    logger.info(f"Item {item_key} ({description}): {num_chunks} chunks found")

    # For items we know exist, we expect at least 1 chunk
    if expected_severity == "exists":
        assert num_chunks > 0, f"Item {item_key} should exist but has 0 chunks"

    # For items we're investigating, just report what we find
    if num_chunks == 0:
        logger.warning(f"Item {item_key} ({expected_severity}) NOT FOUND in ChromaDB")
        return

    logger.info(f"Item {item_key} ({expected_severity}) FOUND with {num_chunks} chunks")

    # Inspect the chunks (limit to first 3 for readability)
    for idx, (chunk_id, doc, meta) in enumerate(
        zip(results["ids"][:3], results["documents"][:3], results["metadatas"][:3])
    ):
        chunk_length = len(doc) if doc else 0
        doc_preview = doc[:300] if doc else "(empty)"

        logger.info(f"  Chunk {idx + 1}:")
        logger.info(f"    ID: {chunk_id}")
        logger.info(f"    Length: {chunk_length} chars")

        # Check for obvious corruption patterns
        if doc:
            cid_count = doc.count("(cid:")
            newline_count = doc.count("\n")
            newline_ratio = newline_count / len(doc) if len(doc) > 0 else 0

            logger.info(f"    CID patterns: {cid_count}")
            logger.info(f"    Newlines: {newline_count} ({newline_ratio:.1%})")

            if cid_count > 0:
                logger.warning("    ⚠️  Contains CID corruption")
            if newline_ratio > 0.1:
                logger.warning("    ⚠️  High newline ratio indicates corruption")

        logger.info(f"    Preview:\n{doc_preview}\n")

    # Log metadata from first chunk
    if results["metadatas"]:
        first_meta = results["metadatas"][0]
        logger.info(
            f"  Metadata: item_key={first_meta.get('item_key')}, "
            f"version={first_meta.get('version')}, "
            f"chunk_index={first_meta.get('chunk_index')}"
        )


async def test_search_returns_items_that_exist_in_chromadb(mcp_server_local):
    """Test that items returned by search actually exist in ChromaDB.

    This is a sanity check to ensure the search tool and get_item tool
    are operating on the same collection.
    """
    search_tool = main.get_search_tool()
    await search_tool.ensure_cache_initialized()
    collection = search_tool.collection

    # Do a simple search
    search_results = await search_tool.search(query="suzor", n_results=5)

    assert len(search_results) > 0, "Search returned no results"

    # For each result, verify we can retrieve it directly
    for result in search_results:
        meta = result.metadata
        item_key = meta.get("item_key") or meta.get("document_id")
        if not item_key:
            logger.warning(f"Search result missing item_key or document_id: {result}")
            continue

        # Try to retrieve this item directly using document_id
        direct_results = collection.get(
            where={"document_id": {"$eq": item_key}}, include=["documents", "metadatas"]
        )

        num_chunks = len(direct_results["ids"])
        logger.info(
            f"Search returned {item_key}: {num_chunks} chunks found via direct query"
        )

        assert (
            num_chunks > 0
        ), f"Search returned item {item_key} but it has no chunks in ChromaDB"
