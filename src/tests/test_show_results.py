"""Show actual results from ZotMCP tools for manual inspection.

These tests run real queries and display the results to help evaluate
search quality, relevance, and tool effectiveness. They don't assert
pass/fail - they just show you what comes back.

Run with: uv run pytest src/tests/test_show_results.py -v -s
(The -s flag shows print output)
"""

import pytest
from fastmcp import Client

pytestmark = pytest.mark.anyio


class TestSearchResults:
    """Show actual search results for common queries."""

    async def test_show_content_moderation_search(self, mcp_server):
        """Search: content moderation - show top 5 results."""
        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "search",
                {
                    "query": "content moderation",
                    "n_results": 5,
                    "search_mode": "hybrid",
                },
            )

            print("\n" + "=" * 80)
            print("SEARCH: 'content moderation' (hybrid mode)")
            print("=" * 80)
            print(f"Total results: {result.data.get('total_results', 0)}")
            print(f"Search mode: {result.data.get('search_mode', 'unknown')}")
            print()

            for i, item in enumerate(result.data.get("results", []), 1):
                print(f"\n{i}. {item.get('citation', 'No citation')}")
                print(f"   Score: {item.get('combined_score', item.get('semantic_score', 'N/A'))}")
                print(f"   Zotero: {item.get('zotero_key', 'N/A')}")
                excerpt = item.get("excerpt", "")
                if excerpt:
                    # Truncate long excerpts
                    excerpt_display = excerpt[:200] + "..." if len(excerpt) > 200 else excerpt
                    print(f"   Excerpt: {excerpt_display}")
                print()

    async def test_show_platform_governance_semantic(self, mcp_server):
        """Search: platform governance - semantic only."""
        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "search",
                {
                    "query": "platform governance",
                    "n_results": 5,
                    "search_mode": "semantic",
                },
            )

            print("\n" + "=" * 80)
            print("SEARCH: 'platform governance' (semantic mode)")
            print("=" * 80)
            print(f"Total results: {result.data.get('total_results', 0)}")
            print()

            for i, item in enumerate(result.data.get("results", []), 1):
                print(f"\n{i}. {item.get('citation', 'No citation')}")
                print(f"   Semantic score: {item.get('semantic_score', 'N/A')}")
                excerpt = item.get("excerpt", "")[:150]
                print(f"   Excerpt: {excerpt}...")
                print()

    async def test_show_search_with_date_filter(self, mcp_server):
        """Search with date filter - recent papers only."""
        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "search",
                {
                    "query": "social media regulation",
                    "n_results": 5,
                    "date_from": 2022,
                    "search_mode": "hybrid",
                },
            )

            print("\n" + "=" * 80)
            print("SEARCH: 'social media regulation' (2022+)")
            print("=" * 80)
            print(f"Total results: {result.data.get('total_results', 0)}")
            print()

            for i, item in enumerate(result.data.get("results", []), 1):
                print(f"\n{i}. {item.get('citation', 'No citation')}")
                print()

    async def test_compare_hybrid_vs_semantic(self, mcp_server):
        """Compare hybrid vs semantic search results for same query."""
        query = "algorithmic transparency"

        async with Client(mcp_server) as client:
            # Hybrid search
            hybrid = await client.call_tool(
                "search",
                {
                    "query": query,
                    "n_results": 5,
                    "search_mode": "hybrid",
                },
            )

            # Semantic search
            semantic = await client.call_tool(
                "search",
                {
                    "query": query,
                    "n_results": 5,
                    "search_mode": "semantic",
                },
            )

            print("\n" + "=" * 80)
            print(f"COMPARISON: '{query}'")
            print("=" * 80)

            print("\n--- HYBRID MODE ---")
            print(f"Total: {hybrid.data.get('total_results', 0)}")
            for i, item in enumerate(hybrid.data.get("results", []), 1):
                print(f"{i}. {item.get('citation', 'No citation')[:80]}")

            print("\n--- SEMANTIC MODE ---")
            print(f"Total: {semantic.data.get('total_results', 0)}")
            for i, item in enumerate(semantic.data.get("results", []), 1):
                print(f"{i}. {item.get('citation', 'No citation')[:80]}")

            print()


class TestAuthorSearch:
    """Show author search results."""

    async def test_show_author_search_results(self, mcp_server):
        """Search by author name - show what it finds."""
        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "search_by_author",
                {
                    "author_name": "Suzor",
                    "limit": 10,
                },
            )

            print("\n" + "=" * 80)
            print("AUTHOR SEARCH: 'Suzor'")
            print("=" * 80)

            papers = result.data if isinstance(result.data, list) else []
            print(f"Total papers found: {len(papers)}")
            print()

            for i, paper in enumerate(papers, 1):
                print(f"{i}. {paper.get('citation', 'No citation')}")
                if paper.get('authors'):
                    print(f"   Authors: {paper.get('authors')}")
                print()

    async def test_show_search_with_author_filter(self, mcp_server):
        """Search with author filter via main search tool."""
        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "search",
                {
                    "query": "content moderation",
                    "author": "Gillespie",
                    "n_results": 5,
                    "search_mode": "hybrid",
                },
            )

            print("\n" + "=" * 80)
            print("SEARCH: 'content moderation' by 'Gillespie'")
            print("=" * 80)
            print(f"Total results: {result.data.get('total_results', 0)}")
            print()

            for i, item in enumerate(result.data.get("results", []), 1):
                print(f"{i}. {item.get('citation', 'No citation')}")
                print()


class TestSimilarItems:
    """Show similar items functionality."""

    async def test_show_similar_items(self, mcp_server):
        """Find similar items - show what it returns."""
        async with Client(mcp_server) as client:
            # First get a reference item
            search_result = await client.call_tool(
                "search",
                {
                    "query": "content moderation",
                    "n_results": 1,
                },
            )

            if search_result.data["total_results"] == 0:
                pytest.skip("No items in collection")

            ref_item = search_result.data["results"][0]
            item_key = ref_item.get("zotero_key")

            if not item_key:
                pytest.skip("No item key available")

            # Get similar items
            similar = await client.call_tool(
                "get_similar_items",
                {
                    "item_key": item_key,
                    "n_results": 5,
                },
            )

            print("\n" + "=" * 80)
            print("SIMILAR ITEMS")
            print("=" * 80)
            print(f"Reference: {ref_item.get('citation', 'No citation')[:80]}")
            print()

            if "error" in similar.data:
                print(f"Error: {similar.data['error']}")
            else:
                similar_items = similar.data.get("similar_items", [])
                print(f"Found {len(similar_items)} similar items:")
                print()

                for i, item in enumerate(similar_items, 1):
                    print(f"{i}. {item.get('citation', 'No citation')[:80]}")
                    if item.get('similarity_score'):
                        print(f"   Similarity: {item['similarity_score']}")
                    print()


class TestGetItem:
    """Show get_item full text retrieval."""

    async def test_show_full_item_retrieval(self, mcp_server):
        """Get full item by key - verify metadata and content are returned.

        This test verifies that get_item() returns full metadata for a Zotero item.
        Currently FAILS because get_item() raises NotImplementedError instead of
        returning data. Once implemented, the test should pass.
        """
        async with Client(mcp_server) as client:
            # Arrange: Get an item key from real search results
            search_result = await client.call_tool(
                "search",
                {
                    "query": "platform governance",
                    "n_results": 1,
                },
            )

            if search_result.data["total_results"] == 0:
                pytest.skip("No items in collection")

            item_key = search_result.data["results"][0].get("zotero_key")
            if not item_key:
                pytest.skip("No item key available")

            # Act: Get full item metadata
            # This call will raise NotImplementedError until get_item() is implemented
            item = await client.call_tool(
                "get_item",
                {
                    "item_key": item_key,
                },
            )

            # Assert: Verify response contains real metadata (not error or N/A)
            # These assertions define the expected behavior

            # Should have citation with actual content
            assert "citation" in item.data, "Response missing 'citation' field"
            assert item.data["citation"] != "N/A", "Citation should not be 'N/A'"
            assert item.data["citation"] is not None, "Citation should not be None"

            # Should have title
            assert "title" in item.data, "Response missing 'title' field"
            assert item.data["title"] is not None, "Title should not be None"

            # Should have item_type
            assert "item_type" in item.data, "Response missing 'item_type' field"
            assert item.data["item_type"] is not None, "Item type should not be None"

            # Should have at least one identifier (DOI, URL, or zotero_link)
            has_identifier = (
                item.data.get("doi") or
                item.data.get("url") or
                item.data.get("zotero_link")
            )
            assert has_identifier, "Response should have at least one of: DOI, URL, or zotero_link"

            # Should have some content (abstract or full_text_preview)
            has_content = (
                item.data.get("abstract") or
                item.data.get("full_text_preview")
            )
            assert has_content, "Response should have either abstract or full_text_preview"


class TestCollectionInfo:
    """Show collection statistics and metadata."""

    async def test_show_collection_info(self, mcp_server):
        """Display collection statistics."""
        async with Client(mcp_server) as client:
            result = await client.call_tool("get_collection_info")

            print("\n" + "=" * 80)
            print("COLLECTION INFO")
            print("=" * 80)
            print(f"Collection: {result.data.get('collection_name', 'N/A')}")
            print(f"Total chunks: {result.data.get('total_chunks', 0):,}")
            print(f"Embedding model: {result.data.get('embedding_model', 'N/A')}")
            print(f"Dimensions: {result.data.get('dimensions', 'N/A')}")

            if result.data.get('metadata'):
                print("\nMetadata:")
                for key, value in result.data['metadata'].items():
                    print(f"  {key}: {value}")

            print()
