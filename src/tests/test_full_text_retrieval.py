"""Test that search excerpts return full chunk content, not truncated."""

import pytest
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


class TestGetItemLargeDocument:
    """Tests for large document handling with temp file output."""

    # Threshold for large document detection (500KB)
    LARGE_DOCUMENT_THRESHOLD_BYTES = 500 * 1024

    async def test_get_item_large_document_uses_temp_file(self, mcp_server):
        """Large documents (>500KB) should return temp file path instead of inline text.

        Uses mcp_server (parametrized): Validates get_item through MCP client
        interface in both local and Docker environments.

        For documents exceeding 500KB, get_item should:
        1. Write full text to a temp file
        2. Return 'full_text_file' with the path
        3. Return 'full_text_preview' (first ~2000 chars)
        4. NOT return 'full_text' inline
        5. Set 'is_large_document' to True

        Expected failure: Currently fails because:
        - get_item always returns 'full_text' inline
        - get_item always sets 'is_large_document' to False
        - No temp file logic is implemented
        """
        from pathlib import Path
        from fastmcp import Client

        async with Client(mcp_server) as client:
            # Search for books or theses which are more likely to be large
            # These item types typically have more content than journal articles
            search_result = await client.call_tool(
                "search",
                {
                    "query": "comprehensive analysis methodology",
                    "n_results": 20,
                },
            )

            assert "results" in search_result.data, (
                f"Expected 'results' key in search response: {search_result.data}"
            )
            results = search_result.data["results"]
            assert len(results) > 0, "Expected at least one search result"

            # Try to find a document with enough chunks to exceed 500KB
            # Average chunk is ~2000 chars, so ~250 chunks = 500KB
            # We'll check actual size after retrieving
            large_doc_found = False
            large_doc_key = None
            large_doc_data = None

            for result in results:
                zotero_key = result.get("zotero_key")
                if not zotero_key:
                    continue

                item_result = await client.call_tool(
                    "get_item",
                    {"item_key": zotero_key},
                )

                item_data = item_result.data
                chunk_count = item_data.get("chunk_count", 0)

                # Check if document is large either by:
                # 1. is_large_document flag being True (correct implementation)
                # 2. full_text size exceeding threshold (old/broken behavior)
                is_large = item_data.get("is_large_document", False)
                full_text = item_data.get("full_text", "")
                full_text_size = len(full_text.encode("utf-8")) if full_text else 0
                # For large docs with correct implementation, check full_text_size_bytes field
                reported_size = item_data.get("full_text_size_bytes", full_text_size)

                if is_large or full_text_size > self.LARGE_DOCUMENT_THRESHOLD_BYTES:
                    large_doc_found = True
                    large_doc_key = zotero_key
                    large_doc_data = item_data
                    break

            if not large_doc_found:
                pytest.skip(
                    f"No documents found exceeding {self.LARGE_DOCUMENT_THRESHOLD_BYTES} bytes. "
                    f"Largest found was {reported_size} bytes with {chunk_count} chunks. "
                    "This test requires real large documents in the collection."
                )

            # Now verify the large document handling behavior
            # EXPECTED: is_large_document should be True for docs > 500KB
            assert large_doc_data.get("is_large_document") is True, (
                f"Document with {len(large_doc_data.get('full_text', '').encode('utf-8'))} bytes "
                f"should have is_large_document=True. "
                f"Got: is_large_document={large_doc_data.get('is_large_document')}"
            )

            # EXPECTED: Should have full_text_file (path to temp file)
            assert "full_text_file" in large_doc_data, (
                f"Large document should have 'full_text_file' with temp file path. "
                f"Got keys: {list(large_doc_data.keys())}"
            )

            # EXPECTED: Should have full_text_preview (first ~2000 chars)
            assert "full_text_preview" in large_doc_data, (
                f"Large document should have 'full_text_preview'. "
                f"Got keys: {list(large_doc_data.keys())}"
            )

            # EXPECTED: Should NOT have full_text inline for large docs
            assert "full_text" not in large_doc_data, (
                f"Large document should NOT have 'full_text' inline (saves memory). "
                f"Should use 'full_text_file' instead. "
                f"Got keys: {list(large_doc_data.keys())}"
            )

            # Verify the temp file exists and is readable
            temp_file_path = Path(large_doc_data["full_text_file"])
            assert temp_file_path.exists(), (
                f"Temp file should exist at: {temp_file_path}"
            )
            assert temp_file_path.is_file(), (
                f"Temp file path should be a file: {temp_file_path}"
            )

            # Verify file content matches expected size
            file_content = temp_file_path.read_text(encoding="utf-8")
            assert len(file_content.encode("utf-8")) > self.LARGE_DOCUMENT_THRESHOLD_BYTES, (
                f"Temp file content should exceed threshold. "
                f"Got {len(file_content.encode('utf-8'))} bytes"
            )
