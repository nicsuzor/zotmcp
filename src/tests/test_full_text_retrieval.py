"""Test that search excerpts return full chunk content, not truncated."""

from fastmcp import Client


class TestGetItemFullText:
    """Tests for get_item returning all chunks concatenated."""

    async def test_get_item_returns_all_chunks_concatenated(self, mcp_server):
        """get_item should return all chunks concatenated, not just first chunk.

        Uses mcp_server (parametrized): Validates get_item through MCP client
        interface in both local and Docker environments.

        The current implementation only retrieves the first chunk and truncates
        to 500 characters. This test verifies that:
        1. All chunks are retrieved and concatenated
        2. Response includes chunk_count field
        3. Response includes full_text (or full_text_file for large docs)

        Expected failure: Currently fails because:
        - get_item returns 'full_text_preview' (truncated to 500 chars)
        - get_item doesn't have 'chunk_count' field
        - get_item only gets first chunk, not all chunks
        """
        async with Client(mcp_server) as client:
            # First, search to find a document with substantial content
            search_result = await client.call_tool(
                "search",
                {
                    "query": "content moderation",
                    "n_results": 5,
                },
            )

            assert "results" in search_result.data, (
                f"Expected 'results' key in search response: {search_result.data}"
            )
            results = search_result.data["results"]
            assert len(results) > 0, "Expected at least one search result"

            # Get the zotero_key from the first result
            first_result = results[0]
            zotero_key = first_result.get("zotero_key")
            assert zotero_key, f"Expected 'zotero_key' in search result: {first_result}"

            # Call get_item with that key
            item_result = await client.call_tool(
                "get_item",
                {"item_key": zotero_key},
            )

            # Verify response structure for full text retrieval
            item_data = item_result.data

            # Check that chunk_count field exists (new requirement)
            assert "chunk_count" in item_data, (
                f"Expected 'chunk_count' field in get_item response. "
                f"Got keys: {list(item_data.keys())}"
            )

            # Check that full_text or full_text_file exists (not full_text_preview)
            has_full_text = "full_text" in item_data
            has_full_text_file = "full_text_file" in item_data

            assert has_full_text or has_full_text_file, (
                f"Expected 'full_text' or 'full_text_file' in get_item response. "
                f"Got keys: {list(item_data.keys())}. "
                f"Found 'full_text_preview' instead: {'full_text_preview' in item_data}"
            )

            # For documents with multiple chunks, verify full_text is longer than 500 chars
            chunk_count = item_data.get("chunk_count", 0)
            if chunk_count > 1 and has_full_text:
                full_text = item_data["full_text"]
                assert len(full_text) > 500, (
                    f"Multi-chunk document (chunk_count={chunk_count}) should have "
                    f"full_text longer than 500 chars. Got {len(full_text)} chars. "
                    f"This suggests only the first chunk was retrieved."
                )


class TestSearchFullText:
    """Tests for full-text content retrieval in search results."""

    async def test_search_excerpt_shows_full_chunk(self, mcp_server):
        """Search excerpts should show full chunk content, not truncated to 500 chars.

        Uses mcp_server (parametrized): Validates search results through MCP client
        interface in both local and Docker environments.

        The current implementation truncates document content to 500 characters
        at main.py line 763: `result.document[:500]`. This test verifies that
        full chunk content is available in search results.

        Expected failure: Currently fails because excerpts are hard-truncated
        to 500 characters, losing valuable context from longer chunks.
        """
        async with Client(mcp_server) as client:
            # Search for something that returns results with substantial content
            result = await client.call_tool(
                "search",
                {
                    "query": "content moderation",
                    "n_results": 10,
                },
            )

            # Should have results
            assert "results" in result.data, f"Expected 'results' key in response: {result.data}"
            results = result.data["results"]
            assert len(results) > 0, "Expected at least one search result"

            # Collect excerpt lengths to analyze truncation
            excerpt_lengths = []
            for r in results:
                excerpt = r.get("excerpt")
                if excerpt:
                    excerpt_lengths.append(len(excerpt))

            assert len(excerpt_lengths) > 0, "Expected at least one result with an excerpt"

            # Check if any excerpt is longer than 500 chars
            # If all excerpts are <= 500 chars, AND any excerpt is exactly 500 chars,
            # it's strong evidence of truncation (statistically unlikely for natural text)
            max_length = max(excerpt_lengths)
            has_exact_500 = 500 in excerpt_lengths

            # The test should fail if:
            # 1. No excerpt exceeds 500 characters (all were truncated), AND
            # 2. At least one excerpt is exactly 500 characters (evidence of truncation)
            assert max_length > 500 or not has_exact_500, (
                f"Excerpts appear to be truncated to 500 characters. "
                f"Max excerpt length: {max_length}, "
                f"Has exact 500-char excerpt: {has_exact_500}. "
                f"Excerpt lengths: {sorted(excerpt_lengths, reverse=True)[:5]}"
            )
