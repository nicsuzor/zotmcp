"""Test ChromaDB initialization before search operations.

Test Fixture Strategy
---------------------
This test verifies that ChromaDB must be fully initialized before any search
operations can run. It uses the existing test infrastructure from conftest.py
and connects to live data.

Fixtures Used:
- bm_dev: Buttermilk instance with dev database (from conftest.py)
- mcp_server_local: Local MCP server with initialized buttermilk (from conftest.py)

Test Data:
- Uses EXISTING ChromaDB collection via project configs
- Connects to REAL production search_tool (no fake data)
- NEVER creates new databases/collections for testing
"""

from fastmcp import Client
import main
import pytest


async def test_search_tool_must_be_initialized_before_search(mcp_server_local):
    """Test that search_tool.initialize() must be called before search operations.

    This test verifies the critical initialization requirement:
    1. ChromaDB collection must exist and be accessible
    2. search_tool must be initialized via .initialize()
    3. Collection must have data (count > 0)

    Uses mcp_server_local: Tests internal state of search_tool.
    Uses EXISTING test infrastructure: Connects to live ChromaDB via bm_dev fixture.

    Expected to FAIL with: search_tool not initialized OR collection count is 0.
    """
    # Get the search tool (this should be created but NOT initialized)
    search_tool = main.get_search_tool()

    # Verify search_tool exists
    assert search_tool is not None, "search_tool should exist"

    # CRITICAL CHECK: Verify that initialize() has been called
    # This should FAIL if initialization hasn't happened
    assert hasattr(search_tool, '_initialized'), "search_tool missing _initialized attribute"
    assert search_tool._initialized is True, "search_tool not initialized - must call .initialize() first"

    # Verify ChromaDB collection is accessible
    collection = main.get_collection()
    assert collection is not None, "ChromaDB collection should be accessible"

    # Verify collection has data (not empty)
    collection_count = collection.count()
    assert collection_count > 0, f"ChromaDB collection is empty (count: {collection_count}) - need existing data for tests"

    # If we get here, initialization is complete and ready for search operations
    # This validates that the test infrastructure properly initializes ChromaDB
