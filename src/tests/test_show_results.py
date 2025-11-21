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
        """Test date filtering with realistic date ranges based on actual data.

        This test verifies that date filtering works correctly by:
        1. Getting baseline results without filter
        2. Testing filter that INCLUDES the years present in data (2020-2021)
        3. Testing filter that EXCLUDES those years (2022+)

        Expected behavior: Filter correctly includes/excludes based on year ranges.
        """
        async with Client(mcp_server) as client:
            # STEP 1: Get baseline WITHOUT date filter
            print("\n" + "=" * 80)
            print("STEP 1: Baseline search WITHOUT date filter")
            print("=" * 80)

            result_no_filter = await client.call_tool(
                "search",
                {
                    "query": "social media regulation",
                    "n_results": 10,
                    "search_mode": "hybrid",
                },
            )

            total_without_filter = result_no_filter.data.get('total_results', 0)
            print(f"Total results WITHOUT filter: {total_without_filter}")

            # Show sample years from results
            print("\nSample years from results:")
            for i, item in enumerate(result_no_filter.data.get("results", [])[:5], 1):
                citation = item.get('citation', 'No citation')[:60]
                date_field = item.get("date", "unknown")
                print(f"  {i}. {citation}... [{date_field}]")

            # STEP 2: Test filter that INCLUDES data years (2020-2021)
            print("\n" + "=" * 80)
            print("STEP 2: Filter INCLUDING data years (date_from=2020, date_to=2021)")
            print("=" * 80)

            result_inclusive = await client.call_tool(
                "search",
                {
                    "query": "social media regulation",
                    "n_results": 10,
                    "date_from": 2020,
                    "date_to": 2021,
                    "search_mode": "hybrid",
                },
            )

            total_inclusive = result_inclusive.data.get('total_results', 0)
            print(f"Total results WITH date_from=2020, date_to=2021: {total_inclusive}")
            print(f"Expected: Similar to baseline ({total_without_filter})")
            print()

            # STEP 3: Test filter that EXCLUDES most data years (2022+)
            print("=" * 80)
            print("STEP 3: Filter with later years (date_from=2022)")
            print("=" * 80)

            result_later = await client.call_tool(
                "search",
                {
                    "query": "social media regulation",
                    "n_results": 10,
                    "date_from": 2022,
                    "search_mode": "hybrid",
                },
            )

            total_later = result_later.data.get('total_results', 0)
            print(f"Total results WITH date_from=2022: {total_later}")
            print(f"Expected: Much fewer than baseline (most data is 2020-2021)")
            print()

            # SUMMARY: Verify filtering behavior
            print("=" * 80)
            print("FILTERING VERIFICATION")
            print("=" * 80)
            print(f"✓ Baseline (no filter):           {total_without_filter} results")
            print(f"✓ Including range (2020-2021):    {total_inclusive} results")
            print(f"✓ Later years (2022+):            {total_later} results")
            print()

            # Verify expected behavior
            if total_later < total_without_filter:
                print("✓ PASS: Filter correctly reduces results for later years")
            else:
                print(f"✗ UNEXPECTED: Filter should reduce results for 2022+, got {total_later}/{total_without_filter}")

            if total_inclusive > 0 and total_inclusive <= total_without_filter:
                print("✓ PASS: Filter correctly includes papers from 2020-2021 range")
            else:
                print(f"✗ UNEXPECTED: Filter should find papers in 2020-2021 range")

            # Show that filtering is working as expected
            if total_later < total_inclusive:
                print("✓ PASS: More results in 2020-2021 range than in 2022+ range (as expected)")
            else:
                print(f"✗ UNEXPECTED: Should have more results in 2020-2021 than 2022+")

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
    """Show OpenAlex author search results."""

    async def test_show_openalex_author_search_results(self, mcp_server):
        """Search by author name in OpenAlex - show what it finds."""
        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "search_openalex_author",
                {
                    "author_name": "Suzor",
                    "limit": 10,
                },
            )

            print("\n" + "=" * 80)
            print("OPENALEX AUTHOR SEARCH: 'Suzor'")
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


class TestDateDiagnostics:
    """Diagnostic tests for understanding data structure."""

    async def test_diagnose_date_storage(self, mcp_server):
        """Diagnose how dates are stored in ChromaDB metadata.

        This diagnostic test queries the live ChromaDB collection to understand
        the actual date format stored in metadata. It helps diagnose why date
        filtering (e.g., date_from=2022) returns 0 results.

        The test prints:
        - Raw date field values from metadata
        - Any nested date fields in zotero_data JSON
        - Separate year/month/day fields if present
        - Sample of different date formats to identify patterns

        Run with: uv run pytest src/tests/test_show_results.py::TestSearchResults::test_diagnose_date_storage -xvs -s
        """
        async with Client(mcp_server) as client:
            # Get 20 papers to examine date formats
            result = await client.call_tool(
                "search",
                {
                    "query": "social media",
                    "n_results": 20,
                    "search_mode": "semantic",
                },
            )

            print("\n" + "=" * 80)
            print("DATE STORAGE DIAGNOSTIC")
            print("=" * 80)
            print(f"Total results: {result.data.get('total_results', 0)}")
            print()

            papers = result.data.get("results", [])
            if not papers:
                print("WARNING: No papers found in search results")
                return

            print("Examining date fields in metadata...")
            print()

            # Track unique date formats
            date_formats_seen = set()

            for i, paper in enumerate(papers, 1):
                citation = paper.get("citation", "No citation")[:60]
                print(f"\n{i}. {citation}...")

                # Check for various date-related fields
                date_field = paper.get("date")
                year_field = paper.get("year")
                zotero_data = paper.get("zotero_data")

                print(f"   date field: {repr(date_field)}")
                print(f"   year field: {repr(year_field)}")

                if date_field:
                    date_formats_seen.add(type(date_field).__name__)

                # If zotero_data exists, try to parse it
                if zotero_data:
                    import json
                    try:
                        zotero_dict = json.loads(zotero_data) if isinstance(zotero_data, str) else zotero_data
                        print(f"   zotero_data.date: {repr(zotero_dict.get('date'))}")
                        print(f"   zotero_data.year: {repr(zotero_dict.get('year'))}")
                    except (json.JSONDecodeError, AttributeError) as e:
                        print(f"   zotero_data parse error: {e}")

            # Summary
            print("\n" + "=" * 80)
            print("SUMMARY")
            print("=" * 80)
            print(f"Papers examined: {len(papers)}")
            print(f"Date field types seen: {date_formats_seen}")
            print()
            print("QUESTIONS TO ANSWER:")
            print("1. Is 'date' field present in metadata?")
            print("2. Is it a string like '2022' or '2022-01-01'?")
            print("3. Is it nested in zotero_data JSON?")
            print("4. Is there a separate 'year' field?")
            print("5. What format does ChromaDB's $gte filter expect?")
            print()
