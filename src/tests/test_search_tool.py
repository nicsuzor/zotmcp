"""Test get_search_tool initialization and search functionality.

Test Fixture Strategy
---------------------
This file uses two fixture types:

1. `mcp_server_local` - For tests requiring direct Python object access:
   - Testing internal functions (main.get_search_tool(), main.get_collection())
   - Validating Python object caching/identity
   - Checking internal attributes (main.bm.cfg)

   These tests MUST use the local fixture because they test implementation
   details not exposed through the MCP client interface.

2. `mcp_server` - For tests validating public MCP API behavior:
   - Testing search tool functionality through MCP client
   - Validating end-to-end workflows

   These tests run TWICE (parametrized):
   - Once against local in-process server [local-server]
   - Once against Docker HTTP server [docker-e2e] (with @pytest.mark.slow)
"""

import pytest
from pathlib import Path
from fastmcp import Client
from buttermilk import init_async
import main


async def test_get_search_tool_returns_instance(mcp_server_local):
    """Test that get_search_tool returns a ChromaDBSearchTool instance.

    Uses mcp_server_local: Tests internal function not exposed via MCP.
    """
    search_tool = main.get_search_tool()

    assert search_tool is not None
    assert search_tool.collection_name is not None
    assert search_tool.embedding_model is not None


async def test_get_search_tool_caches_instance(mcp_server_local):
    """Test that get_search_tool returns the same instance on subsequent calls.

    Uses mcp_server_local: Tests Python object identity (caching behavior).
    """
    tool1 = main.get_search_tool()

    tool2 = main.get_search_tool()

    assert tool1 is tool2


async def test_bm_has_cfg_attribute(mcp_server_local):
    """Test that bm has the cfg attribute after initialization.

    Uses mcp_server_local: Tests internal main.bm.cfg attribute.

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

    Uses mcp_server_local: Tests internal main.get_collection() function.

    This verifies that the search_tool.collection accessor works.
    """
    collection = main.get_collection()

    assert collection is not None
    assert hasattr(collection, "count")
    assert hasattr(collection, "get")
    assert hasattr(collection, "query")


async def test_search_result_metadata_is_dict(mcp_server):
    """Test that search results have properly structured metadata.

    Uses mcp_server (parametrized): Validates search results through MCP client
    interface in both local and Docker environments.

    This validates that result metadata contains expected fields and types,
    catching potential serialization issues where metadata might be incorrectly
    converted to a string instead of remaining a dict.

    Tests the defensive check at main.py:226-231 that prevents
    "'str' object has no attribute 'get'" errors.
    """
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

        # Verify we got results
        assert "results" in result.data
        assert len(result.data["results"]) > 0, "Search should return at least one result"

        # Validate each result has properly structured metadata fields
        for search_result in result.data["results"]:
            # These fields should all be present (though may be None)
            assert "citation" in search_result, "Result missing citation field"
            assert "excerpt" in search_result, "Result missing excerpt field"
            assert "zotero_key" in search_result, "Result missing zotero_key field"

            # Citation should be a string
            assert isinstance(search_result["citation"], str), (
                f"Citation must be a string, got {type(search_result['citation']).__name__}"
            )

            # Optional fields should be None or strings
            for field in ["doi_or_url", "uri", "zotero_key", "citation_key", "zotero_link", "zotero_web_link"]:
                if field in search_result and search_result[field] is not None:
                    assert isinstance(search_result[field], str), (
                        f"{field} must be None or string, got {type(search_result[field]).__name__}"
                    )
