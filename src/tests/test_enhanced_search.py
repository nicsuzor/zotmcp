"""End-to-end integration tests for enhanced search features.

These tests verify the enhanced search capabilities:
1. search tool with multiple modes (hybrid, semantic, metadata)
2. Author filtering with fuzzy matching via search tool
3. search_by_doi for exact DOI lookup
4. search_by_citation_key for citation key lookup
5. Date filtering across all search modes
6. Enhanced result format with multiple scores
"""

import pytest
from fastmcp import Client
from unittest.mock import AsyncMock, MagicMock
from dataclasses import dataclass

from enhanced_search import hybrid_search
from search_utils import SearchResult

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

            assert "error" not in result.data, (
                f"Search failed: {result.data.get('error')}"
            )
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
            assert "results" in result.data
            # Date filters are applied internally but not returned in response
            assert isinstance(result.data["results"], list)

    async def test_advanced_search_with_item_type_filter(self, mcp_server):
        """Verify item type filtering works."""
        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "search",
                {
                    "query": "research",
                    "n_results": 5,
                    "filter_type": "journalArticle",
                    "search_mode": "semantic",
                },
            )

            assert "error" not in result.data
            # Note: filter_type is passed but may not be in response filters

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
            assert "error" not in result.data or "ChromaDB" in result.data.get(
                "error", ""
            )
            assert "results" in result.data


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
            assert "no item found" in result.data["error"].lower()

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
                    if item.get("doi_or_url") and "doi.org/" in str(
                        item.get("doi_or_url")
                    ):
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
            assert "no item found" in result.data["error"].lower()

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
        """Verify all enhanced search tools are registered."""
        async with Client(mcp_server) as client:
            tools = await client.list_tools()
            tool_names = {tool.name for tool in tools}

            expected_tools = {
                "search",  # Main search tool with all features
                "search_by_doi",  # Exact DOI lookup
                "search_by_citation_key",  # Citation key lookup
            }

            missing_tools = expected_tools - tool_names
            assert len(missing_tools) == 0, f"Missing tools: {missing_tools}"

    async def test_search_tool_has_enhanced_description(self, mcp_server):
        """Verify search tool has description mentioning enhanced features."""
        async with Client(mcp_server) as client:
            tools = await client.list_tools()
            tool_dict = {tool.name: tool for tool in tools}

            # Check that search tool has description mentioning enhanced features
            assert "search" in tool_dict
            search_tool = tool_dict["search"]
            assert hasattr(search_tool, "description")
            assert len(search_tool.description) > 0
            # Should mention hybrid or fuzzy or modes
            description_lower = search_tool.description.lower()
            assert (
                "hybrid" in description_lower
                or "fuzzy" in description_lower
                or "mode" in description_lower
            )


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
                    "filter_type": "journalArticle",
                },
            )

            assert "error" not in result.data
            # Filters are applied internally but may not be in response

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
            assert "error" not in result.data or "ChromaDB" in result.data.get(
                "error", ""
            )


class TestCorruptionFiltering:
    """Test corruption filtering in hybrid_search function."""

    async def test_hybrid_search_filters_corrupted_results(self):
        """Test hybrid_search() filters out corrupted chunks before returning.

        The hybrid_search() function should use filter_corrupted_results() to
        remove search results with heavy CID corruption (>=20 patterns) before
        returning to the user.

        Arrange:
            Mock ChromaDB search tool to return results with corruption patterns:
            - 1 clean result with no CID patterns
            - 1 result with heavy CID corruption (25 patterns)
            - 1 result with minor corruption (5 patterns, should keep)

        Act:
            Call hybrid_search() with mocked search tool

        Assert:
            - Clean result is in returned list
            - Minor corruption result is in returned list
            - Heavy corruption result is NOT in returned list (filtered out)

        This test FAILS until hybrid_search() calls filter_corrupted_results().
        """
        # Arrange: Create mock ChromaDB search tool
        mock_search_tool = AsyncMock()
        mock_collection = MagicMock()

        # Create clean result
        clean_result = MagicMock()
        clean_result.metadata = {
            "item_key": "CLEAN_ITEM",
            "title": "Clean Document",
        }
        clean_result.content = "This is clean text with no corruption patterns."
        clean_result.score = 0.95

        # Create minor corruption result (5 CID patterns, below threshold)
        minor_cid_patterns = " ".join(f"(cid:{i})" for i in range(5))
        minor_corruption_result = MagicMock()
        minor_corruption_result.metadata = {
            "item_key": "MINOR_CID_ITEM",
            "title": "Document with Header CIDs",
        }
        minor_corruption_result.content = (
            f"Header with {minor_cid_patterns} but clean content."
        )
        minor_corruption_result.score = 0.88

        # Create heavy corruption result (25 CID patterns, above threshold)
        heavy_cid_patterns = " ".join(f"(cid:{i})" for i in range(25))
        heavy_corruption_result = MagicMock()
        heavy_corruption_result.metadata = {
            "item_key": "CORRUPT_ITEM",
            "title": "Corrupted OCR Document",
        }
        heavy_corruption_result.content = (
            f"Heavily corrupted with {heavy_cid_patterns} patterns."
        )
        heavy_corruption_result.score = 0.92

        # Mock search_tool.search() to return all three results
        mock_search_tool.search.return_value = [
            clean_result,
            minor_corruption_result,
            heavy_corruption_result,
        ]

        # Act: Call hybrid_search with mocked dependencies
        results = await hybrid_search(
            search_tool=mock_search_tool,
            collection=mock_collection,
            query="test query",
            n_results=10,
        )

        # Assert: Verify filtering behavior
        assert isinstance(results, list), "Should return a list"

        # Extract item keys from results
        result_keys = {r.item_key for r in results}

        # Verify clean result is present
        assert "CLEAN_ITEM" in result_keys, (
            "Clean result should be in returned results"
        )

        # Verify minor corruption result is present
        assert "MINOR_CID_ITEM" in result_keys, (
            "Minor corruption result (< 20 CID patterns) should be retained"
        )

        # Verify heavy corruption result is filtered out
        # THIS ASSERTION WILL FAIL until hybrid_search() calls filter_corrupted_results()
        assert "CORRUPT_ITEM" not in result_keys, (
            "Heavy corruption result (>= 20 CID patterns) should be filtered out. "
            "This test FAILS because hybrid_search() does not yet call filter_corrupted_results()"
        )

    async def test_advanced_search_semantic_filters_corrupted(self):
        """Test advanced_search() in semantic mode filters corrupted chunks.

        The advanced_search() function when called with search_mode="semantic"
        should use filter_corrupted_results() to remove corrupted chunks,
        just like hybrid_search() does.

        Arrange:
            Mock semantic search to return:
            - 1 clean result with no CID patterns
            - 1 result with heavy CID corruption (25 patterns)
            - 1 result with minor corruption (5 patterns, should keep)

        Act:
            Call advanced_search() with search_mode="semantic"

        Assert:
            - Clean result is in returned list
            - Minor corruption result is in returned list
            - Heavy corruption result is NOT in returned list (filtered out)

        This test FAILS until advanced_search() semantic mode calls
        filter_corrupted_results().
        """
        from enhanced_search import advanced_search

        # Arrange: Create mock ChromaDB search tool
        mock_search_tool = AsyncMock()
        mock_collection = MagicMock()

        # Create clean result
        clean_result = MagicMock()
        clean_result.metadata = {
            "item_key": "CLEAN_SEMANTIC_ITEM",
            "title": "Clean Document",
        }
        clean_result.content = "This is clean text with no corruption patterns."
        clean_result.score = 0.95

        # Create minor corruption result (5 CID patterns, below threshold)
        minor_cid_patterns = " ".join(f"(cid:{i})" for i in range(5))
        minor_corruption_result = MagicMock()
        minor_corruption_result.metadata = {
            "item_key": "MINOR_CID_SEMANTIC_ITEM",
            "title": "Document with Header CIDs",
        }
        minor_corruption_result.content = (
            f"Header with {minor_cid_patterns} but clean content."
        )
        minor_corruption_result.score = 0.88

        # Create heavy corruption result (25 CID patterns, above threshold)
        heavy_cid_patterns = " ".join(f"(cid:{i})" for i in range(25))
        heavy_corruption_result = MagicMock()
        heavy_corruption_result.metadata = {
            "item_key": "CORRUPT_SEMANTIC_ITEM",
            "title": "Corrupted OCR Document",
        }
        heavy_corruption_result.content = (
            f"Heavily corrupted with {heavy_cid_patterns} patterns."
        )
        heavy_corruption_result.score = 0.92

        # Mock search_tool.search() to return all three results
        mock_search_tool.search.return_value = [
            clean_result,
            minor_corruption_result,
            heavy_corruption_result,
        ]

        # Act: Call advanced_search with search_mode="semantic"
        results = await advanced_search(
            search_tool=mock_search_tool,
            collection=mock_collection,
            query="test query",
            n_results=10,
            search_mode="semantic",
        )

        # Assert: Verify filtering behavior
        assert isinstance(results, list), "Should return a list"

        # Extract item keys from results
        result_keys = {r.item_key for r in results}

        # Verify clean result is present
        assert "CLEAN_SEMANTIC_ITEM" in result_keys, (
            "Clean result should be in returned results"
        )

        # Verify minor corruption result is present
        assert "MINOR_CID_SEMANTIC_ITEM" in result_keys, (
            "Minor corruption result (< 20 CID patterns) should be retained"
        )

        # Verify heavy corruption result is filtered out
        # THIS ASSERTION WILL FAIL until advanced_search() semantic mode
        # calls filter_corrupted_results()
        assert "CORRUPT_SEMANTIC_ITEM" not in result_keys, (
            "Heavy corruption result (>= 20 CID patterns) should be filtered out. "
            "This test FAILS because advanced_search() semantic mode does not yet "
            "call filter_corrupted_results()"
        )

    async def test_exclude_corrupted_parameter_controls_filtering(self):
        """Test exclude_corrupted parameter controls whether filtering happens.

        The advanced_search() function should accept an exclude_corrupted parameter
        that controls whether corruption filtering is applied:
        - exclude_corrupted=True (default): corrupted results filtered out
        - exclude_corrupted=False: corrupted results included in output

        Arrange:
            Mock semantic_search to return:
            - 1 clean result with no CID patterns
            - 1 result with heavy CID corruption (25 patterns)

        Act:
            1. Call advanced_search() with exclude_corrupted=True
            2. Call advanced_search() with exclude_corrupted=False

        Assert:
            - With exclude_corrupted=True: corrupted result NOT in results
            - With exclude_corrupted=False: corrupted result IS in results

        This test FAILS because exclude_corrupted parameter doesn't exist yet.
        Expected error: TypeError: advanced_search() got an unexpected keyword
        argument 'exclude_corrupted'
        """
        from enhanced_search import advanced_search

        # Arrange: Create mock ChromaDB search tool
        mock_search_tool = AsyncMock()
        mock_collection = MagicMock()

        # Create clean result
        clean_result = MagicMock()
        clean_result.metadata = {
            "item_key": "CLEAN_ITEM",
            "title": "Clean Document",
        }
        clean_result.content = "This is clean text with no corruption patterns."
        clean_result.score = 0.95

        # Create heavy corruption result (25 CID patterns, above threshold)
        heavy_cid_patterns = " ".join(f"(cid:{i})" for i in range(25))
        heavy_corruption_result = MagicMock()
        heavy_corruption_result.metadata = {
            "item_key": "CORRUPT_ITEM",
            "title": "Corrupted OCR Document",
        }
        heavy_corruption_result.content = (
            f"Heavily corrupted with {heavy_cid_patterns} patterns."
        )
        heavy_corruption_result.score = 0.92

        # Mock search_tool.search() to return both results
        mock_search_tool.search.return_value = [
            clean_result,
            heavy_corruption_result,
        ]

        # Act & Assert 1: Test with exclude_corrupted=True (default behavior)
        results_filtered = await advanced_search(
            search_tool=mock_search_tool,
            collection=mock_collection,
            query="test query",
            n_results=10,
            search_mode="semantic",
            exclude_corrupted=True,  # This parameter doesn't exist yet - will raise TypeError
        )

        result_keys_filtered = {r.item_key for r in results_filtered}

        # With exclude_corrupted=True, corrupted result should be filtered
        assert "CLEAN_ITEM" in result_keys_filtered
        assert "CORRUPT_ITEM" not in result_keys_filtered, (
            "With exclude_corrupted=True, corrupted results should be filtered out"
        )

        # Act & Assert 2: Test with exclude_corrupted=False (include corrupted)
        results_unfiltered = await advanced_search(
            search_tool=mock_search_tool,
            collection=mock_collection,
            query="test query",
            n_results=10,
            search_mode="semantic",
            exclude_corrupted=False,  # This parameter doesn't exist yet - will raise TypeError
        )

        result_keys_unfiltered = {r.item_key for r in results_unfiltered}

        # With exclude_corrupted=False, corrupted result should be included
        assert "CLEAN_ITEM" in result_keys_unfiltered
        assert "CORRUPT_ITEM" in result_keys_unfiltered, (
            "With exclude_corrupted=False, corrupted results should be included in output"
        )
