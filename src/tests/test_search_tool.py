"""Test get_search_tool initialization and search functionality."""

import pytest
from pathlib import Path
from fastmcp import Client
from buttermilk import init_async
import main


async def test_get_search_tool_returns_instance(mcp_server_local):
    """Test that get_search_tool returns a ChromaDBSearchTool instance."""
    search_tool = main.get_search_tool()

    assert search_tool is not None
    assert search_tool.collection_name is not None
    assert search_tool.embedding_model is not None


async def test_get_search_tool_caches_instance(mcp_server_local):
    """Test that get_search_tool returns the same instance on subsequent calls."""
    tool1 = main.get_search_tool()

    tool2 = main.get_search_tool()

    assert tool1 is tool2


async def test_bm_has_cfg_attribute(mcp_server_local):
    """Test that bm has the cfg attribute after initialization.

    This catches the "'coroutine' object has no attribute 'cfg'" error
    that occurs when bm is not properly awaited.
    """
    assert hasattr(main.bm, "cfg")
    assert hasattr(main.bm.cfg, "storage")
    assert "zotero_vectors" in main.bm.cfg.storage


async def test_search_function_works(mcp_server):
    """Test that the search function actually works end-to-end.

    This is the critical test that catches the coroutine error in production.
    If bm is a coroutine instead of an initialized instance, this will fail
    with "'coroutine' object has no attribute 'cfg'".
    """
    # Use the MCP client to call the search tool
    async with Client(mcp_server) as client:
        result = await client.call_tool(
            "search",
            {
                "query": "content moderation",
                "n_results": 5,
            },
        )

        # Should not have an error
        assert "error" not in result.data, (
            f"Search failed with error: {result.data.get('error')}"
        )

        # Should have expected structure
        assert "results" in result.data
        assert "total_results" in result.data
        assert isinstance(result.data["results"], list)


async def test_get_collection_works(mcp_server_local):
    """Test that get_collection returns a valid ChromaDB collection.

    This verifies that the search_tool.collection accessor works.
    """
    collection = main.get_collection()

    assert collection is not None
    assert hasattr(collection, "count")
    assert hasattr(collection, "get")
    assert hasattr(collection, "query")


async def test_search_result_metadata_is_dict(mcp_server_local):
    """Test that SearchResult.metadata is a dict, not a string.

    This validates that result.metadata.get() works correctly.
    Reproduces bug in main.py lines 227, 231 where result.metadata.get()
    fails because metadata is a string instead of dict.
    """
    # Get the search tool and perform a search
    search_tool = main.get_search_tool()
    results = await search_tool.search(query="content moderation", n_results=5)

    # Verify we got results
    assert len(results) > 0, "Search should return at least one result"

    # Validate each result has metadata as a dict
    for result in results:
        # Check that metadata is a dict type
        assert isinstance(result.metadata, dict), (
            f"SearchResult.metadata must be a dict, got {type(result.metadata).__name__}"
        )

        # Validate that .get() method works (this is what main.py line 227 uses)
        # This should not raise AttributeError
        item_type = result.metadata.get("itemType")
        assert item_type is None or isinstance(item_type, str), (
            "metadata.get('itemType') should return None or a string"
        )

        # Test that extract_citation_metadata works (main.py line 231)
        try:
            # This is what main.py actually does at line 231
            citation, doi_or_url, uri, zotero_key, citation_key, zotero_web_link = (
                main.extract_citation_metadata(result.metadata)
            )
            # Should return values without error
            assert isinstance(citation, str)
            assert doi_or_url is None or isinstance(doi_or_url, str)
            assert uri is None or isinstance(uri, str)
            assert zotero_key is None or isinstance(zotero_key, str)
            assert citation_key is None or isinstance(citation_key, str)
            assert zotero_web_link is None or isinstance(zotero_web_link, str)
        except AttributeError as e:
            pytest.fail(
                f"extract_citation_metadata raised AttributeError: {e}. "
                f"metadata type: {type(result.metadata)}, "
                f"metadata keys: {list(result.metadata.keys()) if isinstance(result.metadata, dict) else 'NOT A DICT'}"
            )
