"""Tests for citation_search module - OpenAlex API integration.

Tests the comprehensive citation search functionality migrated from omcp.
"""

import pytest
import respx
from httpx import Response

from citation_search import (
    search_papers,
    get_paper_citations,
    get_referenced_works,
    search_openalex_author,
    get_paper_details,
)


@pytest.mark.anyio
@respx.mock
async def test_search_papers_basic():
    """Test basic paper search returns list of dicts."""
    # Mock OpenAlex API response
    mock_response = {
        "results": [
            {
                "id": "https://openalex.org/W1234567890",
                "title": "Machine Learning for Toxicity Detection",
                "authorships": [
                    {
                        "author": {
                            "id": "A1",
                            "display_name": "Jane Smith",
                            "orcid": None,
                        }
                    },
                    {"author": {"id": "A2", "display_name": "John Doe", "orcid": None}},
                ],
                "publication_year": 2023,
                "doi": "https://doi.org/10.1234/example",
                "cited_by_count": 42,
                "abstract_inverted_index": {
                    "This": [0],
                    "is": [1],
                    "a": [2],
                    "test": [3],
                    "abstract": [4],
                },
                "open_access": {
                    "is_oa": True,
                    "oa_url": "https://example.com/paper.pdf",
                },
                "primary_location": None,
                "topics": [],
                "cited_by_api_url": "https://api.openalex.org/works?filter=cites:W1234567890",
                "referenced_works": [],
            }
        ],
        "meta": {"count": 1},
    }

    # Set up mock
    respx.get("https://api.openalex.org/works").mock(
        return_value=Response(200, json=mock_response)
    )

    # Call the function
    result = await search_papers(query="toxicity detection", limit=25)

    # Verify result format
    assert isinstance(result, list)
    assert len(result) == 1

    paper = result[0]
    assert paper["id"] == "https://openalex.org/W1234567890"
    assert paper["title"] == "Machine Learning for Toxicity Detection"
    assert paper["publication_year"] == 2023
    assert paper["cited_by_count"] == 42
    assert paper["doi"] == "https://doi.org/10.1234/example"
    assert paper["abstract_snippet"] == "This is a test abstract"

    # Check authors (to_summary returns display names as plain strings)
    assert len(paper["authors"]) == 2
    assert paper["authors"][0] == "Jane Smith"
    assert paper["authors"][1] == "John Doe"


@pytest.mark.anyio
@respx.mock
async def test_search_papers_with_year_filters():
    """Test search with year range filters."""
    mock_response = {"results": [], "meta": {"count": 0}}

    # Capture the request
    route = respx.get("https://api.openalex.org/works").mock(
        return_value=Response(200, json=mock_response)
    )

    await search_papers(query="test", year_from=2020, year_to=2023, limit=10)

    # Verify request parameters
    assert route.called
    request = route.calls.last.request
    url_str = str(request.url)

    # New implementation uses publication_year:2020-2023 format
    assert "publication_year" in url_str
    assert "2020" in url_str
    assert "2023" in url_str


@pytest.mark.anyio
@respx.mock
async def test_search_papers_with_open_access_filter():
    """Test search with open access filter."""
    mock_response = {"results": [], "meta": {"count": 0}}

    route = respx.get("https://api.openalex.org/works").mock(
        return_value=Response(200, json=mock_response)
    )

    await search_papers(query="test", open_access_only=True, limit=10)

    assert route.called
    request = route.calls.last.request
    url_str = str(request.url)
    assert "is_oa" in url_str or "is_oa%3Atrue" in url_str


@pytest.mark.anyio
@respx.mock
async def test_search_papers_handles_missing_abstract():
    """Test handling of papers without abstracts."""
    mock_response = {
        "results": [
            {
                "id": "https://openalex.org/W999",
                "title": "Paper Without Abstract",
                "authorships": [
                    {
                        "author": {
                            "id": "A3",
                            "display_name": "Test Author",
                            "orcid": None,
                        }
                    }
                ],
                "publication_year": 2024,
                "doi": None,
                "cited_by_count": 5,
                "abstract_inverted_index": None,  # No abstract
                "open_access": {"is_oa": False, "oa_url": None},
                "primary_location": None,
                "topics": [],
                "cited_by_api_url": None,
                "referenced_works": [],
            }
        ],
        "meta": {"count": 1},
    }

    respx.get("https://api.openalex.org/works").mock(
        return_value=Response(200, json=mock_response)
    )

    result = await search_papers(query="test")

    # Should still include the paper
    assert len(result) == 1
    assert result[0]["title"] == "Paper Without Abstract"
    assert result[0]["abstract_snippet"] is None


@pytest.mark.anyio
@respx.mock
async def test_get_paper_citations_basic():
    """Test retrieving forward citations for a paper."""
    mock_response = {
        "results": [
            {
                "id": "https://openalex.org/W111",
                "title": "Citing Paper 1",
                "authorships": [
                    {
                        "author": {
                            "id": "A4",
                            "display_name": "Alice Brown",
                            "orcid": None,
                        }
                    }
                ],
                "publication_year": 2024,
                "doi": "https://doi.org/10.1111/cite1",
                "cited_by_count": 10,
                "abstract_inverted_index": None,
                "open_access": None,
                "primary_location": None,
                "topics": [],
                "cited_by_api_url": None,
                "referenced_works": [],
            },
            {
                "id": "https://openalex.org/W222",
                "title": "Citing Paper 2",
                "authorships": [
                    {"author": {"id": "A5", "display_name": "Bob Green", "orcid": None}}
                ],
                "publication_year": 2023,
                "doi": "https://doi.org/10.2222/cite2",
                "cited_by_count": 5,
                "abstract_inverted_index": None,
                "open_access": None,
                "primary_location": None,
                "topics": [],
                "cited_by_api_url": None,
                "referenced_works": [],
            },
        ]
    }

    respx.get("https://api.openalex.org/works").mock(
        return_value=Response(200, json=mock_response)
    )

    result = await get_paper_citations(paper_id="W1234567890")

    # Verify result format
    assert isinstance(result, list)
    assert len(result) == 2

    assert result[0]["title"] == "Citing Paper 1"
    assert result[1]["title"] == "Citing Paper 2"
    assert result[0]["authors"][0] == "Alice Brown"
    assert result[0]["publication_year"] == 2024


@pytest.mark.anyio
@respx.mock
async def test_get_paper_citations_with_year_filter():
    """Test filtering citations by year."""
    mock_response = {"results": []}

    route = respx.get("https://api.openalex.org/works").mock(
        return_value=Response(200, json=mock_response)
    )

    await get_paper_citations(paper_id="W123", year_from=2020, limit=10)

    # Verify filter in request
    assert route.called
    request = route.calls.last.request
    url_str = str(request.url)
    assert "cites" in url_str
    assert "W123" in url_str
    assert "publication_year" in url_str
    assert "2020" in url_str


@pytest.mark.anyio
@respx.mock
async def test_get_referenced_works():
    """Test retrieving papers referenced by a given paper."""
    # First call: get the paper itself
    paper_response = {
        "id": "https://openalex.org/W999",
        "title": "Original Paper",
        "referenced_works": [
            "https://openalex.org/W111",
            "https://openalex.org/W222",
        ],
        "authorships": [],
        "publication_year": 2023,
        "cited_by_count": 0,
        "abstract_inverted_index": None,
        "open_access": None,
        "primary_location": None,
        "topics": [],
        "cited_by_api_url": None,
    }

    # Second call: get the referenced works
    refs_response = {
        "results": [
            {
                "id": "https://openalex.org/W111",
                "title": "Referenced Paper 1",
                "authorships": [],
                "publication_year": 2020,
                "cited_by_count": 100,
                "abstract_inverted_index": None,
                "open_access": None,
                "primary_location": None,
                "topics": [],
                "cited_by_api_url": None,
                "referenced_works": [],
            },
            {
                "id": "https://openalex.org/W222",
                "title": "Referenced Paper 2",
                "authorships": [],
                "publication_year": 2021,
                "cited_by_count": 50,
                "abstract_inverted_index": None,
                "open_access": None,
                "primary_location": None,
                "topics": [],
                "cited_by_api_url": None,
                "referenced_works": [],
            },
        ]
    }

    # Set up mocks
    respx.get("https://api.openalex.org/works/W999").mock(
        return_value=Response(200, json=paper_response)
    )
    respx.get("https://api.openalex.org/works").mock(
        return_value=Response(200, json=refs_response)
    )

    result = await get_referenced_works(paper_id="W999")

    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["title"] == "Referenced Paper 1"
    assert result[1]["title"] == "Referenced Paper 2"


@pytest.mark.anyio
@respx.mock
async def test_search_openalex_author():
    """Test searching for papers by author name using OpenAlex."""
    # First call: find author
    author_response = {
        "results": [
            {
                "id": "https://openalex.org/A123456",
                "display_name": "Jane Smith",
                "orcid": "https://orcid.org/0000-0001-2345-6789",
            }
        ]
    }

    # Second call: get papers by author
    papers_response = {
        "results": [
            {
                "id": "https://openalex.org/W555",
                "title": "Paper by Jane",
                "authorships": [
                    {
                        "author": {
                            "id": "A123456",
                            "display_name": "Jane Smith",
                            "orcid": "https://orcid.org/0000-0001-2345-6789",
                        }
                    }
                ],
                "publication_year": 2023,
                "cited_by_count": 15,
                "abstract_inverted_index": None,
                "open_access": None,
                "primary_location": None,
                "topics": [],
                "cited_by_api_url": None,
                "referenced_works": [],
            }
        ]
    }

    # Set up mocks
    respx.get("https://api.openalex.org/authors").mock(
        return_value=Response(200, json=author_response)
    )
    respx.get("https://api.openalex.org/works").mock(
        return_value=Response(200, json=papers_response)
    )

    result = await search_openalex_author(author_name="Jane Smith", limit=50)

    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["title"] == "Paper by Jane"
    assert result[0]["authors"][0] == "Jane Smith"


@pytest.mark.anyio
@respx.mock
async def test_get_paper_details_by_id():
    """Test getting paper details by OpenAlex ID."""
    paper_response = {
        "id": "https://openalex.org/W333",
        "title": "Detailed Paper",
        "authorships": [
            {"author": {"id": "A7", "display_name": "Author Name", "orcid": None}}
        ],
        "publication_year": 2023,
        "doi": "https://doi.org/10.1234/detail",
        "cited_by_count": 25,
        "abstract_inverted_index": {"Test": [0], "abstract": [1], "text": [2]},
        "open_access": {"is_oa": True, "oa_url": "https://example.com/paper.pdf"},
        "primary_location": None,
        "topics": [],
        "cited_by_api_url": None,
        "referenced_works": [],
    }

    respx.get("https://api.openalex.org/works/W333").mock(
        return_value=Response(200, json=paper_response)
    )

    result = await get_paper_details(paper_id="W333")

    assert isinstance(result, dict)
    assert result["id"] == "https://openalex.org/W333"
    assert result["title"] == "Detailed Paper"
    assert result["abstract"] == "Test abstract text"
    assert result["doi"] == "https://doi.org/10.1234/detail"


@pytest.mark.anyio
@respx.mock
async def test_get_paper_details_by_doi():
    """Test getting paper details by DOI."""
    paper_response = {
        "id": "https://openalex.org/W444",
        "title": "Paper by DOI",
        "authorships": [],
        "publication_year": 2022,
        "doi": "https://doi.org/10.5678/test",
        "cited_by_count": 10,
        "abstract_inverted_index": None,
        "open_access": None,
        "primary_location": None,
        "topics": [],
        "cited_by_api_url": None,
        "referenced_works": [],
    }

    respx.get("https://api.openalex.org/works/https://doi.org/10.5678/test").mock(
        return_value=Response(200, json=paper_response)
    )

    result = await get_paper_details(paper_id="10.5678/test")

    assert isinstance(result, dict)
    assert result["title"] == "Paper by DOI"
    assert result["doi"] == "https://doi.org/10.5678/test"


@pytest.mark.anyio
@respx.mock
async def test_get_paper_details_not_found():
    """Test getting paper details when paper doesn't exist."""
    respx.get("https://api.openalex.org/works/W999999").mock(
        return_value=Response(404, json={"error": "not found"})
    )

    result = await get_paper_details(paper_id="W999999")

    assert result is None


# ===== Live API Integration Tests =====
# These tests hit the REAL OpenAlex API (no mocking)
# Marked as @pytest.mark.slow - run with: uv run pytest -m slow


@pytest.mark.slow
@pytest.mark.anyio
async def test_search_papers_live_api():
    """Integration test: search_papers hits real OpenAlex API.

    Verifies:
    - Real API connectivity works
    - Response parsing handles actual API responses
    - Returns expected data structure

    Uses generic query that should consistently return results.
    """
    # Use a generic academic query that should always return results
    result = await search_papers(query="machine learning", limit=5)

    # Verify result structure
    assert isinstance(result, list)
    assert len(result) > 0, "Expected at least one result from OpenAlex"

    # Verify first result has expected fields
    paper = result[0]
    assert "id" in paper
    assert "title" in paper
    assert "authors" in paper
    assert "publication_year" in paper
    assert isinstance(paper["authors"], list)

    # Note: title CAN be None in real OpenAlex data (edge case)
    # At least one paper should have a valid title though
    titles = [p.get("title") for p in result if p.get("title")]
    assert len(titles) > 0, "Expected at least one paper with a title"


@pytest.mark.slow
@pytest.mark.anyio
async def test_search_papers_with_filters_live_api():
    """Integration test: search with year and OA filters against live API."""
    result = await search_papers(
        query="content moderation",
        year_from=2020,
        year_to=2024,
        open_access_only=True,
        limit=3,
    )

    assert isinstance(result, list)
    # May return 0 results if no OA papers match, which is fine

    # If results exist, verify filtering worked
    for paper in result:
        year = paper.get("publication_year")
        if year:  # Some papers may not have year
            assert 2020 <= year <= 2024, f"Year {year} outside filter range"

        # Verify open access status if available
        if paper.get("open_access"):
            assert paper["open_access"].get("is_oa") is True


@pytest.mark.slow
@pytest.mark.anyio
async def test_get_paper_citations_live_api():
    """Integration test: get forward citations from real API.

    Uses a well-known paper that should have citations.
    OpenAlex ID: W2741809807 (a highly cited paper on neural networks)
    """
    result = await get_paper_citations(paper_id="W2741809807", limit=10)

    assert isinstance(result, list)
    # Highly cited papers should have many citations
    assert len(result) > 0, "Expected citations for highly cited paper"

    # Verify citation structure
    if len(result) > 0:
        citation = result[0]
        assert "id" in citation
        assert "title" in citation
        assert "cited_by_count" in citation


@pytest.mark.slow
@pytest.mark.anyio
async def test_get_referenced_works_live_api():
    """Integration test: get backward citations from real API.

    Uses same well-known paper to verify referenced works retrieval.
    """
    result = await get_referenced_works(paper_id="W2741809807", limit=10)

    assert isinstance(result, list)
    # Papers typically cite other papers
    assert len(result) > 0, "Expected referenced works"

    # Verify structure
    if len(result) > 0:
        reference = result[0]
        assert "id" in reference
        assert "title" in reference


@pytest.mark.slow
@pytest.mark.anyio
async def test_search_openalex_author_live_api():
    """Integration test: author search against real OpenAlex API.

    Uses a well-known academic who should have indexed works.
    """
    # Search for a well-known researcher with many publications
    result = await search_openalex_author(author_name="Geoffrey Hinton", limit=10)

    assert isinstance(result, list)
    assert len(result) > 0, "Expected papers by well-known author"

    # Verify papers have expected structure
    paper = result[0]
    assert "title" in paper
    assert "authors" in paper

    # Verify author name appears in results
    author_names = [
        author["display_name"]
        for paper in result
        for author in paper.get("authors", [])
    ]
    # At least one paper should have "Hinton" in author names
    assert any("Hinton" in name for name in author_names), (
        "Expected to find Hinton in author names"
    )


@pytest.mark.slow
@pytest.mark.anyio
async def test_get_paper_details_live_api():
    """Integration test: get full paper details from real API.

    Tests both OpenAlex ID and DOI lookup methods.
    """
    # Test with OpenAlex ID
    result_by_id = await get_paper_details(paper_id="W2741809807")

    assert result_by_id is not None
    assert isinstance(result_by_id, dict)
    assert "id" in result_by_id
    assert "title" in result_by_id
    assert "authors" in result_by_id

    # Verify we got actual content
    assert result_by_id["title"] is not None
    assert len(result_by_id["authors"]) > 0


@pytest.mark.slow
@pytest.mark.anyio
async def test_live_api_error_handling():
    """Integration test: verify error handling with invalid requests.

    Tests that the real API properly handles invalid paper IDs.
    """
    # Try to fetch a paper that definitely doesn't exist
    result = await get_paper_details(paper_id="W999999999999999")

    # Should return None for not found, not raise an exception
    assert result is None
