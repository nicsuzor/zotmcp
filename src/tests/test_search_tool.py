"""Test get_search_tool initialization and search functionality."""

import pytest
from pathlib import Path
from fastmcp import Client
from buttermilk import init_async
import main


async def test_get_search_tool_returns_instance(mcp_server):
    """Test that get_search_tool returns a ChromaDBSearchTool instance."""
    async with Client(mcp_server) as client:
        search_tool = main.get_search_tool()

        assert search_tool is not None
        assert search_tool.collection_name is not None
        assert search_tool.embedding_model is not None


async def test_get_search_tool_caches_instance(mcp_server):
    """Test that get_search_tool returns the same instance on subsequent calls."""
    async with Client(mcp_server) as client:
        tool1 = main.get_search_tool()

    async with Client(mcp_server) as client:
        tool2 = main.get_search_tool()

    assert tool1 is tool2


async def test_bm_has_cfg_attribute(mcp_server):
    """Test that bm has the cfg attribute after initialization.

    This catches the "'coroutine' object has no attribute 'cfg'" error
    that occurs when bm is not properly awaited.
    """
    async with Client(mcp_server) as client:
        assert hasattr(main.bm, "cfg")
        assert hasattr(main.bm.cfg, "storage")
        assert hasattr(main.bm.cfg.storage, "zotero_vectors")


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


async def test_get_collection_works(mcp_server):
    """Test that get_collection returns a valid ChromaDB collection.

    This verifies that the search_tool.collection accessor works.
    """
    async with Client(mcp_server) as client:
        collection = main.get_collection()

        assert collection is not None
        assert hasattr(collection, "count")
        assert hasattr(collection, "get")
        assert hasattr(collection, "query")
