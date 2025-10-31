"""Tests for citation_search module - OpenAlex API integration."""

import pytest
import respx
from httpx import Response

from citation_search import search_papers


@pytest.mark.anyio
@respx.mock
async def test_search_papers_basic():
    """Test basic paper search returns formatted results."""
    # Mock OpenAlex API response
    mock_response = {
        "results": [
            {
                "id": "https://openalex.org/W1234567890",
                "title": "Machine Learning for Toxicity Detection",
                "authorships": [
                    {"author": {"display_name": "Jane Smith"}},
                    {"author": {"display_name": "John Doe"}},
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
                "open_access": {"is_oa": True, "oa_url": "https://example.com/paper.pdf"},
            }
        ]
    }

    # Set up mock
    respx.get("https://api.openalex.org/works").mock(
        return_value=Response(200, json=mock_response)
    )

    # Call the function
    result = await search_papers(query="toxicity detection", limit=20)

    # Verify result format
    assert isinstance(result, str)
    assert "Machine Learning for Toxicity Detection" in result
    assert "Jane Smith" in result
    assert "2023" in result
    assert "42" in result  # citation count
    assert "10.1234/example" in result  # DOI


@pytest.mark.anyio
@respx.mock
async def test_search_papers_with_year_filters():
    """Test search with year range filters."""
    mock_response = {"results": []}

    # Capture the request
    route = respx.get("https://api.openalex.org/works").mock(
        return_value=Response(200, json=mock_response)
    )

    await search_papers(query="test", year_from=2020, year_to=2023, limit=10)

    # Verify request parameters - check for URL-encoded versions
    assert route.called
    request = route.calls.last.request
    url_str = str(request.url)
    # URL encoding converts : to %3A and , to %2C
    assert "from_publication_date" in url_str
    assert "2020-01-01" in url_str
    assert "to_publication_date" in url_str
    assert "2023-12-31" in url_str


@pytest.mark.anyio
@respx.mock
async def test_search_papers_handles_missing_abstract():
    """Test handling of papers without abstracts."""
    mock_response = {
        "results": [
            {
                "id": "https://openalex.org/W999",
                "title": "Paper Without Abstract",
                "authorships": [{"author": {"display_name": "Test Author"}}],
                "publication_year": 2024,
                "doi": None,
                "cited_by_count": 5,
                "abstract_inverted_index": None,  # No abstract
                "open_access": {"is_oa": False, "oa_url": None},
            }
        ]
    }

    respx.get("https://api.openalex.org/works").mock(
        return_value=Response(200, json=mock_response)
    )

    result = await search_papers(query="test")

    # Should still include the paper
    assert "Paper Without Abstract" in result
    assert "Test Author" in result
