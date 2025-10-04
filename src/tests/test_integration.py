"""End-to-end integration tests for ZotMCP Docker container.

These tests verify that the packaged Docker image:
1. Starts successfully
2. Provides all expected MCP tools
3. Tools return valid responses
4. ChromaDB integration works
5. Error handling is appropriate
"""

import pytest
from fastmcp import Client
import json

# Mark all tests in this module as async
pytestmark = pytest.mark.anyio


class TestServerStartup:
    """Test that the server starts and initializes correctly."""

    async def test_server_connects(self, mcp_server):
        """Verify the server accepts connections."""
        # If we get here, the client fixture connected successfully
        async with Client(mcp_server) as mcp_client:
            assert mcp_client is not None

    async def test_server_lists_tools(self, mcp_server):
        """Verify the server exposes all expected tools."""
        async with Client(mcp_server) as mcp_client:
            tools = await mcp_client.list_tools()
            tool_names = {tool.name for tool in tools}

            expected_tools = {
                "search",
                "get_item",
                "get_similar_items",
                "get_collection_info",
                "assisted_search",
                "search_by_author",
            }

            assert expected_tools.issubset(tool_names), (
                f"Missing tools: {expected_tools - tool_names}"
            )


class TestCollectionInfo:
    """Test collection metadata retrieval."""

    async def test_get_collection_info(self, mcp_server):
        """Verify collection info returns valid metadata."""
        async with Client(mcp_server) as mcp_client:
            result = await mcp_client.call_tool("get_collection_info")

            # Should return collection metadata
            assert "collection_name" in result.data
            assert "total_chunks" in result.data
            assert isinstance(result.data["total_chunks"], int)
            assert result.data["total_chunks"] > 0

    async def test_collection_has_embedding_config(self, mcp_server):
        """Verify collection reports embedding configuration."""
        async with Client(mcp_server) as mcp_client:
            result = await mcp_client.call_tool("get_collection_info")

            assert "embedding_model" in result.data
            assert "dimensions" in result.data
            assert isinstance(result.data["dimensions"], int)


class TestSearch:
    """Test the search functionality."""

    async def test_search_returns_results(self, mcp_server):
        """Verify search returns relevant results."""
        async with Client(mcp_server) as mcp_client:
            result = await mcp_client.call_tool(
                "search",
                {
                    "query": "content moderation",
                    "n_results": 5,
                },
            )

            assert "results" in result.data
            assert "total_results" in result.data
            assert isinstance(result.data["results"], list)
            assert result.data["total_results"] >= 0

    async def test_search_result_structure(self, mcp_server):
        """Verify search results have expected structure."""
        async with Client(mcp_server) as mcp_client:
            result = await mcp_client.call_tool(
                "search",
                {
                    "query": "platform governance",
                    "n_results": 3,
                },
            )

            if result.data["total_results"] > 0:
                first_result = result.data["results"][0]

                # Check required fields
                assert "citation" in first_result
                assert "excerpt" in first_result
                assert "similarity" in first_result
                assert "metadata" in first_result

                # Excerpt should be truncated
                assert len(first_result["excerpt"]) <= 503  # 500 + "..."

    async def test_search_respects_n_results(self, mcp_server):
        """Verify n_results parameter is respected."""
        async with Client(mcp_server) as mcp_client:
            result = await mcp_client.call_tool(
                "search",
                {
                    "query": "social media",
                    "n_results": 2,
                },
            )

            # Should return at most n_results
            assert result.data["total_results"] <= 2

    async def test_search_with_filter(self, mcp_server):
        """Verify search handles type filtering."""
        async with Client(mcp_server) as mcp_client:
            result = await mcp_client.call_tool(
                "search",
                {
                    "query": "misinformation",
                    "n_results": 5,
                    "filter_type": "journalArticle",
                },
            )

            # Should return results (may be fewer than requested if filter is restrictive)
            assert "results" in result.data
            assert "total_results" in result.data


class TestSimilarItems:
    """Test similar item discovery."""

    async def test_get_similar_items(self, mcp_server):
        """Verify similar item search works."""
        async with Client(mcp_server) as mcp_client:
            # First, get an item key from search
            search_result = await mcp_client.call_tool(
                "search",
                {
                    "query": "content moderation",
                    "n_results": 1,
                },
            )

            if search_result.data["total_results"] == 0:
                pytest.skip("No items in collection")

            item_key = search_result.data["results"][0]["metadata"].get("zotero_key")
            if not item_key:
                pytest.skip("No item key in search results")

            # Find similar items
            result = await mcp_client.call_tool(
                "get_similar_items",
                {
                    "item_key": item_key,
                    "n_results": 3,
                },
            )

            if "error" not in result.data:
                assert "similar_items" in result.data
                assert isinstance(result.data["similar_items"], list)

    async def test_similar_items_excludes_reference(self, mcp_server):
        """Verify similar items don't include the reference item itself."""
        async with Client(mcp_server) as mcp_client:
            search_result = await mcp_client.call_tool(
                "search",
                {
                    "query": "platform",
                    "n_results": 1,
                },
            )

            if search_result.data["total_results"] == 0:
                pytest.skip("No items in collection")

            item_key = search_result.data["results"][0]["metadata"].get("zotero_key")
            if not item_key:
                pytest.skip("No item key in search results")

            result = await mcp_client.call_tool(
                "get_similar_items",
                {
                    "item_key": item_key,
                    "n_results": 5,
                },
            )

            if "error" not in result.data:
                similar_keys = [
                    item["item_key"] for item in result.data["similar_items"]
                ]
                assert item_key not in similar_keys


class TestAuthorSearch:
    """Test author search functionality."""

    async def test_search_by_author(self, mcp_server):
        """Verify author search works."""
        async with Client(mcp_server) as mcp_client:
            # Search for a common author name
            result = await mcp_client.call_tool(
                "search_by_author",
                {
                    "author_name": "Smith",
                    "n_results": 5,
                },
            )

            assert "author" in result.data
            assert "total_results" in result.data
            assert "items" in result.data
            assert isinstance(result.data["items"], list)


class TestErrorHandling:
    """Test error handling and edge cases."""

    async def test_search_with_invalid_params(self, mcp_server):
        """Verify search handles invalid parameters gracefully."""
        async with Client(mcp_server) as mcp_client:
            # n_results should be clamped to max (50)
            result = await mcp_client.call_tool(
                "search",
                {
                    "query": "test",
                    "n_results": 1000,  # Should be clamped to max (50)
                },
            )

            # Should not error, but clamp to reasonable value
            assert result.data["total_results"] <= 50

    async def test_empty_query_search(self, mcp_server):
        """Verify search handles empty query string."""
        async with Client(mcp_server) as mcp_client:
            result = await mcp_client.call_tool(
                "search",
                {
                    "query": "",
                    "n_results": 5,
                },
            )

            # Should return something or handle gracefully
            assert "results" in result.data
            assert "total_results" in result.data

    async def test_invalid_item_key(self, mcp_server):
        """Verify appropriate error for invalid item key."""
        async with Client(mcp_server) as mcp_client:
            result = await mcp_client.call_tool(
                "get_similar_items",
                {"item_key": "nonexistent_key_12345"},
            )

            # Should return error
            assert "error" in result.data


@pytest.mark.skip("Non-core functionality - no LLM integration yet")
class TestAssistedSearch:
    """Test assisted search (currently returns structured data without LLM)."""

    async def test_assisted_search_returns_response(self, mcp_server):
        """Verify assisted search completes and returns a response."""
        async with Client(mcp_server) as mcp_client:
            result = await mcp_client.call_tool(
                "assisted_search",
                {
                    "research_question": "What are the main challenges in content moderation?",
                },
            )

            assert "response" in result.data
            assert "literature" in result.data
            assert isinstance(result.data["literature"], list)
