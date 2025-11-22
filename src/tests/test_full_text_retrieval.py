"""Test that search excerpts return full chunk content, not truncated."""

from fastmcp import Client


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
