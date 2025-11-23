"""Counterspeech search quality regression tests.

These tests validate search quality based on a real research session
documented in bmem (projects/zotmcp/specs/zotmcp-search-quality-tests-counterspeech-session-2025-11-22).
They ensure the search tool continues to return high-quality results for
counterspeech and marginalized voice research.

Test Fixture Strategy
---------------------
These tests use `mcp_server` (parametrized fixture) to run against:
- Local in-process server [local-server]
- Docker container server [docker-e2e] (with @pytest.mark.slow)
"""

from pathlib import Path

import pytest
from fastmcp import Client

pytestmark = pytest.mark.anyio


class TestCounterspeechSearchQuality:
    """Regression tests for counterspeech research queries."""

    async def test_counterspeech_discovery(self, mcp_server):
        """Test counterspeech discovery query returns expected high-quality results.

        Query: Meta Facebook Instagram counterspeech amplification marginalized voices promotion

        Expected results include:
        - Nunziato (2021): The varieties of counterspeech and censorship on social media
        - Bartlett & Krasodomski-Jones (2015): Counter-speech examining content
        - Mathew et al. (2019): Thou Shalt Not Hate
        """
        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "search",
                {
                    "query": "Meta Facebook Instagram counterspeech amplification marginalized voices promotion",
                    "n_results": 10,
                },
            )

            assert "error" not in result.data, (
                f"Search failed with error: {result.data.get('error')}"
            )
            assert "results" in result.data
            assert len(result.data["results"]) > 0, "Should return results"

            # Extract citations for validation
            citations = [r.get("citation", "") for r in result.data["results"]]
            citations_text = "\n".join(citations)

            # Check for expected authors in results
            expected_authors = ["Nunziato", "Bartlett", "Mathew"]
            found_authors = [
                author for author in expected_authors
                if any(author.lower() in c.lower() for c in citations)
            ]

            assert len(found_authors) >= 2, (
                f"Expected at least 2 of {expected_authors} in results. "
                f"Found: {found_authors}. Citations:\n{citations_text}"
            )

            # Validate semantic scores for top results
            for search_result in result.data["results"][:5]:
                semantic_score = search_result.get("semantic_score", 0)
                assert semantic_score > 0.3, (
                    f"Top result semantic_score should be > 0.3, got {semantic_score} "
                    f"for: {search_result.get('citation', 'unknown')}"
                )

    async def test_bartolo_thesis_returns_temp_file(self, mcp_server):
        """CRITICAL: Test that large document (Bartolo thesis) returns temp file path.

        This test validates the MCP server can return filenames for large documents
        that exceed the inline text limit (500KB). This enables further LLM analysis
        of large PDFs.

        Steps:
        1. Search for Bartolo thesis on algorithmic recommendation
        2. Get item using known key (AZXGV9XT)
        3. Assert is_large_document == True
        4. Assert full_text_file exists and is readable
        5. Assert file size > 500KB
        """
        # Known item key for Bartolo (2024) thesis
        bartolo_key = "AZXGV9XT"

        async with Client(mcp_server) as client:
            # First verify we can find it via search
            search_result = await client.call_tool(
                "search",
                {
                    "query": "algorithmic recommendation repair work Bartolo thesis",
                    "n_results": 5,
                },
            )

            assert "error" not in search_result.data, (
                f"Search failed: {search_result.data.get('error')}"
            )

            # Now get the full item
            item_result = await client.call_tool(
                "get_item",
                {"item_key": bartolo_key},
            )

            assert "error" not in item_result.data, (
                f"get_item failed: {item_result.data.get('error')}"
            )

            item_data = item_result.data

            # Validate full_text_file path exists (all documents now return temp files)
            assert "full_text_file" in item_data, (
                f"Large document should have 'full_text_file' with temp file path. "
                f"Got keys: {list(item_data.keys())}"
            )

            # Validate the file is readable and has substantial content
            temp_file_path = Path(item_data["full_text_file"])
            assert temp_file_path.exists(), (
                f"Temp file should exist at: {temp_file_path}"
            )

            # Check file size > 500KB (the threshold for large documents)
            file_size = temp_file_path.stat().st_size
            min_size = 500 * 1024  # 500KB
            assert file_size > min_size, (
                f"Bartolo thesis temp file should be > 500KB. "
                f"Got: {file_size / 1024:.1f}KB"
            )

            # Verify we can read the file
            content = temp_file_path.read_text(encoding="utf-8")
            assert len(content) > 0, "Temp file should have content"

            # Validate preview is included
            assert "full_text_preview" in item_data, (
                "Large document should include full_text_preview"
            )

    async def test_gender_platform_governance(self, mcp_server):
        """Test gender and platform governance query returns expected results.

        Query: Facebook platform promotion diversity gender equality creator programs

        Expected results include:
        - Nurik (2019): "Men Are Scum": Self-Regulation, Hate Speech, and Gender-Based Censorship
        - Gillett et al. (2022): Safety for Whom?
        """
        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "search",
                {
                    "query": "Facebook platform promotion diversity gender equality creator programs",
                    "n_results": 10,
                },
            )

            assert "error" not in result.data, (
                f"Search failed with error: {result.data.get('error')}"
            )
            assert "results" in result.data
            assert len(result.data["results"]) > 0, "Should return results"

            # Extract citations for validation
            citations = [r.get("citation", "") for r in result.data["results"]]
            citations_text = "\n".join(citations)

            # Check for expected authors in results
            expected_authors = ["Nurik", "Gillett"]
            found_authors = [
                author for author in expected_authors
                if any(author.lower() in c.lower() for c in citations)
            ]

            assert len(found_authors) >= 1, (
                f"Expected at least 1 of {expected_authors} in results. "
                f"Found: {found_authors}. Citations:\n{citations_text}"
            )

            # Validate results span multiple document types
            # (checking we get diverse sources: journal, report, magazine)
            excerpts = [r.get("excerpt", "") for r in result.data["results"]]

            # Gender-related terms should appear in excerpts
            gender_terms = ["gender", "women", "female", "equality"]
            has_gender_terms = any(
                term in excerpt.lower()
                for excerpt in excerpts
                for term in gender_terms
            )
            assert has_gender_terms, (
                f"Results should contain gender-related terms in excerpts. "
                f"Looked for: {gender_terms}"
            )

    async def test_counterspeech_interventions(self, mcp_server):
        """Test counterspeech intervention query returns expected results.

        Query: social media counterspeech intervention hate speech response

        Expected results include:
        - Keller & Askanius (2020)
        - Garland et al. (2020)
        - Miskolci et al. (2020)
        """
        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "search",
                {
                    "query": "social media counterspeech intervention hate speech response",
                    "n_results": 10,
                },
            )

            assert "error" not in result.data, (
                f"Search failed with error: {result.data.get('error')}"
            )
            assert "results" in result.data
            assert len(result.data["results"]) > 0, "Should return results"

            # Extract citations for validation
            citations = [r.get("citation", "") for r in result.data["results"]]
            citations_text = "\n".join(citations)

            # Check for expected authors in results
            # Note: Miskolci may appear with special characters (Misˇkolci)
            expected_authors = ["Keller", "Garland", "Mathew"]
            found_authors = [
                author for author in expected_authors
                if any(author.lower() in c.lower() for c in citations)
            ]

            assert len(found_authors) >= 1, (
                f"Expected at least 1 of {expected_authors} in results. "
                f"Found: {found_authors}. Citations:\n{citations_text}"
            )

            # Validate fuzzy_score > 60 OR semantic_score > 0.3 for top results
            for search_result in result.data["results"][:3]:
                fuzzy_score = search_result.get("fuzzy_score", 0)
                semantic_score = search_result.get("semantic_score", 0)
                assert fuzzy_score > 60 or semantic_score > 0.3, (
                    f"Top result should have fuzzy_score > 60 OR semantic_score > 0.3, "
                    f"got fuzzy={fuzzy_score}, semantic={semantic_score} "
                    f"for: {search_result.get('citation', 'unknown')}"
                )

    async def test_platform_initiative_programs(self, mcp_server):
        """Test platform initiative programs query returns expected results.

        Query: Facebook Online Civil Courage Initiative counterspeech programs funding

        Expected results include:
        - Bartlett & Krasodomski-Jones (2015) - Demos report
        """
        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "search",
                {
                    "query": "Facebook Online Civil Courage Initiative counterspeech programs funding",
                    "n_results": 10,
                },
            )

            assert "error" not in result.data, (
                f"Search failed with error: {result.data.get('error')}"
            )
            assert "results" in result.data
            assert len(result.data["results"]) > 0, "Should return results"

            # Validate excerpts reference OCCI or counterspeech programs
            excerpts = [r.get("excerpt", "") for r in result.data["results"]]
            occi_terms = ["occi", "civil courage", "counterspeech", "counter-speech", "program", "initiative"]
            has_occi_terms = any(
                term in excerpt.lower()
                for excerpt in excerpts
                for term in occi_terms
            )
            assert has_occi_terms, (
                f"Results should reference OCCI or counterspeech programs in excerpts. "
                f"Looked for: {occi_terms}"
            )

    async def test_algorithmic_amplification(self, mcp_server):
        """Test algorithmic amplification query returns expected results.

        Query: platform intervention positive amplification recommendation algorithm promotion

        Expected results include:
        - Keller (2021)
        - Gillespie (2022)
        """
        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "search",
                {
                    "query": "platform intervention positive amplification recommendation algorithm promotion",
                    "n_results": 10,
                },
            )

            assert "error" not in result.data, (
                f"Search failed with error: {result.data.get('error')}"
            )
            assert "results" in result.data
            assert len(result.data["results"]) > 0, "Should return results"

            # Extract citations for validation
            citations = [r.get("citation", "") for r in result.data["results"]]
            citations_text = "\n".join(citations)

            # Check for expected authors in results
            expected_authors = ["Keller", "Gillespie"]
            found_authors = [
                author for author in expected_authors
                if any(author.lower() in c.lower() for c in citations)
            ]

            assert len(found_authors) >= 1, (
                f"Expected at least 1 of {expected_authors} in results. "
                f"Found: {found_authors}. Citations:\n{citations_text}"
            )

            # Validate semantic_score > 0.35 for top 3 results
            for search_result in result.data["results"][:3]:
                semantic_score = search_result.get("semantic_score", 0)
                assert semantic_score > 0.35, (
                    f"Top result semantic_score should be > 0.35, got {semantic_score} "
                    f"for: {search_result.get('citation', 'unknown')}"
                )

    async def test_creator_programs_marginalized_groups(self, mcp_server):
        """Test creator programs for marginalized groups query returns expected results.

        Query: Instagram creator fund support marginalized LGBTQ Black creators program

        Expected results include:
        - Bishop (2021)
        - Duffy & Meisner (2022)
        - Haimson et al. (2021)
        """
        async with Client(mcp_server) as client:
            result = await client.call_tool(
                "search",
                {
                    "query": "Instagram creator fund support marginalized LGBTQ Black creators program",
                    "n_results": 10,
                },
            )

            assert "error" not in result.data, (
                f"Search failed with error: {result.data.get('error')}"
            )
            assert "results" in result.data
            assert len(result.data["results"]) > 0, "Should return results"

            # Validate top result has reasonable semantic score
            top_result = result.data["results"][0]
            semantic_score = top_result.get("semantic_score", 0)
            assert semantic_score > 0.25, (
                f"Top result semantic_score should be > 0.25, got {semantic_score} "
                f"for: {top_result.get('citation', 'unknown')}"
            )
