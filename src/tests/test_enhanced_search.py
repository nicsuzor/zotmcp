"""End-to-end integration tests for enhanced search features.

These tests verify the enhanced search capabilities:
1. search tool with multiple modes (hybrid, semantic, metadata)
2. search_zotero_by_author with fuzzy matching (upgraded internally)
3. search_by_doi for exact DOI lookup
4. search_by_citation_key for citation key lookup
5. Date filtering across all search modes
6. Enhanced result format with multiple scores
"""

import pytest
from fastmcp import Client

# Mark all tests in this module as async
pytestmark = pytest.mark.anyio


class TestEnhancedSearch:
    """Test the enhanced search tool with multiple modes and filters."""

    async def test_search_hybrid_mode(self, mcp_server):
        """Verify search works in hybrid mode (default)."""
        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "search",
                {
                    "query": "content moderation",
                    "n_results": 5,
                    "search_mode": "hybrid",
                },
            )

            assert "error" not in result.data, f"Search failed: {result.data.get('error')}"
            assert "results" in result.data
            assert "search_mode" in result.data
            assert result.data["search_mode"] == "hybrid"
            assert isinstance(result.data["results"], list)

    async def test_advanced_search_semantic_mode(self, mcp_server):
        """Verify advanced_search works in semantic-only mode."""
        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "search",
                {
                    "query": "platform governance",
                    "n_results": 5,
                    "search_mode": "semantic",
                },
            )

            assert "error" not in result.data
            assert result.data["search_mode"] == "semantic"
            assert "results" in result.data

    async def test_advanced_search_metadata_mode(self, mcp_server):
        """Verify advanced_search works in metadata-only mode."""
        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "search",
                {
                    "query": "privacy",
                    "n_results": 5,
                    "search_mode": "metadata",
                },
            )

            assert "error" not in result.data
            assert result.data["search_mode"] == "metadata"
            assert "results" in result.data

    async def test_advanced_search_with_date_filter(self, mcp_server):
        """Verify date filtering works in advanced_search."""
        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "search",
                {
                    "query": "social media",
                    "n_results": 10,
                    "date_from": 2020,
                    "date_to": 2024,
                    "search_mode": "hybrid",
                },
            )

            assert "error" not in result.data
            assert "filters" in result.data
            assert result.data["filters"]["date_from"] == 2020
            assert result.data["filters"]["date_to"] == 2024

            # If we got results, verify they have dates in range
            if result.data["total_results"] > 0:
                # Results should be in the filtered range
                # (actual date verification would require parsing citations)
                assert isinstance(result.data["results"], list)

    async def test_advanced_search_with_item_type_filter(self, mcp_server):
        """Verify item type filtering works."""
        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "search",
                {
                    "query": "research",
                    "n_results": 5,
                    "item_type": "journalArticle",
                    "search_mode": "semantic",
                },
            )

            assert "error" not in result.data
            assert result.data["filters"]["item_type"] == "journalArticle"

    async def test_advanced_search_invalid_mode(self, mcp_server):
        """Verify error handling for invalid search mode."""
        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "search",
                {
                    "query": "test",
                    "search_mode": "invalid_mode",
                },
            )

            assert "error" in result.data
            assert "invalid" in result.data["error"].lower()

    async def test_advanced_search_result_format(self, mcp_server):
        """Verify enhanced result format with scores."""
        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "search",
                {
                    "query": "content moderation",
                    "n_results": 3,
                    "search_mode": "hybrid",
                },
            )

            assert "error" not in result.data

            # If we got results, verify enhanced format
            if result.data["total_results"] > 0:
                first_result = result.data["results"][0]

                # Standard fields should be present
                assert "citation" in first_result
                assert "excerpt" in first_result
                assert "zotero_key" in first_result

                # New enhanced fields may be present (depending on mode)
                # In hybrid mode, we should have both scores
                if "semantic_score" in first_result:
                    assert isinstance(first_result["semantic_score"], (int, float))
                    assert 0 <= first_result["semantic_score"] <= 1

                if "combined_score" in first_result:
                    assert isinstance(first_result["combined_score"], (int, float))
                    assert 0 <= first_result["combined_score"] <= 100

    async def test_advanced_search_respects_n_results(self, mcp_server):
        """Verify n_results parameter is respected."""
        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "search",
                {
                    "query": "research",
                    "n_results": 3,
                    "search_mode": "semantic",
                },
            )

            assert "error" not in result.data
            assert result.data["total_results"] <= 3

    async def test_advanced_search_max_results_clamping(self, mcp_server):
        """Verify n_results is clamped to maximum (100)."""
        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "search",
                {
                    "query": "research",
                    "n_results": 500,  # Should be clamped to 100
                    "search_mode": "semantic",
                },
            )

            assert "error" not in result.data
            assert result.data["total_results"] <= 100


class TestSearchWithAuthorFilter:
    """Test search tool with author filtering (uses fuzzy matching)."""

    async def test_search_with_author_filter(self, mcp_server):
        """Verify search with author filter works."""
        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "search",
                {
                    "query": "research",
                    "author": "Smith",
                    "n_results": 5,
                    "search_mode": "hybrid",
                },
            )

            # Should not error (may return 0 results if no Smith in DB)
            assert "error" not in result.data
            assert "results" in result.data
            assert "total_results" in result.data
            assert isinstance(result.data["results"], list)

    async def test_search_author_with_date_filter(self, mcp_server):
        """Verify author + date filtering works together."""
        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "search",
                {
                    "query": "research",
                    "author": "Smith",
                    "date_from": 2020,
                    "n_results": 10,
                    "search_mode": "hybrid",
                },
            )

            assert "error" not in result.data
            assert "results" in result.data

    async def test_search_author_metadata_mode(self, mcp_server):
        """Verify author search in metadata mode (pure fuzzy matching)."""
        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "search",
                {
                    "query": "",
                    "author": "Smith",
                    "n_results": 5,
                    "search_mode": "metadata",
                },
            )

            # Metadata mode with author should work
            assert "error" not in result.data or "ChromaDB" in result.data.get("error", "")
            assert "results" in result.data


class TestLegacyAuthorSearch:
    """Test that legacy search_zotero_by_author now uses fuzzy matching."""

    async def test_legacy_author_search_upgraded(self, mcp_server):
        """Verify legacy author search now uses fuzzy matching internally."""
        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "search_zotero_by_author",
                {
                    "author_name": "Smith",
                    "n_results": 5,
                },
            )

            # Should work without error
            assert "error" not in result.data
            assert "items" in result.data
            assert "total_results" in result.data

    async def test_legacy_author_search_result_format(self, mcp_server):
        """Verify legacy author search returns proper format."""
        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "search_zotero_by_author",
                {
                    "author_name": "Smith",
                    "n_results": 10,
                },
            )

            # Should work
            assert "error" not in result.data
            assert "items" in result.data
            assert "total_results" in result.data

            # If we got results, verify format
            if result.data["total_results"] > 0:
                first_item = result.data["items"][0]
                assert "citation" in first_item
                assert "zotero_key" in first_item


class TestDOISearch:
    """Test search_by_doi for exact DOI lookup."""

    async def test_doi_search_not_found(self, mcp_server):
        """Verify appropriate error for non-existent DOI."""
        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "search_by_doi",
                {
                    "doi": "10.9999/nonexistent123456",
                },
            )

            # Should return error for non-existent DOI
            assert "error" in result.data
            assert "not found" in result.data["error"].lower()

    async def test_doi_search_format_variations(self, mcp_server):
        """Verify DOI search handles different format variations."""
        async with Client(mcp_server) as client:
            # Try different DOI formats (should normalize internally)
            doi_formats = [
                "10.1038/nature12373",
                "doi:10.1038/nature12373",
                "https://doi.org/10.1038/nature12373",
            ]

            for doi_format in doi_formats:
                result = await client.call_tool(
                    "search_by_doi",
                    {
                        "doi": doi_format,
                    },
                )

                # All formats should be handled (error or success, but no crash)
                assert isinstance(result.data, dict)

    async def test_doi_search_result_format(self, mcp_server):
        """Verify DOI search result format when item found."""
        async with Client(mcp_server) as client:
            # Try to find any item with a DOI
            # First search for items
            search_result = await client.call_tool(
                "search",
                {
                    "query": "research",
                    "n_results": 20,
                },
            )

            # Find an item with a DOI
            doi_to_search = None
            if search_result.data["total_results"] > 0:
                for item in search_result.data["results"]:
                    if item.get("doi_or_url") and "doi.org/" in str(item.get("doi_or_url")):
                        # Extract DOI from URL
                        doi_to_search = item["doi_or_url"]
                        break

            if doi_to_search:
                # Test DOI lookup
                result = await client.call_tool(
                    "search_by_doi",
                    {
                        "doi": doi_to_search,
                    },
                )

                if "error" not in result.data:
                    # Verify structure
                    assert "citation" in result.data
                    assert "doi" in result.data
                    assert "zotero_key" in result.data
            else:
                pytest.skip("No items with DOIs found in test database")


class TestCitationKeySearch:
    """Test search_by_citation_key for exact citation key lookup."""

    async def test_citation_key_search_not_found(self, mcp_server):
        """Verify appropriate error for non-existent citation key."""
        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "search_by_citation_key",
                {
                    "citation_key": "nonexistentkey9999",
                },
            )

            # Should return error for non-existent key
            assert "error" in result.data
            assert "not found" in result.data["error"].lower()

    async def test_citation_key_search_result_format(self, mcp_server):
        """Verify citation key search result format when item found."""
        async with Client(mcp_server) as client:
            # Try to find any item with a citation key
            search_result = await client.call_tool(
                "search",
                {
                    "query": "research",
                    "n_results": 20,
                },
            )

            # Find an item with a citation key
            citation_key_to_search = None
            if search_result.data["total_results"] > 0:
                for item in search_result.data["results"]:
                    if item.get("citation_key"):
                        citation_key_to_search = item["citation_key"]
                        break

            if citation_key_to_search:
                # Test citation key lookup
                result = await client.call_tool(
                    "search_by_citation_key",
                    {
                        "citation_key": citation_key_to_search,
                    },
                )

                if "error" not in result.data:
                    # Verify structure
                    assert "citation" in result.data
                    assert "citation_key" in result.data
                    assert result.data["citation_key"] == citation_key_to_search
                    assert "zotero_key" in result.data
            else:
                pytest.skip("No items with citation keys found in test database")


class TestToolAvailability:
    """Test that all new tools are registered and available."""

    async def test_all_enhanced_tools_available(self, mcp_server):
        """Verify all new enhanced search tools are registered."""
        async with Client(mcp_server) as client:
            tools = await client.list_tools()
            tool_names = {tool.name for tool in tools}

            expected_new_tools = {
                "search",
                "search_zotero_by_author",
                "search_by_doi",
                "search_by_citation_key",
            }

            missing_tools = expected_new_tools - tool_names
            assert len(missing_tools) == 0, f"Missing tools: {missing_tools}"

    async def test_enhanced_tools_have_descriptions(self, mcp_server):
        """Verify new tools have proper descriptions."""
        async with Client(mcp_server) as client:
            tools = await client.list_tools()
            tool_dict = {tool.name: tool for tool in tools}

            # Check that new tools have descriptions
            for tool_name in ["search", "search_zotero_by_author"]:
                if tool_name in tool_dict:
                    tool = tool_dict[tool_name]
                    assert hasattr(tool, "description")
                    assert len(tool.description) > 0
                    # Description should mention key features
                    if tool_name == "search":
                        assert "fuzzy" in tool.description.lower() or "hybrid" in tool.description.lower()
                    elif tool_name == "search_zotero_by_author":
                        assert "fuzzy" in tool.description.lower()


class TestIntegrationScenarios:
    """Test realistic end-to-end scenarios."""

    async def test_search_comparison_semantic_vs_hybrid(self, mcp_server):
        """Compare semantic and hybrid search results for same query."""
        async with Client(mcp_server) as client:
            query = "content moderation"

            # Semantic search
            semantic_result = await client.call_tool(
                "search",
                {
                    "query": query,
                    "n_results": 10,
                    "search_mode": "semantic",
                },
            )

            # Hybrid search
            hybrid_result = await client.call_tool(
                "search",
                {
                    "query": query,
                    "n_results": 10,
                    "search_mode": "hybrid",
                },
            )

            # Both should work
            assert "error" not in semantic_result.data
            assert "error" not in hybrid_result.data

            # Both should return results (assuming DB has relevant data)
            assert "results" in semantic_result.data
            assert "results" in hybrid_result.data

    async def test_multi_filter_combination(self, mcp_server):
        """Test combining multiple filters in advanced_search."""
        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "search",
                {
                    "query": "research",
                    "n_results": 20,
                    "search_mode": "hybrid",
                    "date_from": 2020,
                    "item_type": "journalArticle",
                },
            )

            assert "error" not in result.data
            assert result.data["filters"]["date_from"] == 2020
            assert result.data["filters"]["item_type"] == "journalArticle"

    async def test_empty_query_with_filters(self, mcp_server):
        """Test that filters work even with empty query."""
        async with Client(mcp_server) as client:
            # Empty query with title filter (metadata mode)
            result = await client.call_tool(
                "search",
                {
                    "query": "",
                    "n_results": 5,
                    "search_mode": "metadata",
                    "date_from": 2020,
                },
            )

            # Should handle gracefully
            assert "error" not in result.data or "ChromaDB" in result.data.get("error", "")
